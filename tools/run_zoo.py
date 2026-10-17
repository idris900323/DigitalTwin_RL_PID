"""Run the synthetic motor zoo and write results/motor_zoo/ (summary.md, rows.json). A few seconds per motor with --fast, ~30 s without.

    python tools/run_zoo.py --n 20 --out results/motor_zoo
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.motors import load_base_config  # noqa: E402
from tuning import zoo  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", default=str(ROOT / "results" / "motor_zoo"))
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--first-seed", type=int, default=0)
    a = ap.parse_args(argv)
    fast = dict(popsize=6, maxiter=8, restarts=1, n_train_plants=6, n_test_plants=16) if a.fast else dict(popsize=8, maxiter=15, restarts=1, n_train_plants=10, n_test_plants=32)
    base = load_base_config()
    rows = []
    for k in range(a.n):
        seed = a.first_seed + k
        row = zoo.run_one(seed, base=base, fast=fast)
        rows.append(row)
        print(seed, row["status"], {k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items() if k in ("stable", "meets_spec", "price")}, flush=True)
    s = zoo.summarise(rows)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.json").write_text(json.dumps(rows, indent=1, default=float) + "\n", encoding="utf-8", newline="\n")
    cover = ", ".join(f"{k} {v * 100:.0f} %" for k, v in s["band_coverage"].items())
    md = ["# Synthetic motor zoo (simulated, preliminary)", "",
          f"{s['motors']} random but physically consistent motors; Tier 1 pipeline on the published-style datasheet text only; judged on the TRUE plant. "
          "Generation assumptions are in `tuning/zoo.py` (rotor inertia log-normal sigma 0.6 around the mass-based approximation, efficiency 0.45-0.9, ...); "
          "the calibration numbers depend on them.", "",
          "| criterion | result |", "|---|---|",
          f"| imported | {s['imported']} of {s['motors']} |",
          f"| Tier 1 gains stable on the true plant | {s['stable_fraction'] * 100:.0f} % |",
          f"| meet the overshoot, settling and accuracy spec on the true plant | {s['meets_spec_fraction'] * 100:.0f} % |",
          f"| price of uncertainty: cost vs gains optimised with perfect knowledge (median / 90th percentile ratio) | {s['price_of_uncertainty_median']:.2f} / {s['price_of_uncertainty_p90']:.2f} |",
          f"| true-plant metrics inside the predicted 5th-95th percentile band | {cover} (mean {s['band_coverage_mean'] * 100:.0f} %; target about 90 %) |",
          "| true parameter inside the derived interval | " + ", ".join(f"{k} {v * 100:.0f} %" for k, v in s["interval_coverage"].items()) + " |", "",
          "## Per motor", "", "| motor | V | N | stable | meets spec | cost ratio | overshoot % | settling s | datasheet conflicts |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["status"] != "ok":
            md.append(f"| {r['motor']} | {r['V']:g} | {r['N']:g} | {r['status']} | | | | | {r['reason']} |")
        else:
            md.append(f"| {r['motor']} | {r['V']:g} | {r['N']:g} | {r['stable']} | {r['meets_spec']} | {r['price']:.2f} | {r['overshoot']:.2f} | {r['settle']:.3f} | {'; '.join(r['conflicts']) or '-'} |")
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(s, indent=1, default=float))


if __name__ == "__main__":
    main()
