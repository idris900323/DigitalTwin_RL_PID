"""Post-hoc sensitivity analysis: is the residual-PPO advantage just a better constant? (PRE-VALIDATION, simulation only.)

The learned policies end at nearly constant gains (see paper/gain_spread), so the advantage over ``best_constant`` could come from the coarse constant search
rather than from adaptation. This script adds two constant baselines, both derived on VALIDATION seeds only (never on the test seeds), and evaluates them
once on the test seeds of the policy under study:

    best_constant_ext   a much larger validation search: random candidates plus the original best constant and Tuned, then Nelder-Mead in log-gain space
    ppo_distilled       the median final gains of the validation-selected PPO policy on the VALIDATION scenarios (the policy 'frozen' into one constant)

This analysis was added AFTER the confirmatory runs, in response to the gain-spread observation; it is labelled post hoc in the paper.

    python simulation/constant_sensitivity.py --policy-dir rl/policies/ppo_v3 --which selected --test-seed0 60000 --out-dir results/constant_sensitivity_v3
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

    def f(x):                                              # Nelder-Mead on (log Kp, Ki, log Kd); Ki is clipped at 0
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy-dir", required=True)
    ap.add_argument("--which", default="selected")
    ap.add_argument("--test-seed0", type=int, required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--n-val", type=int, default=40)
    ap.add_argument("--random-candidates", type=int, default=150)
    ap.add_argument("--nm-evals", type=int, default=100)
    ap.add_argument("--const-candidates", type=int, default=48, help="must equal the comparison's setting so best_constant is reproduced")
    ap.add_argument("--const-rounds", type=int, default=2)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--constants-cache", default=str(ROOT / "results" / "constant_sensitivity" / "ext_constants.json"))
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cache_path = pathlib.Path(a.constants_cache)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    ppo = load_ppo(pathlib.Path(a.policy_dir), a.which)
    seeds = [a.test_seed0 + i for i in range(a.n)]
    rows, consts = [], {}
    for reg in REGIMES:
        base, bval, _ = select_best_constant(reg, a.n_val, a.const_candidates, a.const_rounds)      # identical to the comparison's best_constant
        if reg not in cache:
            g, v, n = ext_constant(reg, a.n_val, a.random_candidates, a.nm_evals, base)
            cache[reg] = dict(gains=[float(x) for x in g], val_return=v, evaluations=n, original_val_return=bval)
            cache_path.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8", newline="\n")
        ext = np.array(cache[reg]["gains"])
        val = {n: float(np.mean([run_episode(make_env(reg, p["overrides"], action_mode=p["action_mode"], n_stack=p["n_stack"]), s, policy=p["predict"])["ret"]
                                 for s in [VAL_SEED0 + i for i in range(a.n_val)]])) for n, p in ppo.items()}
        chosen = max(val, key=val.get)
        dist = distilled(reg, ppo[chosen], a.n_val)
        consts[reg] = dict(best_constant=[float(x) for x in base], best_constant_ext=[float(x) for x in ext], ppo_distilled=[float(x) for x in dist],
                           ppo_selected=chosen, val_return_original=bval, val_return_ext=cache[reg]["val_return"])
        print(reg, {k: np.round(v, 3).tolist() if isinstance(v, list) else v for k, v in consts[reg].items()}, flush=True)
        env = make_env(reg)
        penv = make_env(reg, ppo[chosen]["overrides"], action_mode=ppo[chosen]["action_mode"], n_stack=ppo[chosen]["n_stack"])
        for s in seeds:
            for name, g in (("best_constant", base), ("best_constant_ext", ext), ("ppo_distilled", dist)):
                r = run_episode(env, s, gains=g)
                rows.append(dict(regime=reg, controller=name, seed=s, margin=min(r["margin"], 99.0), ret=r["ret"], success=int(r["success"]),
                                 Kp=r["gains"][0], Ki=r["gains"][1], Kd=r["gains"][2]))
            r = run_episode(penv, s, policy=ppo[chosen]["predict"])
            rows.append(dict(regime=reg, controller="ppo", seed=s, margin=min(r["margin"], 99.0), ret=r["ret"], success=int(r["success"]),
                             Kp=r["gains"][0], Ki=r["gains"][1], Kd=r["gains"][2]))
        print(f"  {reg}: evaluated {len(seeds)} test scenarios", flush=True)
    with open(out / "per_episode.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})
    (out / "constants.json").write_text(json.dumps(consts, indent=2) + "\n", encoding="utf-8", newline="\n")
    md = ["# Constant-gain sensitivity (POST HOC, simulation only)", "",
          "Added after the confirmatory runs because the learned policies end at nearly constant gains. Both new constants are derived on validation seeds "
          f"({VAL_SEED0}..{VAL_SEED0 + a.n_val - 1}); the test seeds ({seeds[0]}..{seeds[-1]}) are used once for evaluation. Paired differences are to the ORIGINAL best constant "
          "(feasible scenarios; median [95 % bootstrap CI] / mean / Wilcoxon p, unadjusted).", ""]
    for reg in REGIMES:
        by = {}
        for r in rows:
            if r["regime"] == reg:
                by.setdefault(r["controller"], []).append(r)
        feas = np.array([float(r["margin"]) >= 1.0 for r in by["best_constant"]])
        ref = np.array([r["ret"] for r in by["best_constant"]])[feas]
        md += [f"## {reg}", "", f"Constants: original {np.round(consts[reg]['best_constant'], 2).tolist()} (val {consts[reg]['val_return_original']:.3f}), extended "
               f"{np.round(consts[reg]['best_constant_ext'], 2).tolist()} (val {consts[reg]['val_return_ext']:.3f}), distilled from `{consts[reg]['ppo_selected']}` "
               f"{np.round(consts[reg]['ppo_distilled'], 2).tolist()}.", "", "| controller | return mean | Δmedian [95 % CI] | Δmean | p |", "|---|---|---|---|---|"]
        for name in ("best_constant", "best_constant_ext", "ppo_distilled", "ppo"):
            rr = np.array([r["ret"] for r in by[name]])[feas]
            d = rr - ref
            lo, hi = bootstrap_ci(d, np.median)
            md.append(f"| {name} | {rr.mean():.3f} | {np.median(d):+.3f} [{lo:+.3f}, {hi:+.3f}] | {d.mean():+.3f} | "
                      f"{'--' if name == 'best_constant' else format(wilcoxon_p(d), '.3g')} |")
        md.append("")
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    rawlog.write_manifest(out, script="simulation/constant_sensitivity.py", args=dict(policy_dir=pathlib.Path(a.policy_dir).name, which=a.which, test_seed0=a.test_seed0,
                          n=a.n, n_val=a.n_val, random_candidates=a.random_candidates, nm_evals=a.nm_evals), seeds=[VAL_SEED0, seeds[0], seeds[-1]],
                          files=[out / "per_episode.csv", out / "summary.md", out / "constants.json"], name="sensitivity_manifest.json")
    print("\n".join(md).encode("ascii", "replace").decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
