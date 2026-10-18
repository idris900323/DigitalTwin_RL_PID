"""Kd-bound check (POST HOC, simulation only): do the extended-search constants move off the Kd bound when it is raised from 2 to 4?

The extended constants of ``constant_sensitivity.py`` sit at the Kd upper bound of 2 (set in the YAML for encoder-noise reasons). Here the extended-constant search is
repeated with the Kd bound raised to ``--kd-max`` (default 4) for the CONSTANTS ONLY, deriving them on VALIDATION seeds (40000-40039); the learned policy is evaluated in
its own training environment (bound 2) exactly as before. Everything is then evaluated once on a fresh seed range (default 90000-90099).

    python simulation/kd_bound_check.py --policy-dir rl/policies/ppo_v3 --regimes static --out-dir results/kd_bound_check_v3_90k
    python simulation/kd_bound_check.py --summarize --out-dir results/kd_bound_check_v3_90k
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
from simulation.constant_sensitivity import REGIMES, ext_constant, row, write_rows  # noqa: E402

EXT2 = ROOT / "results" / "constant_sensitivity" / "ext_constants.json"          # the bound-2 extended constants (derived earlier on validation seeds)


def run(a) -> int:
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ppo = load_ppo(pathlib.Path(a.policy_dir), a.which)
    ext2 = json.loads(EXT2.read_text())
    seeds = [a.test_seed0 + i for i in range(a.n)]
    ov = {"gain_bounds": {"Kd": [0.005, a.kd_max]}}
    for reg in a.regimes:
        base, bval, _ = select_best_constant(reg, a.n_val, a.const_candidates, a.const_rounds)
        g2 = np.array(ext2[reg]["gains"])
        g4, v4, n4 = ext_constant(reg, a.n_val, a.random_candidates, a.nm_evals, g2, overrides=ov)         # starts from the bound-2 constant, so it cannot be worse on validation
        val = {n: float(np.mean([run_episode(make_env(reg, p["overrides"], action_mode=p["action_mode"], n_stack=p["n_stack"]), s, policy=p["predict"])["ret"]
                                 for s in [VAL_SEED0 + i for i in range(a.n_val)]])) for n, p in ppo.items()}
        chosen = max(val, key=val.get)
        consts = dict(best_constant=[float(x) for x in base], best_constant_ext=[float(x) for x in g2], best_constant_ext_kd4=[float(x) for x in g4],
                      val_return_original=bval, val_return_ext=ext2[reg]["val_return"], val_return_ext_kd4=v4, evaluations_kd4=n4, ppo_selected=chosen, val_return_ppo=val[chosen],
                      kd_max=a.kd_max)
        print(reg, json.dumps({k: (np.round(v, 3).tolist() if isinstance(v, list) else v) for k, v in consts.items()}), flush=True)
        env4 = make_env(reg, ov)
        penv = make_env(reg, ppo[chosen]["overrides"], action_mode=ppo[chosen]["action_mode"], n_stack=ppo[chosen]["n_stack"])
        rows = []
        for s in seeds:
            for name, g in (("best_constant", base), ("best_constant_ext", g2), ("best_constant_ext_kd4", g4)):
                rows.append(row(reg, name, s, run_episode(env4, s, gains=g)))
            rows.append(row(reg, "ppo", s, run_episode(penv, s, policy=ppo[chosen]["predict"])))
        write_rows(out / f"per_episode_{reg}.csv", rows)
        (out / f"constants_{reg}.json").write_text(json.dumps(consts, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"  {reg}: evaluated {len(seeds)} test scenarios", flush=True)
    (out / "run_args.json").write_text(json.dumps(dict(policy_dir=pathlib.Path(a.policy_dir).name, which=a.which, test_seed0=a.test_seed0, n=a.n, n_val=a.n_val,
                                                       random_candidates=a.random_candidates, nm_evals=a.nm_evals, kd_max=a.kd_max), indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


def summarize(a) -> int:
    out = pathlib.Path(a.out_dir)
    rows, consts = [], {}
    for reg in REGIMES:
        p = out / f"per_episode_{reg}.csv"
        if p.exists():
            rows += list(csv.DictReader(open(p, encoding="utf-8")))
            consts[reg] = json.loads((out / f"constants_{reg}.json").read_text())
    ra = json.loads((out / "run_args.json").read_text())
    with open(out / "per_episode.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    (out / "constants.json").write_text(json.dumps(consts, indent=2) + "\n", encoding="utf-8", newline="\n")
    md = [f"# Kd-bound check (POST HOC, simulation only): extended constants with the Kd bound raised from 2 to {ra['kd_max']}", "",
          f"Constants derived on validation seeds ({VAL_SEED0}..{VAL_SEED0 + ra['n_val'] - 1}); evaluated once on fresh seeds {ra['test_seed0']}..{ra['test_seed0'] + ra['n'] - 1} "
          "(feasible scenarios). The policy is evaluated in its own training environment (Kd bound 2). Paired differences A - B: median [95 % CI] / mean / IQR / Wilcoxon p (unadjusted).", ""]
    for reg, c in consts.items():
        by = {}
        for r in rows:
            if r["regime"] == reg:
                by.setdefault(r["controller"], []).append(r)
        feas = np.array([float(r["margin"]) >= 1.0 for r in by["best_constant"]])

        def ret(n, by=by, feas=feas):
            return np.array([float(r["ret"]) for r in by[n]])[feas]
        md += [f"## {reg} (n feasible = {int(feas.sum())})", "",
               f"Extended constant, Kd bound 2: {np.round(c['best_constant_ext'], 2).tolist()} (val {c['val_return_ext']:.3f}); Kd bound {ra['kd_max']}: "
               f"{np.round(c['best_constant_ext_kd4'], 2).tolist()} (val {c['val_return_ext_kd4']:.3f}).", "",
               "| A - B | A mean return | Δmedian [95 % CI] | Δmean | IQR of Δ | p |", "|---|---|---|---|---|---|"]
        for A, B in (("best_constant_ext", "best_constant"), ("best_constant_ext_kd4", "best_constant"), ("best_constant_ext_kd4", "best_constant_ext"),
                     ("ppo", "best_constant"), ("ppo", "best_constant_ext"), ("ppo", "best_constant_ext_kd4")):
            d = ret(A) - ret(B)
            lo, hi = bootstrap_ci(d, np.median)
            q1, q3 = np.percentile(d, [25, 75])
            md.append(f"| {A} − {B} | {ret(A).mean():.3f} | {np.median(d):+.3f} [{lo:+.3f}, {hi:+.3f}] | {d.mean():+.3f} | [{q1:+.3f}, {q3:+.3f}] | {wilcoxon_p(d):.3g} |")
        md.append("")
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    rawlog.write_manifest(out, script="simulation/kd_bound_check.py", args=ra, seeds=[VAL_SEED0, ra["test_seed0"]],
                          files=[out / "per_episode.csv", out / "summary.md", out / "constants.json"], name="sensitivity_manifest.json")
    print("\n".join(md).encode("ascii", "replace").decode())
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy-dir")
    ap.add_argument("--which", default="selected")
    ap.add_argument("--test-seed0", type=int, default=90000)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--n-val", type=int, default=40)
    ap.add_argument("--regimes", nargs="*", default=REGIMES)
    ap.add_argument("--kd-max", type=float, default=4.0)
    ap.add_argument("--random-candidates", type=int, default=150)
    ap.add_argument("--nm-evals", type=int, default=100)
    ap.add_argument("--const-candidates", type=int, default=48)
    ap.add_argument("--const-rounds", type=int, default=2)
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    return summarize(a) if a.summarize else run(a)


if __name__ == "__main__":
    raise SystemExit(main())
