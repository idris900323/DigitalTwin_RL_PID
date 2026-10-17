"""Precompute Tier 1 PID recommendations for every motor in motors/ on the bare-shaft load, for the browser page.

    python tools/precompute_recommendations.py            # writes autotune_360/recommendations.json (a few minutes)
    python tools/generate_js_config.py                     # then embeds it in config.generated.js and the HTML

The browser cannot run the optimiser, so it shows these stored results. Each entry records the profile hash it was computed from;
``tests/test_motor_library_ui.py`` fails if a profile changed after its recommendation was computed. PRELIMINARY: Tier 1 only.
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.motor_profile import list_motors  # noqa: E402
from tuning.recommend import recommend  # noqa: E402

OUT = ROOT / "autotune_360" / "recommendations.json"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--load", default="bare_shaft")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    out = {}
    for mid in list_motors():
        rec = recommend(mid, a.load, seed=a.seed)
        out[mid] = {
            "tier": int(rec.tier), "label": rec.tier.label, "load": rec.load_id, "profile_hash": rec.profile_hash, "seed": a.seed,
            "gains": {"Kp": rec.gains[0], "Ki": rec.gains[1], "Kd": rec.gains[2]}, "method": rec.winner,
            "predictions": rec.predictions, "constraint_probability": rec.constraint_probability,
            "margins": {k: (v if v == v and abs(v) != float("inf") else None) for k, v in rec.margins.items() if k != "stable"},
            "warnings": rec.warnings, "next_measurement": rec.next_measurement,
        }
        print(mid, [round(g, 4) for g in rec.gains], rec.winner)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
