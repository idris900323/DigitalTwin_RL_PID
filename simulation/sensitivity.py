"""Sensitivity analysis of the preliminary digital twin (master prompt section 16, G3.2).

Question answered: which plant parameters matter most for the closed-loop step response, so we know what to
measure on the real motor first? Controller held at the Tuned gains (15 / 0 / 0.3), 90 deg step, bare shaft.

Parts
  1. One-at-a-time (OAT): R, Kt, Ke, Jm, Bm, eta by -50/-20/+20/+50 %; L at 0.1 ... 5 mH (absolute, nominal is 0);
     control delay 1-3 samples; supply voltage +-5 % (datasheet tier). Parameter sets method_a/method_c (and any
     other simulatable set) are compared as an extra bar.
  2. Global Morris screening (elementary effects, numpy only) with ranges set by provenance confidence
     (config `sensitivity_ranges`: datasheet +-5 %, calculated +-20 %, assumed +-50 %, Jm/Bm a factor of 3,
     L 0.1-5 mH, delay 0-3 samples), bootstrap confidence intervals over trajectories.
  3. Ke/Kt consistency: an ideal DC motor has Ke = Kt in SI; method_c deliberately does not (ratio 3.2). The study
     runs (a) the nominal set with Ke = Kt forced to Kt, to Ke and to their geometric mean and (b) a Monte-Carlo
     comparison of independent Ke, Kt versus a single shared K, to show whether the inconsistency is itself a
     leading driver.
  4. Robustness preview for the RL tuner: the committed policy's gains versus the Tuned preset and the legacy
     default on the perturbed plants.

Conditions: ``--loaded`` repeats everything with a 1 kg payload at 10 cm and gravity on (vertical plane). The bare
shaft has no load torque, so the gearbox efficiency eta cannot matter there; the loaded run shows when it does.

Everything is simulated on the unvalidated twin (PRELIMINARY). Outputs go to ``--out-dir`` (default
``results/sensitivity``): sensitivity_oat.csv, sensitivity_table.md, sensitivity_tornado.png, sensitivity_morris.png,
sensitivity_morris.csv, sensitivity_morris_samples.csv, sensitivity_keKt.csv, sensitivity_rl_robustness.csv,
sensitivity_ranking.md, oat_raw.csv (per-tick logs in the project schema) and sensitivity_manifest.json.
Seeded and deterministic.

    python simulation/sensitivity.py                  # full study, a few minutes
    python simulation/sensitivity.py --smoke          # tiny version for CI
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402

from models.factory import build_twin_from_config  # noqa: E402
from models.joint import Joint, JointParams  # noqa: E402
from simulation import rawlog  # noqa: E402
from simulation.metrics import all_metrics  # noqa: E402

CONFIG_PATH = ROOT / "config" / "motor_parameters.yaml"
PARAMS = ("V_supply", "R", "Kt", "Ke", "Jm", "Bm", "eta", "L", "delay_steps")
OAT_PARAMS = ("R", "Kt", "Ke", "Jm", "Bm", "eta", "L", "delay_steps", "V_supply")
REL_LEVELS = (-0.5, -0.2, 0.2, 0.5)
L_LEVELS_H = (1e-4, 5e-4, 1e-3, 2e-3, 5e-3)       # 0.1 ... 5 mH, inside the range where DCMotor.step sub-steps stably
DELAY_LEVELS = (1, 2, 3)
VSUPPLY_LEVELS = (-0.05, 0.05)
METRICS = ("overshoot_pct", "settle_s", "rise_s", "iae_deg_s", "peak_current_A", "sse_deg")
MORRIS_OUT = ("overshoot_pct", "settle_s", "iae_deg_s", "peak_current_A", "sse_deg")
# Condition the study runs under (set by main): bare shaft by default, ``--loaded`` for a gravity-loaded arm.
LOADED_JOINT = dict(payload_mass_kg=1.0, arm_length_m=0.10, gravity_on=True)
_COND = {"joint": None, "name": "bare shaft"}
TUNED = (15.0, 0.0, 0.3)
LEGACY = (5.0, 20.0, 0.05)
MEASURE_HINT = {
    "R": "winding resistance: low-voltage locked-rotor test with a current limit (or 4-wire ohmmeter)",
    "Kt": "torque constant: measure stall/low-speed torque against current with a torque arm",
    "Ke": "back-EMF constant: speed-versus-voltage line at several voltages, or coast-down generator voltage",
    "Jm": "rotor inertia: free-run speed decay / mechanical time constant, ideally with a known added inertia",
    "Bm": "viscous friction: steady-state speed versus current at low speeds, both directions",
    "eta": "gearbox efficiency: loaded versus no-load current at a known output torque",
    "L": "armature inductance: LCR meter or a voltage-step current rise",
    "delay_steps": "loop dead time: timing audit of the real controller/driver (scope on command and PWM)",
    "V_supply": "supply voltage under load: log the rail during a step with the real supply and wiring",
}


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ----------------------------------------------------------------------------------------------- plant perturbation
def nominal(cfg: dict) -> dict:
    sc = cfg["simulation"]["active_electrical_scenario"]
    d, e = cfg["base_motor"]["derived"][sc], cfg["base_motor"]["estimated"]
    return {"V_supply": cfg["supply"]["V_rated"], "R": d["R_ohm"], "Kt": d["Kt_Nm_per_A"], "Ke": d["Ke_V_s_per_rad"],
            "Jm": e["Jm_kgm2"], "Bm": d.get("Bm_Nms_per_rad", e["Bm_Nms_per_rad"]),
            "eta": d.get("gearbox_efficiency", cfg["gearbox"]["efficiency"]), "L": e["L_H"],
            "delay_steps": cfg.get("driver", {}).get("delay_steps", 0)}


def perturbed_cfg(cfg: dict, values: dict) -> dict:
    """Copy of ``cfg`` with the active parameter set overridden by ``values`` (keys of ``PARAMS``)."""
    c = copy.deepcopy(cfg)
    sc = c["simulation"]["active_electrical_scenario"]
    d, e = c["base_motor"]["derived"][sc], c["base_motor"]["estimated"]
    for k, v in values.items():
        if k == "V_supply":
            c["supply"]["V_rated"] = float(v)
        elif k == "R":
            d["R_ohm"] = float(v)
        elif k == "Kt":
            d["Kt_Nm_per_A"] = float(v)
        elif k == "Ke":
            d["Ke_V_s_per_rad"] = float(v)
        elif k == "Jm":
            e["Jm_kgm2"] = float(v)
        elif k == "Bm":
            e["Bm_Nms_per_rad"] = float(v)
            if "Bm_Nms_per_rad" in d:
                d["Bm_Nms_per_rad"] = float(v)
        elif k == "eta":
            c["gearbox"]["efficiency"] = float(v)
            if "gearbox_efficiency" in d:
                d["gearbox_efficiency"] = float(v)
        elif k == "L":
            e["L_H"] = float(v)
        elif k == "delay_steps":
            c.setdefault("driver", {})["delay_steps"] = int(v)
        else:
            raise KeyError(k)
    return c


def run(cfg: dict, gains=TUNED, *, target_deg=90.0, t_end=2.0, joint=None, scenario=None, keep_log=False):
    """One closed-loop step response on ``cfg``; returns (metrics dict, log or None)."""
    tw = build_twin_from_config(cfg, *gains, scenario=scenario, joint=joint or _COND["joint"] or Joint(JointParams()))
    log = tw.run(math.radians(target_deg), int(round(t_end / tw.dt)))
    m = all_metrics(log["t"], np.degrees(log["theta_out"]), target_deg, log["V_applied"], log["i_motor"],
                    error_deg=np.degrees(log["error"]))
    return m, (log if keep_log else None)


def finite(m: dict, t_end=2.0) -> dict:
    """Metric dict with 'never settles / never rises' (NaN) replaced by the window length, for statistics."""
    out = dict(m)
    for k in ("settle_s", "rise_s", "time_to_2pct_s"):
        if isinstance(out.get(k), float) and math.isnan(out[k]):
            out[k] = t_end
    out["sse_deg"] = abs(out["sse_deg"])
    return out


# ----------------------------------------------------------------------------------------------- 1. one-at-a-time
def oat_cases(cfg: dict) -> list:
    """List of (parameter, level label, parameter values dict) around the nominal set."""
    nom = nominal(cfg)
    cases = [("nominal", "nominal", {})]
    for p in ("R", "Kt", "Ke", "Jm", "Bm", "eta"):
        for lv in REL_LEVELS:
            v = nom[p] * (1.0 + lv)
            if p == "eta":
                v = min(v, 1.0)               # an efficiency cannot exceed 1
            cases.append((p, f"{lv * 100:+.0f}%", {p: v}))
    for L in L_LEVELS_H:
        cases.append(("L", f"{L * 1e3:g} mH", {"L": L}))
    for d in DELAY_LEVELS:
        cases.append(("delay_steps", f"{d} sample(s)", {"delay_steps": d}))
    for lv in VSUPPLY_LEVELS:
        cases.append(("V_supply", f"{lv * 100:+.0f}%", {"V_supply": nom["V_supply"] * (1.0 + lv)}))
    return cases


def run_oat(cfg: dict, t_end: float, keep_logs: bool):
    rows, blocks = [], []
    jp = _COND["joint"].p if _COND["joint"] else JointParams()
    for k, (p, lv, vals) in enumerate(oat_cases(cfg)):
        m, log = run(perturbed_cfg(cfg, vals), TUNED, t_end=t_end, keep_log=keep_logs)
        rows.append(dict(parameter=p, level=lv, value=vals.get(p, nominal(cfg).get(p)), **m))
        if keep_logs:
            blocks.append(rawlog.rows_from_twin_log(
                log, target_deg=90.0, gains=TUNED, cpr=cfg["encoder"]["output_cpr"], v_supply=vals.get("V_supply", cfg["supply"]["V_rated"]),
                run_id=f"S-03-oat-{k}", experiment_id="S-03", seed=0, method=f"OAT {p} {lv}", true_params={**nominal(cfg), **vals},
                payload_kg=jp.payload_mass_kg, arm_len_m=jp.arm_length_m, gravity_on=jp.gravity_on))
    return rows, blocks


def run_method_sets(cfg: dict, t_end: float):
    rows = []
    for name, d in cfg["base_motor"]["derived"].items():
        if d.get("R_ohm") is None or d.get("Kt_Nm_per_A") is None:
            continue
        m, _ = run(cfg, TUNED, t_end=t_end, scenario=name)
        rows.append(dict(parameter="parameter set", level=name, value=float("nan"), **m))
    return rows


# ----------------------------------------------------------------------------------------------- 2. Morris screening
def ranges(cfg: dict) -> dict:
    """Per-parameter sampling spec from the YAML ``sensitivity_ranges`` section."""
    sr, nom = cfg["sensitivity_ranges"], nominal(cfg)
    spec = {}
    for p in PARAMS:
        t = sr["parameters"][p]
        tier = t["tier"]
        if tier in ("datasheet", "calculated", "assumed"):
            rel = sr[f"{tier}_rel"]
            spec[p] = dict(kind="uniform", lo=nom[p] * (1 - rel), hi=nom[p] * (1 + rel), clip=t.get("clip"))
        elif tier == "order_of_magnitude":
            f = sr["order_of_magnitude_factor"]
            spec[p] = dict(kind="log", lo=nom[p] / f, hi=nom[p] * f, clip=None)
        elif tier == "absolute":
            spec[p] = dict(kind="uniform", lo=t["min"], hi=t["max"], clip=None)
        elif tier == "integer":
            spec[p] = dict(kind="integer", lo=t["min"], hi=t["max"], clip=None)
        else:
            raise ValueError(f"unknown tier {tier!r} for {p}")
    return spec


def from_unit(spec: dict, u: dict) -> dict:
    """Map unit-cube coordinates to parameter values."""
    out = {}
    for p, s in spec.items():
        x = u[p]
        if s["kind"] == "uniform":
            v = s["lo"] + (s["hi"] - s["lo"]) * x
        elif s["kind"] == "log":
            v = math.exp(math.log(s["lo"]) + (math.log(s["hi"]) - math.log(s["lo"])) * x)
        else:
            v = int(round(s["lo"] + (s["hi"] - s["lo"]) * x))
        if s.get("clip"):
            v = min(max(v, s["clip"][0]), s["clip"][1])
        out[p] = v
    return out


def morris_design(k: int, r: int, rng: np.random.Generator, levels: int = 4):
    """Morris (1991) trajectories on a ``levels``-point grid. Returns an array (r, k+1, k) and the factor order per step."""
    delta = levels / (2.0 * (levels - 1))
    grid = np.arange(levels // 2) / (levels - 1)         # starting points keep x + delta <= 1
    X = np.empty((r, k + 1, k))
    order = np.empty((r, k), dtype=int)
    for t in range(r):
        x = rng.choice(grid, size=k)
        perm = rng.permutation(k)
        sign = rng.choice([-1.0, 1.0], size=k)
        X[t, 0] = x
        cur = x.copy()
        for step, i in enumerate(perm):
            if sign[i] > 0 and cur[i] + delta <= 1.0 + 1e-12:
                cur[i] += delta
            elif cur[i] - delta >= -1e-12:
                cur[i] -= delta
            else:
                cur[i] += delta
            X[t, step + 1] = cur
            order[t, step] = i
    return X, order, delta


def run_morris(cfg: dict, r: int, seed: int, t_end: float, n_boot: int = 1000):
    spec = ranges(cfg)
    names = list(PARAMS)
    rng = np.random.default_rng(seed)
    X, order, delta = morris_design(len(names), r, rng)
    Y = np.empty((r, len(names) + 1, len(MORRIS_OUT)))
    samples = []
    for t in range(r):
        for s in range(len(names) + 1):
            vals = from_unit(spec, dict(zip(names, X[t, s])))
            m = finite(run(perturbed_cfg(cfg, vals), TUNED, t_end=t_end)[0], t_end)
            Y[t, s] = [m[k] for k in MORRIS_OUT]
            samples.append(dict(trajectory=t, step=s, **{p: vals[p] for p in names}, **{k: m[k] for k in MORRIS_OUT}))
    EE = np.zeros((r, len(names), len(MORRIS_OUT)))
    for t in range(r):
        for step in range(len(names)):
            i = order[t, step]
            dx = X[t, step + 1, i] - X[t, step, i]
            EE[t, i] = (Y[t, step + 1] - Y[t, step]) / dx            # effect per unit of the parameter's full range
    mu_star = np.mean(np.abs(EE), axis=0)
    sigma = np.std(EE, axis=0, ddof=1) if r > 1 else np.zeros_like(mu_star)
    brng = np.random.default_rng(seed + 1)
    boots = np.empty((n_boot,) + mu_star.shape)
    for b in range(n_boot):
        idx = brng.integers(0, r, r)
        boots[b] = np.mean(np.abs(EE[idx]), axis=0)
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    return dict(names=names, mu_star=mu_star, sigma=sigma, ci_lo=lo, ci_hi=hi, samples=samples, r=r, delta=delta)


# ----------------------------------------------------------------------------------------------- 3. Ke/Kt consistency
def run_keKt(cfg: dict, n: int, seed: int, t_end: float):
    nom = nominal(cfg)
    Kt, Ke = nom["Kt"], nom["Ke"]
    fixed = {"nominal (Ke/Kt = %.2f)" % (Ke / Kt): {},
             "Ke = Kt = Kt": {"Ke": Kt}, "Ke = Kt = Ke": {"Kt": Ke}, "Ke = Kt = geometric mean": {"Kt": math.sqrt(Kt * Ke), "Ke": math.sqrt(Kt * Ke)}}
    rows = []
    for name, vals in fixed.items():
        m = finite(run(perturbed_cfg(cfg, vals), TUNED, t_end=t_end)[0], t_end)
        rows.append(dict(case=name, **{k: m[k] for k in MORRIS_OUT}))
    rng = np.random.default_rng(seed + 2)
    rel = cfg["sensitivity_ranges"]["calculated_rel"]
    out = {}
    for label in ("independent Ke, Kt (each +-20 %)", "single shared K in [Kt, Ke] (log-uniform)"):
        ms = []
        for _ in range(n):
            R = nom["R"] * (1 + rel * (2 * rng.random() - 1))
            if label.startswith("independent"):
                vals = {"R": R, "Kt": Kt * (1 + rel * (2 * rng.random() - 1)), "Ke": Ke * (1 + rel * (2 * rng.random() - 1))}
            else:
                K = math.exp(math.log(Kt) + (math.log(Ke) - math.log(Kt)) * rng.random())
                vals = {"R": R, "Kt": K, "Ke": K}
            ms.append(finite(run(perturbed_cfg(cfg, vals), TUNED, t_end=t_end)[0], t_end))
        out[label] = {k: (float(np.mean([m[k] for m in ms])), float(np.std([m[k] for m in ms], ddof=1))) for k in MORRIS_OUT}
    return rows, out


# ----------------------------------------------------------------------------------------------- 4. RL robustness preview
def policy_gains_nominal(cfg: dict):
    """Gains the committed policy picks for the bare-shaft, 90 deg, full-voltage context (the case analysed here)."""
    sys.path.insert(0, str(ROOT / "autotune_360"))
    import autotune_360.train_autotune_360 as T
    d = json.loads((ROOT / "autotune_360" / "autotune_policy_360.json").read_text())
    pol = T.Policy(np.random.default_rng(0))
    for k in ("W1", "b1", "W2", "b2", "W3", "b3"):
        pol.p[k] = np.array(d[k])
    one = lambda v: np.array([v], dtype=float)
    jp = _COND["joint"].p if _COND["joint"] else JointParams(arm_length_m=0.05)       # bare shaft: no payload mass
    g = T.policy_gains(pol, one(jp.payload_mass_kg), one(jp.arm_length_m), one(float(jp.gravity_on)), one(100.0), one(90.0))[0]
    return tuple(float(x) for x in g)


def run_rl_robustness(cfg: dict, t_end: float, max_cases: int = 0):
    rl = policy_gains_nominal(cfg)
    gains = {"RL policy (committed)": rl, "Tuned preset": TUNED, "Legacy default": LEGACY}
    rows = []
    for name, g in gains.items():
        for p, lv, vals in oat_cases(cfg)[: max_cases or None]:
            if p in ("V_supply",):
                continue
            m = finite(run(perturbed_cfg(cfg, vals), g, t_end=t_end)[0], t_end)
            ok = abs(m["sse_deg"]) < 0.02 * 90.0
            rows.append(dict(controller=name, Kp=g[0], Ki=g[1], Kd=g[2], parameter=p, level=lv,
                             **{k: m[k] for k in ("overshoot_pct", "settle_s", "iae_deg_s", "peak_current_A", "sse_deg")},
                             within_2pct=int(ok)))
    return gains, rows


# ----------------------------------------------------------------------------------------------- reporting
def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if isinstance(v, float) and math.isnan(v) else (f"{v:.6g}" if isinstance(v, float) else v))
                        for k, v in r.items()})


def tornado(path, oat_rows, method_rows):
    nomrow = next(r for r in oat_rows if r["parameter"] == "nominal")
    fig, axes = plt.subplots(2, 3, figsize=(13, 7))
    for ax, metric in zip(axes.ravel(), METRICS):
        base = finite(nomrow)[metric] if metric == "sse_deg" else nomrow[metric]
        base = 2.0 if (isinstance(base, float) and math.isnan(base)) else base
        spans = []
        for p in OAT_PARAMS:
            vals = [r[metric] for r in oat_rows if r["parameter"] == p]
            vals = [2.0 if (isinstance(v, float) and math.isnan(v)) else v for v in vals]
            spans.append((max(vals) - min(vals), p, min(vals), max(vals)))
        for r in method_rows:
            if r["level"] != "method_c":
                v = r[metric]
                v = 2.0 if (isinstance(v, float) and math.isnan(v)) else v
                spans.append((abs(v - base), f"set: {r['level']}", min(v, base), max(v, base)))
        spans.sort()
        for y, (_s, label, lo, hi) in enumerate(spans):
            ax.barh(y, hi - lo, left=lo, color="#0072B2" if not label.startswith("set") else "#D55E00", height=0.6)
        ax.axvline(base, color="k", linewidth=0.8)
        ax.set_yticks(range(len(spans))); ax.set_yticklabels([s[1] for s in spans], fontsize=8)
        ax.set_xlabel(metric.replace("_", " ")); ax.grid(alpha=0.3, axis="x")
    fig.suptitle("One-at-a-time sensitivity, Tuned gains (simulated, preliminary twin); black line = nominal method_c; "
                 "bars span the tested levels, orange = other parameter sets", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=140, metadata={"Software": None})
    plt.close(fig)


def morris_plot(path, mo):
    fig, axes = plt.subplots(1, len(MORRIS_OUT), figsize=(3.2 * len(MORRIS_OUT), 4.2), sharey=True)
    order = np.argsort(np.mean(mo["mu_star"] / (np.max(mo["mu_star"], axis=0) + 1e-12), axis=1))
    for j, (ax, metric) in enumerate(zip(axes, MORRIS_OUT)):
        y = np.arange(len(order))
        mu = mo["mu_star"][order, j]
        err = np.vstack([mu - mo["ci_lo"][order, j], mo["ci_hi"][order, j] - mu])
        ax.barh(y, mu, xerr=np.maximum(err, 0), color="#0072B2", error_kw=dict(ecolor="k", lw=0.8))
        ax.set_yticks(y); ax.set_yticklabels([mo["names"][i] for i in order], fontsize=8)
        ax.set_xlabel(f"mu* of {metric}"); ax.grid(alpha=0.3, axis="x")
    fig.suptitle(f"Morris screening (r = {mo['r']} trajectories; bars: mean |elementary effect| over the full parameter range, "
                 "whiskers: 95 % bootstrap CI), simulated, preliminary", fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=140, metadata={"Software": None})
    plt.close(fig)


def ranking(mo, oat_rows):
    """Overall rank: mean over outputs of mu* normalised by the largest mu* of that output."""
    norm = mo["mu_star"] / (np.max(mo["mu_star"], axis=0) + 1e-12)
    score = np.mean(norm, axis=1)
    order = np.argsort(-score)
    return [(mo["names"][i], float(score[i])) for i in order]


def ke_kt_statement(fixed_rows, mc, cfg, oat_rows):
    nom = nominal(cfg)
    ov = [r["overshoot_pct"] for r in fixed_rows]
    span = max(ov) - min(ov)
    others = []
    for p in ("R", "Jm", "Bm", "eta"):
        vals = [r["overshoot_pct"] for r in oat_rows if r["parameter"] == p and r["level"] in ("-20%", "+20%")]
        others.append((max(vals) - min(vals), p))
    lead = max(others)
    ind = mc["independent Ke, Kt (each +-20 %)"]["overshoot_pct"]
    sh = mc["single shared K in [Kt, Ke] (log-uniform)"]["overshoot_pct"]
    return (f"Forcing Ke = Kt (to Kt, to Ke, or to their geometric mean) moves the Tuned-gain overshoot across a span of "
            f"{span:.1f} percentage points (nominal Ke/Kt = {nom['Ke'] / nom['Kt']:.2f}), versus {lead[0]:.1f} points for the largest "
            f"+-20 % effect among R, Jm, Bm and eta ({lead[1]}). Monte-Carlo overshoot: independent Ke, Kt (+-20 %) mean "
            f"{ind[0]:.1f} % with SD {ind[1]:.1f}; one shared K between Kt and Ke has mean {sh[0]:.1f} % with SD {sh[1]:.1f}. "
            + ("The Ke/Kt inconsistency is therefore a leading driver of the predicted behaviour, not a detail."
               if span > lead[0] else "The Ke/Kt inconsistency matters less than the largest +-20 % parameter effect."))


def main(argv=None):
    cfg = load_config()
    ap = argparse.ArgumentParser(description="Sensitivity analysis of the preliminary twin.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--morris-r", type=int, default=30, help="Morris trajectories")
    ap.add_argument("--mc-n", type=int, default=100, help="Monte-Carlo samples for the Ke/Kt comparison")
    ap.add_argument("--t-end", type=float, default=cfg["simulation"]["run_duration_s"])
    ap.add_argument("--out-dir", default=str(ROOT / "results" / "sensitivity"))
    ap.add_argument("--smoke", action="store_true", help="tiny run (r=3, n=6, no bootstrap) for CI")
    ap.add_argument("--loaded", action="store_true", help="1 kg x 10 cm payload with gravity instead of the bare shaft")
    ap.add_argument("--no-raw", action="store_true", help="skip the per-tick raw log of the OAT runs")
    ap.add_argument("--stamp", action="store_true")
    a = ap.parse_args(argv)
    if a.smoke:
        a.morris_r, a.mc_n = 3, 6
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    if a.loaded:
        _COND["joint"], _COND["name"] = Joint(JointParams(**LOADED_JOINT)), "gravity-loaded arm (1 kg x 10 cm)"
    else:
        _COND["joint"], _COND["name"] = None, "bare shaft"

    print("OAT ...", flush=True)
    oat_rows, blocks = run_oat(cfg, a.t_end, keep_logs=not a.no_raw)
    method_rows = run_method_sets(cfg, a.t_end)
    p = out / "sensitivity_oat.csv"; write_csv(p, oat_rows + method_rows); files.append(p)
    if blocks:
        p = out / "oat_raw.csv"; rawlog.write_raw_csv(p, blocks); files.append(p)
    p = out / "sensitivity_tornado.png"; tornado(p, oat_rows, method_rows); files.append(p)

    print(f"Morris (r={a.morris_r}) ...", flush=True)
    mo = run_morris(cfg, a.morris_r, a.seed, a.t_end, n_boot=50 if a.smoke else 1000)
    rows = []
    for i, n in enumerate(mo["names"]):
        for j, m in enumerate(MORRIS_OUT):
            rows.append(dict(parameter=n, output=m, mu_star=mo["mu_star"][i, j], sigma=mo["sigma"][i, j],
                             mu_star_ci_lo=mo["ci_lo"][i, j], mu_star_ci_hi=mo["ci_hi"][i, j]))
    p = out / "sensitivity_morris.csv"; write_csv(p, rows); files.append(p)
    p = out / "sensitivity_morris_samples.csv"; write_csv(p, mo["samples"]); files.append(p)
    p = out / "sensitivity_morris.png"; morris_plot(p, mo); files.append(p)

    print("Ke/Kt consistency ...", flush=True)
    fixed_rows, mc = run_keKt(cfg, a.mc_n, a.seed, a.t_end)
    p = out / "sensitivity_keKt.csv"
    write_csv(p, fixed_rows + [dict(case=f"MC {k}", **{m: f"mean {v[m][0]:.4g} sd {v[m][1]:.4g}" for m in MORRIS_OUT}) for k, v in mc.items()])
    files.append(p)

    print("RL robustness preview ...", flush=True)
    gains, rl_rows = run_rl_robustness(cfg, a.t_end, max_cases=7 if a.smoke else 0)
    p = out / "sensitivity_rl_robustness.csv"; write_csv(p, rl_rows); files.append(p)

    rank = ranking(mo, oat_rows)
    nom = next(r for r in oat_rows if r["parameter"] == "nominal")
    top3 = [n for n, _ in rank[:3]]
    md = ["# Sensitivity analysis (preliminary twin, simulated)", "",
          f"Tuned gains {TUNED}, 90 deg step, {_COND['name']}, parameter set `{cfg['simulation']['active_electrical_scenario']}`, seed {a.seed}, "
          f"Morris r = {a.morris_r}. Ranges come from `sensitivity_ranges` in the YAML (datasheet +-5 %, calculated +-20 %, "
          "assumed +-50 %, Jm/Bm x/ divided by 3, L 0.1-5 mH, delay 0-3 samples). Nothing here has been validated on hardware.", "",
          "## Overall ranking (Morris, mean of the normalised mu* over overshoot, settling, IAE, peak current, SSE)", "",
          "| rank | parameter | score | what to measure first |", "|---|---|---|---|"]
    for k, (n, s) in enumerate(rank, 1):
        md.append(f"| {k} | {n} | {s:.2f} | {MEASURE_HINT[n]} |")
    md += ["", f"**Recommendation: measure {top3[0]}, {top3[1]} and {top3[2]} on the bench first** "
           "(they dominate the predicted closed-loop behaviour over their plausible ranges).", "",
           "## Ke / Kt consistency", "", ke_kt_statement(fixed_rows, mc, cfg, oat_rows), "",
           "## RL tuner robustness preview", "",
           f"Gains the committed policy picks for this condition's 90 deg case: Kp {gains['RL policy (committed)'][0]:.2f}, "
           f"Ki {gains['RL policy (committed)'][1]:.3f}, Kd {gains['RL policy (committed)'][2]:.3f} (a preview only: pre-validation prototype). "
           "See `sensitivity_rl_robustness.csv` for every perturbed plant.", ""]
    for name in gains:
        sub = [r for r in rl_rows if r["controller"] == name]
        md.append(f"- {name}: overshoot {min(r['overshoot_pct'] for r in sub):.1f}-{max(r['overshoot_pct'] for r in sub):.1f} %, "
                  f"within 2 % of target in {sum(r['within_2pct'] for r in sub)} of {len(sub)} perturbed plants.")
    md += ["", "## One-at-a-time table (Tuned gains)", "", "| parameter | level | " + " | ".join(METRICS) + " |", "|---|---|" + "---|" * len(METRICS)]
    for r in oat_rows + method_rows:
        md.append(f"| {r['parameter']} | {r['level']} | " + " | ".join("never" if (isinstance(r[m], float) and math.isnan(r[m])) else f"{r[m]:.4g}" for m in METRICS) + " |")
    p = out / "sensitivity_table.md"; p.write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n"); files.append(p)
    p = out / "sensitivity_ranking.md"
    p.write_text("\n".join(["# Parameter ranking", ""] + [f"{k}. {n} ({s:.2f}): {MEASURE_HINT[n]}" for k, (n, s) in enumerate(rank, 1)]) + "\n",
                 encoding="utf-8", newline="\n")
    files.append(p)

    try:
        shown_out = pathlib.Path(a.out_dir).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        shown_out = pathlib.Path(a.out_dir).name
    shown = dict(vars(a)); shown["out_dir"] = shown_out
    rawlog.write_manifest(out, script="simulation/sensitivity.py", args=shown, seeds=[a.seed], files=files, stamp=a.stamp,
                          name="sensitivity_manifest.json")
    print("top 3 to measure first:", ", ".join(top3))
    print("wrote", len(files) + 1, "files to", shown_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
