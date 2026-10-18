"""Generate the paper's figures (vector PDF + PNG) and fig*.meta.json into paper/generated/ from results/ and rl/ files only.

PRE-VALIDATION: every figure is simulation on the unvalidated twin; captions (in the manuscript) say so. One fixed colour, marker and
line style per method (analysis.STYLE) in every figure. No titles inside the figures.
"""

from __future__ import annotations

import json
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from analysis import GEN, REGIMES, ROOT, SETS, STYLE, Comparison  # noqa: E402

plt.rcParams.update({"font.size": 8, "axes.labelsize": 8, "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7, "pdf.fonttype": 42,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150, "axes.grid": True, "grid.alpha": 0.25})
COL1, COL2 = 3.5, 7.2


def commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def save(fig, name: str, data_files: list) -> None:
    GEN.mkdir(parents=True, exist_ok=True)
    fig.savefig(GEN / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(GEN / f"{name}.png", dpi=300, bbox_inches="tight")
    (GEN / f"{name}.meta.json").write_text(json.dumps({"data_files": data_files, "commit": commit(), "script": "paper/figures.py"}, indent=1) + "\n",
                                           encoding="utf-8", newline="\n")
    plt.close(fig)


def strip(ax, data_list, positions, color, width=0.5, marker="o"):
    """Box (median, IQR) with every point overlaid."""
    ax.boxplot(data_list, positions=positions, widths=width, showfliers=False, patch_artist=True,
               boxprops=dict(facecolor="white", edgecolor=color), medianprops=dict(color=color, lw=1.5), whiskerprops=dict(color=color), capprops=dict(color=color))
    rng = np.random.default_rng(0)
    for x, d in zip(positions, data_list):
        ax.scatter(x + rng.uniform(-width / 3, width / 3, len(d)), d, s=4, color=color, alpha=0.45, marker=marker, linewidths=0)


def fig_paired(key: str, name: str) -> None:
    """Paired return difference to the best constant, selected PPO seed, feasible scenarios, per regime."""
    c = Comparison(key)
    fig, ax = plt.subplots(figsize=(COL1, 2.4))
    for i, reg in enumerate(REGIMES):
        d = c.paired(reg, "ppo")
        s = c.summary(reg, "ppo")
        strip(ax, [d], [i], STYLE["ppo"]["color"], marker=STYLE["ppo"]["marker"])
        ax.errorbar([i + 0.38], [s["med"]], yerr=[[s["med"] - s["lo"]], [s["hi"] - s["med"]]], color="black", capsize=2, lw=1)
        ax.scatter([i + 0.38], [s["mean"]], color="black", marker="D", s=10, zorder=5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(range(3), [f"{r}\n(n={int(c.feasible(r).sum())})" for r in REGIMES])
    ax.set_ylabel("return(PPO) $-$ return(best constant)")
    ax.set_ylim(-3, 6)
    save(fig, name, [f"results/{SETS[key]['dir']}/per_episode.csv"])


def fig_headroom() -> None:
    c = Comparison("v3_conf")
    fig, ax = plt.subplots(figsize=(COL1, 2.2))
    width = 0.25
    for j, n in enumerate(["ppo_s0", "ppo_s1", "ppo_s2"]):
        vals = [c.headroom_captured(r, n) for r in REGIMES]
        ax.bar(np.arange(3) + (j - 1) * width, vals, width, color=STYLE["ppo"]["color"], alpha=0.35 + 0.3 * j, edgecolor="black", label=f"seed {j}")
    ax.axhline(0, color="black", lw=0.8)
    ax.axhline(100, color=STYLE["random_search"]["color"], ls=STYLE["random_search"]["ls"], lw=1, label="hindsight oracle (100 %)")
    ax.set_xticks(range(3), REGIMES)
    ax.set_ylabel("headroom captured (%)")
    ax.legend(frameon=False)
    save(fig, "fig_headroom", ["results/controller_comparison_v3_fresh/per_episode.csv"])


def fig_curves() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(COL2, 2.3), sharey=False)
    ax = axes[0]
    for i in range(5):
        ev = np.load(ROOT / f"rl/policies/ppo_v2/seed_{i}/evaluations.npz")
        ax.plot(ev["timesteps"] / 1e3, ev["results"].mean(axis=1), color="#999999", lw=1, label="seed" if i == 0 else None)
    ax.set_xlabel("training decisions (thousands)")
    ax.set_ylabel("evaluation return (training-eval seeds)")
    ax.text(0.03, 0.05, "v2: unconstrained", transform=ax.transAxes)
    ax = axes[1]
    for i in range(3):
        vc = json.loads((ROOT / f"rl/policies/ppo_v3/seed_{i}/val_curve.json").read_text())
        ax.plot([p["step"] / 1e3 for p in vc["curve"]], [p["mean"] for p in vc["curve"]], color=STYLE["ppo"]["color"], lw=1, alpha=0.4 + 0.3 * i)
        ax.scatter([vc["selected_step"] / 1e3], [vc["selected_val_mean"]], color="black", marker="o", s=14, zorder=5)
    ax.set_xlabel("training decisions (thousands)")
    ax.set_ylabel("validation return (seeds 40000+)")
    ax.text(0.03, 0.05, "v3: residual (dots: selected checkpoint)", transform=ax.transAxes)
    save(fig, "fig_curves", [f"rl/policies/ppo_v2/seed_{i}/evaluations.npz" for i in range(5)] + [f"rl/policies/ppo_v3/seed_{i}/val_curve.json" for i in range(3)])


def fig_algos() -> None:
    fig, ax = plt.subplots(figsize=(COL2, 2.5))
    keys = ["v4_ppo", "v4_sac", "v4_td3"]
    comps = {k: Comparison(k) for k in keys}
    pos = 0
    ticks, labels = [], []
    for reg in REGIMES:
        for k in keys:
            a = SETS[k]["algo"]
            c = comps[k]
            strip(ax, [c.paired(reg, "ppo")], [pos], STYLE[a]["color"], width=0.7, marker=STYLE[a]["marker"])
            s = c.summary(reg, "ppo")
            ax.scatter([pos], [s["mean"]], color="black", marker="D", s=10, zorder=5)
            ticks.append(pos)
            labels.append(a.upper())
            pos += 1
        pos += 1
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(ticks, labels)
    for i, reg in enumerate(REGIMES):
        ax.text(i * 4 + 1, ax.get_ylim()[1] if False else 5.2, reg, ha="center")
    ax.set_ylim(-6, 6)
    ax.set_ylabel("return(policy) $-$ return(best constant)")
    save(fig, "fig_algos", [f"results/{SETS[k]['dir']}/per_episode.csv" for k in keys])


def fig_baselines() -> None:
    """Fresh seeds: each method's median paired difference to the best constant, with 95 % CI, per regime."""
    c = Comparison("v3_conf")
    fig, ax = plt.subplots(figsize=(COL2, 2.5))
    names = ["tuned", "bandit", "bandit_retune", "ppo", "random_search"]
    w = 0.16
    for j, n in enumerate(names):
        meds, los, his = [], [], []
        for reg in REGIMES:
            s = c.summary(reg, n)
            meds.append(s["med"]); los.append(s["med"] - s["lo"]); his.append(s["hi"] - s["med"])
        st = STYLE[n]
        ax.errorbar(np.arange(3) + (j - 2) * w, meds, yerr=[los, his], color=st["color"], marker=st["marker"], ls="none", capsize=2, label=st["label"])
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(range(3), REGIMES)
    ax.set_ylabel("median $\\Delta$ return vs best constant")
    ax.set_ylim(-5, 4)
    ax.legend(frameon=False, ncol=3, loc="lower right")
    save(fig, "fig_baselines", ["results/controller_comparison_v3_fresh/per_episode.csv"])


def main() -> int:
    fig_paired("v3_conf", "fig_paired_conf")
    fig_paired("v3_expl", "fig_paired_expl")
    fig_headroom()
    fig_curves()
    fig_algos()
    fig_baselines()
    print("figures written to", GEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
