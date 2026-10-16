"""Datasheet consistency of every parameter set, and how much the choice matters for closed-loop behaviour (G3.3).

For each simulatable set (method_a, method_c, and the inactive alternatives method_d, method_d2, method_d3) this
computes what the motor model PREDICTS for the datasheet's headline figures and compares with the datasheet:

    no-load speed 18,000 RPM at 0.8 A | stall current 7.5 A | output stall torque 27.18 kg.cm | output rated torque 12.5 kg.cm

then runs the fixed-PID test sequence (simulation/simulate_pid.py) under each set. Outputs (default
``results/parameter_sets``): datasheet_consistency.csv, closed_loop_by_set.csv, closed_loop_by_set.md,
fig_datasheet_consistency.png, fig_closed_loop_by_set.png, parameter_sets_manifest.json.

PRELIMINARY: every set is calculated from the datasheet, none is validated on hardware. method_b has no R or Kt
and cannot be simulated. Derivation: docs/parameter_derivation.md.

    python simulation/compare_parameter_sets.py
"""

from __future__ import annotations

import argparse
import csv
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

from models.feasibility import feasibility  # noqa: E402
from models.joint import Joint, JointParams  # noqa: E402
from models.units import kgcm_to_Nm, rad_s_to_rpm  # noqa: E402
from simulation import rawlog  # noqa: E402
from simulation.simulate_pid import load_config, run_case, simulatable_sets  # noqa: E402

KGCM = 0.0980665
DATASHEET = {"no_load_rpm": 18000.0, "no_load_current_A": 0.8, "stall_current_A": 7.5, "stall_torque_out_kgcm": 27.18,
             "rated_torque_out_kgcm": 12.5}


def derive_alternative(cfg: dict) -> dict:
    """The algebra behind method_d, d2, d3 (see docs/parameter_derivation.md). Returns the derived numbers."""
    V = cfg["supply"]["V_rated"]
    I0 = cfg["base_motor"]["no_load_current_A"]
    Imax = cfg["base_motor"]["load_current_max_A"]
    N = cfg["gearbox"]["ratio"]
    w0 = cfg["base_motor"]["no_load_speed_rpm"] * 2 * math.pi / 60
    tau_s = cfg["output"]["stall_torque_kgcm"] * KGCM
    tau_r = cfg["output"]["rated_torque_kgcm"] * KGCM
    R = V / Imax                          # 7.5 A taken as the locked-rotor current
    K = (V - R * I0) / w0                 # Ke = Kt = K from V = R*I0 + K*w0 at no load
    Bm = K * I0 / w0                      # the no-load current supplies friction: K*I0 = Bm*w0
    return dict(R=R, K=K, Bm=Bm, omega0=w0,
                stall_torque_motor_Nm=K * Imax, stall_torque_out_eta1_kgcm=K * Imax * N / KGCM,
                eta_for_stall=tau_s / (K * Imax * N),                       # method_d
                current_for_stall_eta08=tau_s / (K * N * cfg["gearbox"]["efficiency"]),     # method_d2 (informational)
                eta_for_rated_at_half_stall=tau_r / (K * (Imax / 2) * N),   # method_d3
                current_of_151_gcm=151 * 9.80665e-5 / K)


def consistency(cfg: dict, name: str) -> dict:
    """Predicted datasheet figures for one parameter set."""
    d = cfg["base_motor"]["derived"][name]
    e = cfg["base_motor"]["estimated"]
    V, N = cfg["supply"]["V_rated"], cfg["gearbox"]["ratio"]
    R, Kt, Ke = d["R_ohm"], d["Kt_Nm_per_A"], d["Ke_V_s_per_rad"]
    Bm = d.get("Bm_Nms_per_rad", e["Bm_Nms_per_rad"])
    eta = d.get("gearbox_efficiency", cfg["gearbox"]["efficiency"])
    w_nl = V * Kt / (R * Bm + Kt * Ke)                      # steady no-load speed including viscous friction
    i_nl = Bm * w_nl / Kt
    Is = V / R
    return dict(set=name, no_load_rpm=rad_s_to_rpm(w_nl), no_load_current_A=i_nl, stall_current_A=Is,
                stall_torque_out_kgcm=Kt * Is * N * eta / KGCM, rated_torque_out_kgcm=Kt * (Is / 2) * N * eta / KGCM,
                Ke_over_Kt=Ke / Kt, eta=eta, Bm=Bm)


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) and not math.isnan(v) else ("" if isinstance(v, float) else v))
                        for k, v in r.items()})


def main(argv=None):
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(ROOT / "results" / "parameter_sets"))
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    sets = simulatable_sets(cfg)

    cons = [consistency(cfg, s) for s in sets]
    p = out / "datasheet_consistency.csv"; write_csv(p, cons); files.append(p)

    # closed loop: the sequence under every set
    cases = [(c["name"], (c["Kp"], c["Ki"], c["Kd"])) for c in cfg["pid_test_sequence"]]
    rows, logs = [], {}
    for s in sets:
        for name, g in cases:
            log, m = run_case(cfg, g, target_deg=90.0, t_end=2.0, dt=cfg["simulation"]["control_loop_dt_s"], params=s,
                              joint=Joint(JointParams()), noise_counts=0.0, seed=0)
            rows.append(dict(set=s, case=name, Kp=g[0], Ki=g[1], Kd=g[2], **{k: m[k] for k in
                        ("rise_s", "overshoot_pct", "settle_s", "sse_deg", "iae_deg_s", "peak_current_A", "energy_J")}))
            logs[(s, name)] = log
    p = out / "closed_loop_by_set.csv"; write_csv(p, rows); files.append(p)

    # gravity-loaded arm (1 kg x 10 cm): the gearbox efficiency now matters, so the d-family separates
    loaded = []
    lj = Joint(JointParams(payload_mass_kg=1.0, arm_length_m=0.10, gravity_on=True))
    for s in sets:
        log, m = run_case(cfg, (15.0, 0.0, 0.3), target_deg=90.0, t_end=2.0, dt=cfg["simulation"]["control_loop_dt_s"], params=s,
                          joint=lj, noise_counts=0.0, seed=0)
        f = feasibility(cfg, 1.0, 0.10, 90.0, gravity=True, scenario=s)
        loaded.append(dict(set=s, overshoot_pct=m["overshoot_pct"], settle_s=m["settle_s"], sse_deg=m["sse_deg"],
                           peak_current_A=m["peak_current_A"], torque_margin=f["margin_path"], status=f["status"]))
    p = out / "closed_loop_loaded_by_set.csv"; write_csv(p, loaded); files.append(p)

    # how much does the choice of set move the closed-loop metrics? (Tuned gains)
    tuned = [r for r in rows if r["case"] == "3 P+D (Tuned)"]
    spread = {k: (min(r[k] for r in tuned), max(r[k] for r in tuned)) for k in ("overshoot_pct", "settle_s", "rise_s", "iae_deg_s")}
    md = ["# Closed-loop behaviour by parameter set (preliminary twin, simulated)", "",
          "Fixed-PID test sequence, 90 deg step, bare shaft, 2 s. Alternative sets (method_d*) are inactive.", "",
          "| set | case | rise [s] | overshoot [%] | settle [s] | SSE [deg] | IAE [deg s] | peak I [A] |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        f = lambda v, nd=3: "never" if (isinstance(v, float) and math.isnan(v)) else f"{v:.{nd}f}"
        md.append(f"| {r['set']} | {r['case']} | {f(r['rise_s'])} | {f(r['overshoot_pct'], 2)} | {f(r['settle_s'])} | "
                  f"{f(r['sse_deg'])} | {f(r['iae_deg_s'], 2)} | {f(r['peak_current_A'], 2)} |")
    md += ["", "## Gravity-loaded arm (1 kg x 10 cm, Tuned gains): the gearbox efficiency matters here", "",
           "| set | overshoot [%] | settle [s] | SSE [deg] | peak I [A] | torque margin | status |", "|---|---|---|---|---|---|---|"]
    for r in loaded:
        md.append(f"| {r['set']} | {r['overshoot_pct']:.2f} | {'never' if math.isnan(r['settle_s']) else f'{r['settle_s']:.3f}'} | "
                  f"{r['sse_deg']:+.3f} | {r['peak_current_A']:.2f} | {r['torque_margin']:.2f} | {r['status']} |")
    md += ["", "## Spread across sets for the Tuned gains (bare shaft)", ""]
    for k, (lo, hi) in spread.items():
        md.append(f"- {k}: {lo:.3g} to {hi:.3g}")
    p = out / "closed_loop_by_set.md"; p.write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n"); files.append(p)

    # figure: predicted / datasheet for each headline quantity
    keys = list(DATASHEET)
    labels = ["no-load speed", "no-load current", "stall current", "stall torque (out)", "rated torque (out)"]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    width = 0.8 / len(cons)
    for i, c in enumerate(cons):
        ax.bar(np.arange(len(keys)) + i * width, [c[k] / DATASHEET[k] for k in keys], width, label=c["set"])
    ax.axhline(1.0, color="k", linewidth=0.8)
    ax.set_xticks(np.arange(len(keys)) + 0.4 - width / 2); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("predicted / datasheet"); ax.set_yscale("log"); ax.grid(alpha=0.3, axis="y"); ax.legend(fontsize=7, ncol=3)
    ax.set_title("Datasheet consistency of each parameter set (simulated, preliminary; 1 = matches the datasheet)", fontsize=9)
    fig.tight_layout()
    p = out / "fig_datasheet_consistency.png"; fig.savefig(p, dpi=150, metadata={"Software": None}); plt.close(fig); files.append(p)

    fig, ax = plt.subplots(figsize=(7, 4.2))
    for i, s in enumerate(sets):
        lg = logs[(s, "3 P+D (Tuned)")]
        ax.plot(lg["t"], np.degrees(lg["theta_out"]), label=s, linewidth=1.4, linestyle=["-", "--", "-.", ":", "-"][i % 5])
    ax.axhline(90, color="gray", linewidth=0.8, linestyle=":")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Output angle [deg]"); ax.grid(alpha=0.3); ax.legend(fontsize=7)
    ax.set_title("Tuned gains under each parameter set (simulated, preliminary)", fontsize=9)
    fig.tight_layout()
    p = out / "fig_closed_loop_by_set.png"; fig.savefig(p, dpi=150, metadata={"Software": None}); plt.close(fig); files.append(p)

    rawlog.write_manifest(out, script="simulation/compare_parameter_sets.py", args={"out_dir": out.name}, seeds=[0], files=files,
                          name="parameter_sets_manifest.json")
    for c in cons:
        print(f"{c['set']:10s} no-load {c['no_load_rpm']:8.0f} RPM  I0 {c['no_load_current_A']:.2f} A  stall {c['stall_current_A']:.2f} A  "
              f"stall-out {c['stall_torque_out_kgcm']:6.2f} kg.cm  rated-out {c['rated_torque_out_kgcm']:6.2f} kg.cm  eta {c['eta']:.3f}")
    print("Tuned-gain spread:", {k: tuple(round(x, 3) for x in v) for k, v in spread.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
