"""Shared loading and statistics for the paper's tables, figures and numbers (PRE-VALIDATION, simulation only).

Everything here reads ``results/<comparison>/per_episode.csv`` (written by ``simulation/compare_controllers.py``) and nothing else, so every
number in the paper regenerates from those files. The statistics are the same functions the comparison script uses.

    python paper/make_numbers.py && python paper/tables.py && python paper/figures.py     # or: make -C paper all
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from simulation.compare_controllers import bootstrap_ci, holm, wilcoxon_p  # noqa: E402

RESULTS = ROOT / "results"
GEN = ROOT / "paper" / "generated"

# One fixed colour + marker + line style per method, used in every figure (colour-blind-safe Okabe-Ito palette).
STYLE = {
    "tuned": dict(color="#999999", marker="s", ls=":", label="Tuned preset"),
    "legacy": dict(color="#555555", marker="x", ls=":", label="Legacy default"),
    "best_constant": dict(color="#000000", marker="D", ls="-", label="Best constant"),
    "zn": dict(color="#8c564b", marker="v", ls="--", label="Ziegler-Nichols"),
    "bandit": dict(color="#E69F00", marker="^", ls="--", label="Bandit (one-shot)"),
    "bandit_retune": dict(color="#D55E00", marker="<", ls="--", label="Bandit (re-tuned)"),
    "random_search": dict(color="#009E73", marker="*", ls="-.", label="Hindsight oracle"),
    "ppo": dict(color="#0072B2", marker="o", ls="-", label="PPO residual (v3)"),
    "sac": dict(color="#CC79A7", marker="P", ls="-", label="SAC"),
    "td3": dict(color="#56B4E9", marker="X", ls="-", label="TD3"),
}

SETS = {
    "v2": dict(dir="controller_comparison", seeds="50000-50099", status="pre-specified (v2 design fixed before its test run)", algo="ppo"),
    "v3_expl": dict(dir="controller_comparison_v3", seeds="50000-50099", status="exploratory", algo="ppo"),
    "v3_conf": dict(dir="controller_comparison_v3_fresh", seeds="60000-60099", status="confirmatory", algo="ppo"),
    "v4_ppo": dict(dir="controller_comparison_v4_ppo", seeds="70000-70099", status="confirmatory (v4)", algo="ppo"),
    "v4_sac": dict(dir="controller_comparison_v4_sac", seeds="70000-70099", status="confirmatory (v4)", algo="sac"),
    "v4_td3": dict(dir="controller_comparison_v4_td3", seeds="70000-70099", status="confirmatory (v4)", algo="td3"),
}
REGIMES = ["static", "changes", "ood"]


class Comparison:
    """One results folder: per regime and controller, arrays aligned by scenario seed."""

    def __init__(self, key: str):
        self.key = key
        self.meta = SETS[key]
        self.dir = RESULTS / self.meta["dir"]
        self.manifest = json.loads((self.dir / "comparison_manifest.json").read_text(encoding="utf-8"))
        self.selection = json.loads((self.dir / "selection.json").read_text(encoding="utf-8"))
        by: dict = {}
        with open(self.dir / "per_episode.csv", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                by.setdefault(r["regime"], {}).setdefault(r["controller"], []).append(r)
        self.data = {reg: {c: sorted(rows, key=lambda r: int(r["seed"])) for c, rows in ctr.items()} for reg, ctr in by.items()}

    def arr(self, reg: str, ctrl: str, field: str = "ret") -> np.ndarray:
        return np.array([float(r[field]) for r in self.data[reg][ctrl]])

    def feasible(self, reg: str) -> np.ndarray:
        return self.arr(reg, "tuned", "margin") >= 1.0

    def seeds(self, reg: str) -> np.ndarray:
        return np.array([int(r["seed"]) for r in self.data[reg]["tuned"]])

    def controllers(self, reg: str) -> list:
        return list(self.data[reg])

    def selected_seed(self, reg: str):
        return self.selection[reg]["ppo_selected"]

    def paired(self, reg: str, ctrl: str, subset: str = "feasible") -> np.ndarray:
        """Return(ctrl) - return(best_constant) per scenario, on the feasible (or infeasible) scenarios."""
        f = self.feasible(reg)
        m = f if subset == "feasible" else ~f
        return (self.arr(reg, ctrl) - self.arr(reg, "best_constant"))[m]

    def summary(self, reg: str, ctrl: str, subset: str = "feasible") -> dict:
        d = self.paired(reg, ctrl, subset)
        lo, hi = bootstrap_ci(d, np.median)
        mlo, mhi = bootstrap_ci(d, np.mean)
        q1, q3 = (float(x) for x in np.percentile(d, [25, 75]))
        f = self.feasible(reg)
        m = f if subset == "feasible" else ~f
        r = self.arr(reg, ctrl)[m]
        return dict(n=int(len(d)), mean_ret=float(r.mean()), std_ret=float(r.std()), med_ret=float(np.median(r)), med=float(np.median(d)), lo=lo, hi=hi,
                    mean=float(d.mean()), mlo=mlo, mhi=mhi, q1=q1, q3=q3, p=wilcoxon_p(d) if ctrl != "best_constant" else float("nan"),
                    success=float(self.arr(reg, ctrl, "success")[m].mean()), at_bound=float(self.arr(reg, ctrl, "at_bound")[m].mean()))

    def holm_table(self) -> dict:
        """Holm-adjusted p for the secondary family (every controller except best_constant, all regimes, excluding the primary pair)."""
        keys, ps = [], []
        for reg in self.data:
            for c in self.controllers(reg):
                if c == "best_constant" or (reg == "static" and c == "ppo"):
                    continue
                keys.append((reg, c))
                ps.append(wilcoxon_p(self.paired(reg, c)))
        return dict(zip(keys, holm(ps)))

    def headroom_captured(self, reg: str, ctrl: str) -> float:
        f = self.feasible(reg)
        ref = self.arr(reg, "best_constant")[f].mean()
        orc = self.arr(reg, "random_search")[f].mean()
        return 100.0 * (self.arr(reg, ctrl)[f].mean() - ref) / (orc - ref)

    def learned(self, reg: str) -> list:
        return sorted(c for c in self.data[reg] if c.startswith(("ppo_s", "sac_s", "td3_s")))


def fmt_ci(med, lo, hi, nd=2) -> str:
    return f"{med:+.{nd}f} [{lo:+.{nd}f}, {hi:+.{nd}f}]"
