"""Compare PID-selection strategies on paired held-out scenarios (G4.3). PRE-VALIDATION: everything here is simulated on the
unvalidated, datasheet-derived twin; nothing is a hardware result.

Controllers (every one runs in the SAME RL_PID_Env scenario for a given seed: same plant, payload, target, delay, noise):

    tuned          fixed Tuned preset 15/0/0.3
    legacy         fixed legacy default 5/20/0.05
    best_constant  ONE fixed gain triple per regime, chosen on VALIDATION seeds (never on the test seeds): best of random candidates
                   plus Tuned, then a local multiplicative search (``select_best_constant``)
    zn             Ziegler-Nichols gains from the linear model of the nominal plant for that load (clipped to the env bounds)
    bandit         the one-shot context -> gains MLP (autotune_360/autotune_policy_360.json), gains fixed for the episode
    bandit_retune  the same MLP, re-queried whenever the payload or target changes mid-episode (the fair non-RL baseline for ``changes``)
    random_search  ORACLE UPPER BOUND, chosen with hindsight on the test scenario (not deployable): the best of N random log-uniform gain sets,
                   a Ki = 0 grid over Kp x Kd, the Tuned preset, the bandit's gains and the best constant
    ppo            step-wise adaptation policies from rl/train_ppo.py (``--policy-dir``); one per training seed. The reported PPO is the
                   seed with the best mean return on the VALIDATION seeds; seed mean and spread are reported too

Regimes: ``static`` (no mid-episode changes), ``changes`` (payload and target change mid-episode), ``ood`` (plant ranges x1.5, double delay).

Pre-specified statistics (fixed before the run, see ``PRIMARY``): the primary METRIC is the episode return (success rate is descriptive only).
ONE primary comparison, validation-selected PPO minus best_constant in the
``static`` regime on feasible scenarios, reported as the paired MEDIAN difference of the episode return with a 95 % bootstrap CI. Every
other comparison is secondary: paired Wilcoxon signed-rank p-values, Holm-adjusted across the whole secondary family. Scenarios whose
torque-feasibility margin is below 1.0 at any point (including after a payload change) are infeasible and are reported in a separate table.

    python simulation/compare_controllers.py --policy-dir rl/policies/ppo_v2 --out-dir results/controller_comparison
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from environments.rl_pid_env import RL_PID_Env  # noqa: E402
from models.feasibility import feasibility  # noqa: E402
from simulation import rawlog  # noqa: E402

VAL_SEED0 = 40_000           # validation scenarios: used to choose best_constant and the PPO seed
EVAL_SEED0 = 50_000          # test scenarios: never used for any choice (training uses seeds < 20_000)
BANDIT_JSON = ROOT / "autotune_360" / "autotune_policy_360.json"
PRIMARY = dict(regime="static", a="ppo", b="best_constant", statistic="paired median difference of return", subset="feasible")
REGIMES = {
    "static": dict(change_prob={"payload": 0.0, "target": 0.0}, widen=1.0, delay_mult=1),
    "changes": dict(change_prob={"payload": 1.0, "target": 1.0}, widen=1.0, delay_mult=1),
    "ood": dict(change_prob={"payload": 0.0, "target": 0.0}, widen=1.5, delay_mult=2),
}
BASELINES = ["tuned", "legacy", "best_constant", "zn", "bandit", "bandit_retune", "random_search"]


def make_env(regime: str, overrides: dict | None = None, **kw) -> RL_PID_Env:
    """Evaluation env for a regime. ``overrides`` are a policy's training-time ``rl_env`` overrides (e.g. a smaller residual range) EXCEPT the
    reward: every policy is scored with the default reward so returns are comparable."""
    r = REGIMES[regime]
    cfg = None
    if overrides:
        from models.motors import load_base_config

        cfg = load_base_config()
        for k, v in overrides.items():
            if k == "reward":
                continue
            cfg["rl_env"][k].update(v) if isinstance(v, dict) else cfg["rl_env"].__setitem__(k, v)
    env = RL_PID_Env(cfg, change_prob=r["change_prob"], **kw)
    if r["widen"] != 1.0:
        for v in env._ranges.values():
            if v["kind"] in ("uniform", "log"):
                v["lo"], v["hi"] = v["lo"] / r["widen"] if v["lo"] > 0 else v["lo"] * r["widen"], v["hi"] * r["widen"]
    if r["delay_mult"] != 1:
        d = env.e["randomize"]["delay_steps"]
        env.e["randomize"]["delay_steps"] = [d[0], d[1] * r["delay_mult"]]
    return env


# ------------------------------------------------------------------ controllers
class Bandit:
    def __init__(self, path=BANDIT_JSON):
        d = json.loads(pathlib.Path(path).read_text())
        self.d = {k: np.asarray(v, float) for k, v in d.items() if isinstance(v, list)}
        self.lo, self.hi = self.d["lo"], self.d["hi"]
        self.mass_max, self.len_min, self.len_max = d["mass_max"], d["len_min"], d["len_max"]

    def gains(self, ctx, target=None):
        m, L, g, v = ctx["mass"], ctx["length"], float(ctx["gravity"]), ctx["vpct"]
        R = ctx["target"] if target is None else target
        x = np.array([m / self.mass_max, (L - self.len_min) / (self.len_max - self.len_min), g, v / 100.0,
                      g * m * L / (self.mass_max * self.len_max), m * L ** 2 / (self.mass_max * self.len_max ** 2), R / 360.0,
                      g * m * L * math.sin(math.radians(R)) / (self.mass_max * self.len_max)])
        h = np.tanh(np.tanh(x @ self.d["W1"] + self.d["b1"]) @ self.d["W2"] + self.d["b2"])
        z = h @ self.d["W3"] + self.d["b3"]
        u = 1.0 / (1.0 + np.exp(-z))
        return self.lo * (self.hi / self.lo) ** u


def zn_gains(env: RL_PID_Env):
    from tuning.analytic import ziegler_nichols
    from tuning.linear import LinearPlant

    c = env.ctx
    plant = LinearPlant.from_cfg(env.cfg, payload_kg=c["mass"], arm_length_m=c["length"], gravity=c["gravity"], target_deg=c["target"])
    return np.array(ziegler_nichols(plant), float)


def _margin(env: RL_PID_Env, mass: float, target: float) -> float:
    c = env.ctx
    m = feasibility(env.cfg, mass, c["length"], target, gravity=c["gravity"], v_pct=c["vpct"])["margin_path"]
    return float("inf") if not math.isfinite(m) else float(m)


def run_episode(env: RL_PID_Env, seed: int, gains=None, policy=None, retune=None) -> dict:
    """One paired episode: the same ``seed`` always yields the same scenario. ``gains`` fixes the gains for the episode (an array, or a
    callable of the env evaluated after the reset), ``policy(obs)`` adapts them every decision, ``retune(env)`` returns new gains when
    the payload or target has changed (used by the re-tuning bandit)."""
    obs, info = env.reset(seed=seed)
    ctx0 = dict(info["context"])
    margin0 = _margin(env, ctx0["mass"], ctx0["target"])
    if callable(gains):
        gains = gains(env)
    if gains is not None:
        env.gains = np.clip(np.asarray(gains, float), [env.lo[0], 0.0, env.lo[2]], env.hi)
        env._apply_gains(env.gains)
    ret, done, last, min_margin = 0.0, False, {}, margin0
    seen = (ctx0["mass"], ctx0["target"])
    while not done:
        if retune is not None and (env.ctx["mass"], env.target_now) != seen:
            seen = (env.ctx["mass"], env.target_now)
            env.gains = np.clip(np.asarray(retune(env), float), [env.lo[0], 0.0, env.lo[2]], env.hi)
            env._apply_gains(env.gains)
        a = np.zeros(3, np.float32) if policy is None else policy(obs)
        obs, r, term, trunc, last = env.step(a)
        min_margin = min(min_margin, _margin(env, env.ctx["mass"], env.target_now))
        ret += r
        done = term or trunc
    m = last.get("episode_metrics", {})
    th = np.degrees(np.array(env.theta_log))
    final_err = abs(env.target_now - th[-1]) / max(env.target_now, 1e-9) if len(th) and np.isfinite(th[-1]) else float("inf")
    diverged = bool(term)
    ok = (not diverged) and final_err < 0.02 and m.get("overshoot_pct", 100.0) <= 10.0
    at_bound = bool(env.gains[0] >= 0.99 * env.hi[0] or env.gains[1] >= 0.99 * env.hi[1] or env.gains[2] >= 0.99 * env.hi[2] or env.gains[0] <= 1.01 * env.lo[0] or env.gains[2] <= 1.01 * env.lo[2])
    return dict(ret=float(ret), iae=float(m.get("iae_deg_s", np.nan)), overshoot=float(m.get("overshoot_pct", np.nan)),
                settle=float(m.get("settle_s", np.nan)), peak_current=float(m.get("peak_current_A", np.nan)), final_err=float(final_err),
                diverged=diverged, success=bool(ok), gains=env.gains.copy(), ctx=ctx0, margin=float(min_margin), at_bound=at_bound)


def regime_of(ctx: dict) -> str:
    if ctx["mass"] < 0.02:
        return "no payload"
    if not ctx["gravity"]:
        return "payload, no gravity"
    return "payload + gravity"


def select_best_constant(regime: str, n_val: int, n_cand: int, rounds: int, seed: int = 4321):
    """The best single gain triple for a regime, chosen on validation scenarios only: random log-uniform candidates plus Tuned, then a
    local multiplicative coordinate search around the best (steps x1.25 / x0.8; Ki restarts from its seed value or 0)."""
    env = make_env(regime)
    vseeds = [VAL_SEED0 + i for i in range(n_val)]
    tuned = np.array([env.cfg["pid_presets"]["tuned"][k] for k in ("Kp", "Ki", "Kd")])
    rng = np.random.default_rng(seed)
    cache = {}
    lo = np.array([env.lo[0], 0.0, env.lo[2]])

    def score(g):
        key = tuple(np.round(g, 6))
        if key not in cache:
            cache[key] = float(np.mean([run_episode(env, s, gains=g)["ret"] for s in vseeds]))
        return cache[key]

    cands = [tuned] + list(np.exp(rng.uniform(np.log(env.lo), np.log(env.hi), (n_cand, 3))))
    best = max(cands, key=score)
    for _ in range(rounds):
        improved = False
        for j in range(3):
            for f in (1.25, 0.8):
                g = best.copy()
                g[j] = np.clip(g[j] * f if g[j] > 0 else (env.ki_seed if f > 1 else 0.0), lo[j], env.hi[j])
                if score(g) > score(best):
                    best, improved = g, True
        if not improved:
            break
    return np.asarray(best, float), score(best), len(cache)


# ------------------------------------------------------------------ statistics
def bootstrap_ci(d: np.ndarray, stat=np.mean, n: int = 2000, seed: int = 0):
    d = np.asarray(d, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), (n, len(d)))
    vals = stat(d[idx], axis=1)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def wilcoxon_p(d: np.ndarray) -> float:
    """Two-sided paired Wilcoxon signed-rank p-value, normal approximation with tie correction (no scipy dependency)."""
    d = np.asarray(d, float)
    d = d[np.isfinite(d)]
    d = d[d != 0]
    n = len(d)
    if n < 10:
        return float("nan")
    order = np.argsort(np.abs(d))
    ranks = np.empty(n)
    a = np.abs(d)[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and a[j + 1] == a[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    w = float(ranks[d > 0].sum())
    mean = n * (n + 1) / 4.0
    _, counts = np.unique(a, return_counts=True)
    var = n * (n + 1) * (2 * n + 1) / 24.0 - float(np.sum(counts ** 3 - counts)) / 48.0
    if var <= 0:
        return float("nan")
    z = (w - mean) / math.sqrt(var)
    return float(math.erfc(abs(z) / math.sqrt(2.0)))


def holm(pvals: list) -> list:
    """Holm-Bonferroni adjusted p-values (NaN stays NaN and is not counted)."""
    idx = [i for i, p in enumerate(pvals) if p == p]
    order = sorted(idx, key=lambda i: pvals[i])
    adj, running, m = {}, 0.0, len(order)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return [adj.get(i, float("nan")) for i in range(len(pvals))]


def finite_mean(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean()) if len(x) else float("nan")


# ------------------------------------------------------------------ policies
def load_ppo(policy_dir: pathlib.Path, which: str):
    from stable_baselines3 import PPO, SAC, TD3

    out = {}
    for d in sorted(policy_dir.glob("seed_*")):
        meta = json.loads((d / "meta.json").read_text())
        cls = {"ppo": PPO, "sac": SAC, "td3": TD3}[meta["algo"]]
        f = d / {"best": "best_model.zip", "final": "final_model.zip", "selected": "selected_model.zip"}[which]
        model = cls.load(str(f), device="cpu")
        name = f"{meta['algo']}_s{meta['seed']}"
        out[name] = dict(predict=lambda obs, m=model: m.predict(obs, deterministic=True)[0], n_stack=meta["common"]["env"]["n_stack"],
                         overrides=meta["common"]["env"].get("rl_env_overrides"),
                         action_mode=meta["common"]["env"]["action_mode"], file=f, meta=meta)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Paired comparison of PID strategies (pre-validation).")
    ap.add_argument("--policy-dir", default=None, help="run folder from rl/train_ppo.py (contains seed_*/)")
    ap.add_argument("--which", default="best", choices=["best", "final", "selected"], help="best = EvalCallback best (training-side eval seeds), selected = chosen on validation seeds by rl/select_checkpoints.py")
    ap.add_argument("--n", type=int, default=150, help="held-out test scenarios per regime")
    ap.add_argument("--n-val", type=int, default=40, help="validation scenarios per regime (best_constant and PPO seed selection)")
    ap.add_argument("--const-candidates", type=int, default=48)
    ap.add_argument("--const-rounds", type=int, default=2)
    ap.add_argument("--oracle-candidates", type=int, default=48)
    ap.add_argument("--test-seed0", type=int, default=EVAL_SEED0, help="first test scenario seed (50000 = original set, 60000 = fresh confirmatory set)")
    ap.add_argument("--label", default="pre-specified", choices=["pre-specified", "exploratory", "confirmatory"],
                    help="how to describe the analysis: exploratory when the design was chosen after seeing results on these seeds; confirmatory for fresh seeds")
    ap.add_argument("--regimes", nargs="*", default=list(REGIMES))
    ap.add_argument("--out-dir", default=str(ROOT / "results" / "controller_comparison"))
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bandit = Bandit()
    ppo = load_ppo(pathlib.Path(a.policy_dir), a.which) if a.policy_dir else {}
    seeds = [a.test_seed0 + i for i in range(a.n)]
    vseeds = [VAL_SEED0 + i for i in range(a.n_val)]
    assert not set(seeds) & set(vseeds)
    rows, results, selection = [], {}, {}
    for reg in a.regimes:
        base = make_env(reg)
        tuned = np.array([base.cfg["pid_presets"]["tuned"][k] for k in ("Kp", "Ki", "Kd")])
        legacy = np.array([base.cfg["pid_presets"]["legacy_default"][k] for k in ("Kp", "Ki", "Kd")])
        const, const_val, n_eval = select_best_constant(reg, a.n_val, a.const_candidates, a.const_rounds)
        print(f"  {reg}: best constant {np.round(const, 3)} (validation return {const_val:.3f}, {n_eval} candidates)", flush=True)
        penvs = {n: make_env(reg, p["overrides"], action_mode=p["action_mode"], n_stack=p["n_stack"]) for n, p in ppo.items()}
        val_ret = {n: float(np.mean([run_episode(penvs[n], s, policy=ppo[n]["predict"])["ret"] for s in vseeds])) for n in ppo}
        chosen = max(val_ret, key=val_ret.get) if val_ret else None
        selection[reg] = dict(best_constant=[float(x) for x in const], best_constant_val_return=const_val, ppo_val_return=val_ret, ppo_selected=chosen)
        rng = np.random.default_rng(1234)
        cands = np.exp(rng.uniform(np.log(base.lo), np.log(base.hi), (a.oracle_candidates, 3)))
        grid = np.array([[kp, 0.0, kd] for kp in (5.0, 10.0, 20.0, 35.0, 50.0) for kd in (0.3, 0.7, 1.3, 2.0)])    # Ki = 0 grid
        cands = np.vstack([cands, grid])
        res = {k: [] for k in BASELINES + list(ppo)}
        for i, s in enumerate(seeds):
            res["tuned"].append(run_episode(base, s, gains=tuned))
            res["legacy"].append(run_episode(base, s, gains=legacy))
            res["best_constant"].append(run_episode(base, s, gains=const))
            res["zn"].append(run_episode(base, s, gains=zn_gains))
            res["bandit"].append(run_episode(base, s, gains=lambda e: bandit.gains(e.ctx)))
            res["bandit_retune"].append(run_episode(base, s, gains=lambda e: bandit.gains(e.ctx),
                                                    retune=lambda e: bandit.gains(e.ctx, target=e.target_now)))
            best = None
            for c in np.vstack([cands, tuned, bandit.gains(base.ctx), const]):             # base.ctx: this seed's context from the runs above
                r = run_episode(base, s, gains=c)
                if best is None or r["ret"] > best["ret"]:
                    best = r
            res["random_search"].append(best)
            for n in ppo:
                res[n].append(run_episode(penvs[n], s, policy=ppo[n]["predict"]))
            if (i + 1) % 25 == 0:
                print(f"  {reg}: {i + 1}/{a.n}", flush=True)
        if chosen:
            res["ppo"] = res[chosen]
        results[reg] = res
        for name, lst in res.items():
            for s, r in zip(seeds, lst):
                rows.append(dict(regime=reg, controller=name, seed=s, context=regime_of(r["ctx"]), target=round(r["ctx"]["target"], 2),
                                 mass=round(r["ctx"]["mass"], 3), margin=min(r["margin"], 99.0), ret=r["ret"], iae=r["iae"],
                                 overshoot=r["overshoot"], settle=r["settle"], peak_current=r["peak_current"], final_err=r["final_err"],
                                 diverged=int(r["diverged"]), success=int(r["success"]), at_bound=int(r["at_bound"]),
                                 Kp=r["gains"][0], Ki=r["gains"][1], Kd=r["gains"][2]))
    with open(out / "per_episode.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})
    (out / "selection.json").write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    md = report(results, seeds, ppo, selection, a)
    (out / "summary.md").write_text(md, encoding="utf-8", newline="\n")
    extra = {"selection": selection, "primary_comparison": PRIMARY}
    if ppo:
        import gymnasium
        import stable_baselines3
        import torch
        extra["rl_software"] = {"torch": torch.__version__, "stable_baselines3": stable_baselines3.__version__, "gymnasium": gymnasium.__version__}
        extra["policy_sha256"] = {f"{n}/{p['file'].name}": rawlog.sha256_file(p["file"]) for n, p in ppo.items()}
        extra["policy_training_software"] = {n: p["meta"].get("software", {}) for n, p in ppo.items()}
    rawlog.write_manifest(out, script="simulation/compare_controllers.py",
                          args=dict(n=a.n, n_val=a.n_val, which=a.which, oracle_candidates=a.oracle_candidates, const_candidates=a.const_candidates,
                                    regimes=a.regimes, policy_dir=pathlib.Path(a.policy_dir).name if a.policy_dir else None),
                          seeds=[vseeds[0], vseeds[-1], seeds[0], seeds[-1]],
                          files=[out / "per_episode.csv", out / "summary.md", out / "selection.json"], extra=extra, name="comparison_manifest.json")
    print(md.encode("ascii", "replace").decode())
    return 0


def report(results, seeds, ppo, selection, a) -> str:
    L = ["# Controller comparison (PRE-VALIDATION, simulated on the unvalidated twin)", "",
         f"{len(seeds)} held-out paired TEST scenarios per regime (seeds {seeds[0]}..{seeds[-1]}); {a.n_val} VALIDATION scenarios "
         f"(seeds {VAL_SEED0}..{VAL_SEED0 + a.n_val - 1}) were used to choose `best_constant` and the reported PPO seed; neither set was used in training. "
         "Every controller sees the same plant, payload, target, delay and noise for a given seed. `return` is the environment reward (higher is better).",
         f"`random_search` is an ORACLE (best of {a.oracle_candidates} random sets + a 20-point Ki = 0 grid + Tuned + bandit + best_constant per scenario, chosen with "
         "hindsight): an upper bound for any adaptive tuner of this kind, not a deployable controller. Primary metric: episode return (success rate is descriptive).", "",
         f"**Analysis status: {a.label}.** " + {"pre-specified": "", "exploratory": "The policy design under test was chosen after seeing results on an earlier test set that overlaps these seeds, so this set is exploratory, not confirmatory. ",
                                                "confirmatory": "These seeds were not used to train, select or tune anything; they confirm (or not) a design fixed earlier. Nothing may be re-tuned on them. "}[a.label] +
         "One primary comparison: validation-selected PPO minus `best_constant`, `static` regime, feasible scenarios, "
         "paired median difference of return with a 95 % bootstrap CI. All other comparisons are secondary: paired Wilcoxon p-values, Holm-adjusted across "
         "the whole secondary family (feasible scenarios, all regimes). Infeasible scenarios (torque margin < 1.0 at any point, including after a payload "
         "change) are reported separately.", ""]
    tables = {}
    for reg, res in results.items():
        feas = np.array([r["margin"] >= 1.0 for r in res["tuned"]])
        ref = np.array([r["ret"] for r in res["best_constant"]])[feas]
        names = list(dict.fromkeys(BASELINES + (["ppo"] if "ppo" in res else []) + list(ppo)))
        tab = []
        for name in names:
            lst = [r for r, f in zip(res[name], feas) if f]
            r = np.array([x["ret"] for x in lst])
            d = r - ref
            lo, hi = bootstrap_ci(d, np.median)
            tab.append(dict(name=name, lst=lst, r=r, d=d, lo=lo, hi=hi, p=wilcoxon_p(d) if name != "best_constant" else float("nan")))
        tables[reg] = (feas, ref, names, tab)
    secondary = [(reg, t) for reg, (_, _, _, tab) in tables.items() for t in tab
                 if t["name"] != "best_constant" and not (reg == PRIMARY["regime"] and t["name"] == "ppo")]
    adj = holm([t["p"] for _, t in secondary])
    adj_map = {(reg, t["name"]): p for (reg, t), p in zip(secondary, adj)}
    primary = None
    for reg, res in results.items():
        feas, ref, names, tab = tables[reg]
        sel = selection[reg]
        L += [f"## Regime `{reg}`", "", f"Best constant gains (chosen on validation): Kp {sel['best_constant'][0]:.2f}, Ki {sel['best_constant'][1]:.2f}, "
              f"Kd {sel['best_constant'][2]:.3f} (validation return {sel['best_constant_val_return']:.3f})."]
        if sel["ppo_selected"]:
            L.append("PPO seeds, validation mean return: " + ", ".join(f"{n} {v:.3f}" for n, v in sel["ppo_val_return"].items())
                     + f". Selected on validation: `{sel['ppo_selected']}`.")
        nf = int(feas.sum())
        L += ["", f"Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload "
              f"change); the headline tables use the {nf} feasible scenarios of {len(feas)}, the {len(feas) - nf} infeasible ones are tabulated separately below."]
        if reg == "changes":
            L += ["", "Note: in this regime the target and payload change mid-episode, so overshoot, settling and success refer to the final target only; the return is the headline."]
        L += ["", f"Feasible scenarios: {nf} of {len(feas)}; infeasible: {len(feas) - nf}.", "", "### Feasible scenarios (headline)", "",
              "| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for t in tab:
            name, lst, r = t["name"], t["lst"], t["r"]
            tag = " **(primary)**" if (reg == PRIMARY["regime"] and name == "ppo") else ""
            L.append(f"| {name}{tag} | {r.mean():.3f} ± {r.std():.3f} | {np.median(r):.3f} | {np.median(t['d']):+.3f} [{t['lo']:+.3f}, {t['hi']:+.3f}] | {t['p']:.3g} | "
                     f"{adj_map.get((reg, name), float('nan')):.3g} | {finite_mean([x['iae'] for x in lst]):.1f} | {finite_mean([x['overshoot'] for x in lst]):.1f} | "
                     f"{finite_mean([x['settle'] for x in lst]):.3f} | {100 * np.mean([x['success'] for x in lst]):.0f} % | "
                     f"{100 * np.mean([x['at_bound'] for x in lst]):.0f} % | {100 * np.mean([x['diverged'] for x in lst]):.0f} % |")
            if reg == PRIMARY["regime"] and name == "ppo":
                primary = (float(np.median(t["d"])), t["lo"], t["hi"], t["p"], sel["ppo_selected"], len(r))
        orc = np.array([r["ret"] for r, f in zip(res["random_search"], feas) if f])
        L += ["", f"Oracle headroom over best_constant (feasible): mean return {orc.mean() - ref.mean():+.3f} ({100 * (orc.mean() - ref.mean()) / abs(ref.mean()):.1f} % of |best_constant return|); "
              "this is the ceiling for any adaptive tuner on this scenario set."]
        if "ppo" in res:
            def cap(n):
                rr = np.array([x["ret"] for x, f in zip(res[n], feas) if f])
                return 100 * (rr.mean() - ref.mean()) / (orc.mean() - ref.mean())
            L += ["Headroom captured (mean PPO gain over best_constant divided by the oracle headroom): selected " + f"{cap('ppo'):.0f} %" + "; per seed " + ", ".join(f"{n} {cap(n):.0f} %" for n in ppo) + ". Success rate is descriptive only; return is the headline."]
        bd = next(t for t in tab if t["name"] == "bandit")
        L += [f"Bandit vs best_constant (return, median difference): {np.median(bd['d']):+.3f} [{bd['lo']:+.3f}, {bd['hi']:+.3f}].", ""]
        if ppo:
            per_seed = [(n, float(np.mean([x["ret"] for x, f in zip(res[n], feas) if f]))) for n in ppo]
            vals = np.array([v for _, v in per_seed])
            L += ["PPO across training seeds (feasible test scenarios, mean return): " + ", ".join(f"{n} {v:.3f}" for n, v in per_seed)
                  + f". Seed mean {vals.mean():.3f}, std {vals.std():.3f}, range [{vals.min():.3f}, {vals.max():.3f}]; best constant {np.mean(ref):.3f}.", ""]
        if (~feas).any():
            L += ["### Infeasible scenarios (reported separately)", "", "| controller | n | return mean | median |", "|---|---|---|---|"]
            for name in names:
                rr = np.array([x["ret"] for x, f in zip(res[name], feas) if not f])
                L.append(f"| {name} | {len(rr)} | {rr.mean():.3f} | {np.median(rr):.3f} |")
            bad = [(seeds[i], res["tuned"][i]["margin"]) for i in range(len(feas)) if not feas[i]]
            L += ["", "Infeasible seeds (min margin): " + ", ".join(f"{s} ({m:.2f})" for s, m in bad[:12]) + ("..." if len(bad) > 12 else ""), ""]
    L += ["## Verdict", ""]
    if primary:
        m, lo, hi, p, n, k = primary
        word = "BETTER than" if lo > 0 else ("WORSE than" if hi < 0 else "NOT distinguishable from")
        L += [f"**Primary** (static, feasible, n={k}): validation-selected PPO (`{n}`) is {word} the best constant gains: paired median difference of "
              f"return {m:+.3f}, 95 % CI [{lo:+.3f}, {hi:+.3f}] (Wilcoxon p = {p:.3g}, single primary test, unadjusted; analysis status: {a.label}).", ""]
    else:
        L += ["No primary comparison was computed (no RL policy supplied, or the `static` regime was not run).", ""]
    sig = [(reg, t["name"], p) for (reg, t), p in zip(secondary, adj) if p == p and p < 0.05]
    L += ["Secondary comparisons against best_constant with Holm-adjusted p < 0.05: " + (", ".join(f"{r_}/{n} (p={p:.2g})" for r_, n, p in sig) or "none")
          + ". The sign of the median difference in the tables gives the direction.", "",
          "Everything above is simulated on the preliminary twin and has not been validated on hardware."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
