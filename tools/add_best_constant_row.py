"""Add the 'best constant gains' baseline row to the committed policy metadata without retraining (the policy file is unchanged).

The gains are chosen on validation contexts (seed 77), the row is evaluated on the same held-out sets as the other rows (seed 123).
    python tools/add_best_constant_row.py
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "autotune_360"))
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import train_autotune_360 as T  # noqa: E402

META = ROOT / "autotune_360" / "autotune_policy_360.meta.json"


def main():
    best, val_cost = T.best_constant_gains()
    meta = json.loads(META.read_text(encoding="utf-8"))
    n, seed = 1000, 123
    for label, feas in (("feasible-only", True), ("full (incl. infeasible)", False)):
        ctx = T.sample_context(n, np.random.default_rng(seed), feasible_only=feas, stats={})
        c, ok = T._score(np.tile(best, (n, 1)), ctx, np.random.default_rng(seed + 1))
        meta["held_out"][label]["rows"][T.BEST_CONST_NAME] = dict(mean_cost=float(c.mean()), within_2pct=float(ok))
        print(f"{label}: {c.mean():.3f} | {100 * ok:.1f} %")
    meta["best_constant"] = dict(gains=[float(x) for x in best], validation_mean_cost=val_cost, validation_seed=77)
    META.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("best constant gains", np.round(best, 3))


if __name__ == "__main__":
    main()
