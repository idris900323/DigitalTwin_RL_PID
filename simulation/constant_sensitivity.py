"""Post-hoc sensitivity analysis: is the residual-PPO advantage just a better constant, or scenario-aware non-learned gains? (PRE-VALIDATION, simulation only.)

The learned policies end at nearly constant gains, so the advantage over ``best_constant`` could come from the coarse constant search rather than from
adaptation. This analysis adds stronger NON-LEARNED or distilled baselines, every one derived on VALIDATION seeds (40000-40039) only and then evaluated once on a
fresh test seed range (default 80000+, never used before):

    best_constant_ext     a much larger validation search (random candidates + Nelder-Mead in log-gain space); cached in ext_constants.json
    ppo_distilled         the median final gains of the validation-selected policy on the validation scenarios of the SAME regime
    ppo_distilled_pooled  the same median pooled over the validation scenarios of all three regimes (one constant; used for v4)
    scenario_fit          non-learned scenario-conditioned gains: log Kp and log Kd are linear in (mass fraction, gravity-torque fraction, inertia fraction),
                          Ki = 0, fitted on validation scenarios by Nelder-Mead; re-evaluated when the payload changes (like the re-tuned bandit)

It was added AFTER the confirmatory runs, in response to the near-constant-gain observation, and is labelled post hoc everywhere it is reported.

    python simulation/constant_sensitivity.py --policy-dir rl/policies/ppo_v3 --test-seed0 80000 --out-dir results/constant_sensitivity_v3 [--regimes static]
    python simulation/constant_sensitivity.py --summarize --out-dir results/constant_sensitivity_v3        # after all regimes ran
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from simulation import rawlog  # noqa: E402
from simulation.compare_controllers import (  # noqa: E402
    VAL_SEED0,
    bootstrap_ci,
    load_ppo,
    make_env,
    run_episode,
    select_best_constant,
    wilcoxon_p,
)

REGIMES = ["static", "changes", "ood"]
CACHE_DIR = ROOT / "results" / "constant_sensitivity"


# ------------------------------------------------------------------ constants
def ext_constant(regime: str, n_val: int, n_rand: int, nm_evals: int, start: np.ndarray, seed: int = 99):
    from scipy.optimize import minimize

    env = make_env(regime)
    vseeds = [VAL_SEED0 + i for i in range(n_val)]
    lo = np.array([env.lo[0], 0.0, env.lo[2]])
    cache = {}

    def score(g):
        g = np.clip(np.asarray(g, float), lo, env.hi)
        key = tuple(np.round(g, 5))
        if key not in cache:
            cache[key] = float(np.mean([run_episode(env, s, gains=g)["ret"] for s in vseeds]))
        return cache[key]

    rng = np.random.default_rng(seed)
    tuned = np.array([env.cfg["pid_presets"]["tuned"][k] for k in ("Kp", "Ki", "Kd")])
    cands = [start, tuned] + [np.array([np.exp(rng.uniform(np.log(5), np.log(env.hi[0]))), 0.0, np.exp(rng.uniform(np.log(0.3), np.log(env.hi[2])))])
                              for _ in range(n_rand)]
    best = max(cands, key=score)

    def f(x):
        return -score([np.exp(x[0]), x[1], np.exp(x[2])])

    x0 = np.array([np.log(best[0]), best[1], np.log(best[2])])
    res = minimize(f, x0, method="Nelder-Mead", options=dict(maxfev=nm_evals, xatol=1e-3, fatol=1e-4, initial_simplex=np.array(
        [x0, x0 + [0.15, 0, 0], x0 + [0, 0.5, 0], x0 + [0, 0, 0.15]])))
    g = np.clip([np.exp(res.x[0]), res.x[1], np.exp(res.x[2])], lo, env.hi)
    if score(g) < score(best):
        g = best
    return np.asarray(g, float), score(g), len(cache)


def distilled(regime: str, policy: dict, n_val: int) -> np.ndarray:
    env = make_env(regime, policy["overrides"], action_mode=policy["action_mode"], n_stack=policy["n_stack"])
    gs = [run_episode(env, VAL_SEED0 + i, policy=policy["predict"])["gains"] for i in range(n_val)]
    return np.median(np.array(gs), axis=0)


# ------------------------------------------------------------------ scenario-conditioned non-learned gains
def scen_features(env, ctx: dict) -> np.ndarray:
    p = env.e["payload"]
    m, L, g = ctx["mass"], ctx["length"], float(ctx["gravity"])
    return np.array([m / p["mass_max_kg"], g * m * L / (p["mass_max_kg"] * p["length_max_m"]), m * L ** 2 / (p["mass_max_kg"] * p["length_max_m"] ** 2)])


def scen_gains(theta: np.ndarray, env, ctx: dict) -> np.ndarray:
    x = scen_features(env, ctx)
    return np.array([np.exp(theta[0] + theta[1:4] @ x), 0.0, np.exp(theta[4] + theta[5:8] @ x)])


def fit_scenario(regime: str, n_val: int, start: np.ndarray, nm_evals: int):
    """Fit the 8 parameters by Nelder-Mead on the mean validation return."""
    from scipy.optimize import minimize

    env = make_env(regime)
    vseeds = [VAL_SEED0 + i for i in range(n_val)]
    cache = {}

    def f(theta):
        key = tuple(np.round(theta, 5))
        if key not in cache:
            fn = lambda e: scen_gains(theta, e, e.ctx)  # noqa: E731
            cache[key] = -float(np.mean([run_episode(env, s, gains=fn, retune=fn)["ret"] for s in vseeds]))
        return cache[key]

    t0 = np.array([np.log(start[0]), 0, 0, 0, np.log(start[2]), 0, 0, 0], float)
    simplex = np.vstack([t0] + [t0 + np.eye(8)[i] * (0.2 if i in (0, 4) else 0.4) for i in range(8)])
    res = minimize(f, t0, method="Nelder-Mead", options=dict(maxfev=nm_evals, xatol=1e-3, fatol=1e-4, initial_simplex=simplex))
    return res.x, -float(res.fun), len(cache)


# ------------------------------------------------------------------ run
def run_regimes(a) -> int:
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ppo = load_ppo(pathlib.Path(a.policy_dir), a.which)
    seeds = [a.test_seed0 + i for i in range(a.n)]
    cache_dir = pathlib.Path(a.cache_dir)
    ext_path = cache_dir / "ext_constants.json"
    ext_cache = json.loads(ext_path.read_text()) if ext_path.exists() else {}
    pooled = None
    if a.pooled:
        allg = []
        for reg in REGIMES:
            val = {n: float(np.mean([run_episode(make_env(reg, p["overrides"], action_mode=p["action_mode"], n_stack=p["n_stack"]), s, policy=p["predict"])["ret"]
                                     for s in [VAL_SEED0 + i for i in range(a.n_val)]])) for n, p in ppo.items()}
            ch = max(val, key=val.get)
            envp = make_env(reg, ppo[ch]["overrides"], action_mode=ppo[ch]["action_mode"], n_stack=ppo[ch]["n_stack"])
            allg += [run_episode(envp, VAL_SEED0 + i, policy=ppo[ch]["predict"])["gains"] for i in range(a.n_val)]
        pooled = np.median(np.array(allg), axis=0)
        print("pooled distilled constant", np.round(pooled, 3).tolist(), flush=True)
    for reg in a.regimes:
        base, bval, _ = select_best_constant(reg, a.n_val, a.const_candidates, a.const_rounds)        # identical to the comparison's best_constant
        if reg not in ext_cache:
            g, v, n = ext_constant(reg, a.n_val, a.random_candidates, a.nm_evals, base)
            ext_cache[reg] = dict(gains=[float(x) for x in g], val_return=v, evaluations=n, original_val_return=bval)
            cache_dir.mkdir(parents=True, exist_ok=True)
            ext_path.write_text(json.dumps(ext_cache, indent=2) + "\n", encoding="utf-8", newline="\n")
        ext = np.array(ext_cache[reg]["gains"])
        fit_path = cache_dir / f"scenario_fit_{reg}.json"
        if fit_path.exists():
            fit = json.loads(fit_path.read_text())
        else:
            theta, v, n = fit_scenario(reg, a.n_val, ext, a.fit_evals)
            fit = dict(theta=[float(x) for x in theta], val_return=v, evaluations=n, features="mass/2, g*m*L/(2*0.15), m*L^2/(2*0.15^2)")
            fit_path.write_text(json.dumps(fit, indent=2) + "\n", encoding="utf-8", newline="\n")
        theta = np.array(fit["theta"])
        val = {n: float(np.mean([run_episode(make_env(reg, p["overrides"], action_mode=p["action_mode"], n_stack=p["n_stack"]), s, policy=p["predict"])["ret"]
                                 for s in [VAL_SEED0 + i for i in range(a.n_val)]])) for n, p in ppo.items()}
        chosen = max(val, key=val.get)
        dist = distilled(reg, ppo[chosen], a.n_val)
        consts = dict(best_constant=[float(x) for x in base], best_constant_ext=[float(x) for x in ext], ppo_distilled=[float(x) for x in dist],
                      ppo_distilled_pooled=None if pooled is None else [float(x) for x in pooled], scenario_fit_theta=fit["theta"], ppo_selected=chosen,
                      val_return_original=bval, val_return_ext=ext_cache[reg]["val_return"], val_return_scenario_fit=fit["val_return"], val_return_ppo=val[chosen])
        print(reg, json.dumps({k: (np.round(v, 3).tolist() if isinstance(v, list) else v) for k, v in consts.items()}), flush=True)
        env = make_env(reg)
        penv = make_env(reg, ppo[chosen]["overrides"], action_mode=ppo[chosen]["action_mode"], n_stack=ppo[chosen]["n_stack"])
        rows = []
        sfn = lambda e: scen_gains(theta, e, e.ctx)  # noqa: E731
        for s in seeds:
            runs = [("best_constant", dict(gains=base)), ("best_constant_ext", dict(gains=ext)), ("ppo_distilled", dict(gains=dist)),
                    ("scenario_fit", dict(gains=sfn, retune=sfn))]
            if pooled is not None:
                runs.append(("ppo_distilled_pooled", dict(gains=pooled)))
            for name, kw in runs:
                r = run_episode(env, s, **kw)
                rows.append(row(reg, name, s, r))
            rows.append(row(reg, "ppo", s, run_episode(penv, s, policy=ppo[chosen]["predict"])))
        write_rows(out / f"per_episode_{reg}.csv", rows)
        (out / f"constants_{reg}.json").write_text(json.dumps(consts, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"  {reg}: evaluated {len(seeds)} test scenarios", flush=True)
    (out / "run_args.json").write_text(json.dumps(dict(policy_dir=pathlib.Path(a.policy_dir).name, which=a.which, test_seed0=a.test_seed0, n=a.n, n_val=a.n_val,
                                                       random_candidates=a.random_candidates, nm_evals=a.nm_evals, fit_evals=a.fit_evals, pooled=a.pooled), indent=1) + "\n",
                                       encoding="utf-8", newline="\n")
    return 0


def row(reg, name, seed, r) -> dict:
    c = r["ctx"]
    return dict(regime=reg, controller=name, seed=seed, margin=min(r["margin"], 99.0), ret=r["ret"], success=int(r["success"]), mass=c["mass"], length=c["length"],
                gravity=int(c["gravity"]), target=c["target"], vpct=c["vpct"], Kp=r["gains"][0], Ki=r["gains"][1], Kd=r["gains"][2])


def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})


def summarize(a) -> int:
    out = pathlib.Path(a.out_dir)
    rows, consts = [], {}
    for reg in REGIMES:
        p = out / f"per_episode_{reg}.csv"
        if not p.exists():
            continue
        rows += list(csv.DictReader(open(p, encoding="utf-8")))
        consts[reg] = json.loads((out / f"constants_{reg}.json").read_text())
    ra = json.loads((out / "run_args.json").read_text())
    with open(out / "per_episode.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    (out / "constants.json").write_text(json.dumps(consts, indent=2) + "\n", encoding="utf-8", newline="\n")
    md = ["# Constant-gain and scenario-conditioned sensitivity (POST HOC, simulation only)", "",
          "Added after the confirmatory runs because the learned policies end at nearly constant gains. Every new baseline is derived on validation seeds "
          f"({VAL_SEED0}..{VAL_SEED0 + ra['n_val'] - 1}); the test seeds ({ra['test_seed0']}..{ra['test_seed0'] + ra['n'] - 1}) are used once for evaluation. "
          "Differences are paired on feasible scenarios: median [95 % bootstrap CI] / mean / IQR / Wilcoxon p (unadjusted).", ""]
    for reg in consts:
        by = {}
        for r in rows:
            if r["regime"] == reg:
                by.setdefault(r["controller"], []).append(r)
        feas = np.array([float(r["margin"]) >= 1.0 for r in by["best_constant"]])
        def ret(n):
            return np.array([float(r["ret"]) for r in by[n]])[feas]
        c = consts[reg]
        md += [f"## {reg} (n feasible = {int(feas.sum())})", "",
               f"Constants: original {np.round(c['best_constant'], 2).tolist()} (val {c['val_return_original']:.3f}); extended {np.round(c['best_constant_ext'], 2).tolist()} "
               f"(val {c['val_return_ext']:.3f}); distilled from `{c['ppo_selected']}` {np.round(c['ppo_distilled'], 2).tolist()}; scenario fit (val {c['val_return_scenario_fit']:.3f}); "
               f"PPO val {c['val_return_ppo']:.3f}.", "",
               "| comparison (A minus B) | A mean return | Δmedian [95 % CI] | Δmean | IQR of Δ | p |", "|---|---|---|---|---|---|"]
        pairs = [("best_constant_ext", "best_constant"), ("ppo_distilled", "best_constant"), ("scenario_fit", "best_constant"), ("ppo", "best_constant"),
                 ("ppo", "best_constant_ext"), ("ppo", "ppo_distilled"), ("ppo", "scenario_fit")]
        if "ppo_distilled_pooled" in by:
            pairs += [("ppo_distilled_pooled", "best_constant"), ("ppo", "ppo_distilled_pooled")]
        for A, B in pairs:
            d = ret(A) - ret(B)
            lo, hi = bootstrap_ci(d, np.median)
            q1, q3 = np.percentile(d, [25, 75])
            md.append(f"| {A} − {B} | {ret(A).mean():.3f} | {np.median(d):+.3f} [{lo:+.3f}, {hi:+.3f}] | {d.mean():+.3f} | [{q1:+.3f}, {q3:+.3f}] | {wilcoxon_p(d):.3g} |")
        md.append("")
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    rawlog.write_manifest(out, script="simulation/constant_sensitivity.py", args=ra, seeds=[VAL_SEED0, ra["test_seed0"]],
                          files=[out / "per_episode.csv", out / "summary.md", out / "constants.json"], name="sensitivity_manifest.json")
    print("\n".join(md).encode("ascii", "replace").decode())
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy-dir")
    ap.add_argument("--which", default="selected")
    ap.add_argument("--test-seed0", type=int, default=80000)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--n-val", type=int, default=40)
    ap.add_argument("--regimes", nargs="*", default=REGIMES)
    ap.add_argument("--random-candidates", type=int, default=150)
    ap.add_argument("--nm-evals", type=int, default=100)
    ap.add_argument("--fit-evals", type=int, default=250)
    ap.add_argument("--const-candidates", type=int, default=48, help="must equal the comparison's setting so best_constant is reproduced")
    ap.add_argument("--const-rounds", type=int, default=2)
    ap.add_argument("--pooled", action="store_true", help="also evaluate the pooled distilled constant (used for v4)")
    ap.add_argument("--cache-dir", default=str(CACHE_DIR), help="where ext_constants.json and scenario_fit_<regime>.json are cached")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    return summarize(a) if a.summarize else run_regimes(a)


if __name__ == "__main__":
    raise SystemExit(main())
