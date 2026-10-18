"""Post-hoc constant/scenario-conditioned sensitivity: macros, table and figures from results/constant_sensitivity_*/ (POST HOC, simulation only).

Reads per_episode.csv and constants.json written by ``simulation/constant_sensitivity.py --summarize``; nothing else.
Outputs: generated/numbers_sens.tex, tab_sensitivity.tex, fig_gain_scatter.pdf/png, fig_sens.pdf/png (+ meta).
"""

from __future__ import annotations

import csv
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from analysis import GEN, REGIMES, RESULTS, STYLE, bootstrap_ci, wilcoxon_p  # noqa: E402
from figures import COL2, save  # noqa: E402

SETS = {"v3": ("constant_sensitivity_v3_80k", "SensVThree"), "v4": ("constant_sensitivity_v4_80k", "SensVFour")}
PAIRS = [("best_constant_ext", "best_constant"), ("ppo_distilled", "best_constant"), ("scenario_fit", "best_constant"), ("ppo", "best_constant"),
         ("ppo", "best_constant_ext"), ("ppo", "ppo_distilled"), ("ppo", "scenario_fit")]
LABEL = {"best_constant": "best constant", "best_constant_ext": "extended-search constant", "ppo_distilled": "policy's median gains (constant)",
         "ppo_distilled_pooled": "policy's pooled median gains", "scenario_fit": "scenario-conditioned (non-learned)", "ppo": "learned policy"}
SENS_STYLE = {"best_constant_ext": dict(color="#000000", marker="D"), "ppo_distilled": dict(color="#0072B2", marker="o"), "scenario_fit": dict(color="#E69F00", marker="^"),
              "ppo": STYLE["ppo"], "ppo_distilled_pooled": dict(color="#56B4E9", marker="X")}


def load(key: str):
    d = RESULTS / SETS[key][0]
    rows = list(csv.DictReader(open(d / "per_episode.csv", encoding="utf-8")))
    by: dict = {}
    for r in rows:
        by.setdefault(r["regime"], {}).setdefault(r["controller"], []).append(r)
    for reg in by:
        for c in by[reg]:
            by[reg][c].sort(key=lambda r: int(r["seed"]))
    return by, json.loads((d / "constants.json").read_text(encoding="utf-8")), d


def diff(by, reg, A, B):
    feas = np.array([float(r["margin"]) >= 1.0 for r in by[reg]["best_constant"]])
    a = np.array([float(r["ret"]) for r in by[reg][A]])[feas]
    b = np.array([float(r["ret"]) for r in by[reg][B]])[feas]
    return a - b


def main() -> int:
    macros, lines = {}, []
    tex = [r"\begin{table*}[t]", r"\centering", r"\small",
           r"\caption{\textbf{Post hoc.} Stronger baselines derived on validation seeds only and evaluated once on fresh seeds 80000--80099 (feasible scenarios). "
           r"Paired return difference A$-$B: median [95\,\% CI], mean, IQR; unadjusted Wilcoxon $p$. Constants: ``extended'' = much larger validation search; ``policy's median gains'' = "
           r"the validation-selected policy's median final gains on the validation scenarios; ``scenario-conditioned'' = non-learned gains, $\log K_p$ and $\log K_d$ linear in "
           r"payload mass, gravity torque and payload inertia, fitted on validation seeds.}", r"\label{tab:sensitivity}",
           r"\begin{tabular}{llrrrr}", r"\toprule", r"Set / regime & A $-$ B & $\Delta$ median [95\,\% CI] & $\Delta$ mean & IQR of $\Delta$ & $p$\\", r"\midrule"]
    ok = False
    for key, (folder, pre) in SETS.items():
        if not (RESULTS / folder / "per_episode.csv").exists():
            continue
        ok = True
        by, consts, d = load(key)
        for reg in REGIMES:
            if reg not in by:
                continue
            first = True
            pairs = PAIRS + ([("ppo_distilled_pooled", "best_constant"), ("ppo", "ppo_distilled_pooled")] if "ppo_distilled_pooled" in by[reg] else [])
            for A, B in pairs:
                dd = diff(by, reg, A, B)
                lo, hi = bootstrap_ci(dd, np.median)
                q1, q3 = np.percentile(dd, [25, 75])
                p = wilcoxon_p(dd)
                R = {"static": "Static", "changes": "Changes", "ood": "Ood"}[reg]
                tag = "".join(w.capitalize() for w in f"{A} {B}".replace("_", " ").split())
                for nm, v in (("Med", np.median(dd)), ("Lo", lo), ("Hi", hi), ("Mean", dd.mean()), ("Qone", q1), ("Qthree", q3)):
                    macros[f"{pre}{R}{tag}{nm}"] = f"{v:+.2f}".replace("-", "$-$")
                macros[f"{pre}{R}{tag}P"] = f"{p:.2g}"
                lab = f"{LABEL[A]} $-$ {LABEL[B]}"
                tex.append(f"{(key + ' / ' + reg) if first else ''} & {lab} & {f'{np.median(dd):+.2f} [{lo:+.2f}, {hi:+.2f}]'.replace('-', '$-$')} & "
                           f"{f'{dd.mean():+.2f}'.replace('-', '$-$')} & {f'[{q1:+.2f}, {q3:+.2f}]'.replace('-', '$-$')} & {p:.2g}\\\\")
                first = False
            f = np.array([float(r["margin"]) >= 1.0 for r in by[reg]["best_constant"]])
            ext_ret = np.array([float(r["ret"]) for r in by[reg]["best_constant_ext"]])[f].mean()
            macros[f"{pre}{R}PpoExtPct"] = f"{100 * np.median(diff(by, reg, 'ppo', 'best_constant_ext')) / abs(ext_ret):.1f}".replace("-", "$-$")
            c = consts[reg]
            macros[f"{pre}{R}ExtKp"] = f"{c['best_constant_ext'][0]:.1f}"
            macros[f"{pre}{R}ExtKd"] = f"{c['best_constant_ext'][2]:.2f}"
            macros[f"{pre}{R}DistKp"] = f"{c['ppo_distilled'][0]:.1f}"
            macros[f"{pre}{R}DistKd"] = f"{c['ppo_distilled'][2]:.2f}"
            macros[f"{pre}{R}ValOrig"] = f"{c['val_return_original']:.2f}".replace("-", "$-$")
            macros[f"{pre}{R}ValExt"] = f"{c['val_return_ext']:.2f}".replace("-", "$-$")
            macros[f"{pre}{R}ValScen"] = f"{c['val_return_scenario_fit']:.2f}".replace("-", "$-$")
            macros[f"{pre}{R}ValPpo"] = f"{c['val_return_ppo']:.2f}".replace("-", "$-$")
            tex.append(r"\midrule")
    if not ok:
        print("no sensitivity results yet (run simulation/constant_sensitivity.py and --summarize)")
        return 0
    tex[-1] = r"\bottomrule"
    tex += [r"\end{tabular}", r"\end{table*}"]
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN / "tab_sensitivity.tex").write_text("\n".join(tex) + "\n", encoding="utf-8", newline="\n")
    (GEN / "numbers_sens.tex").write_text("% generated by paper/sensitivity.py\n" + "\n".join(f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(macros.items())) + "\n",
                                          encoding="utf-8", newline="\n")
    # --- figure: policy minus each stronger baseline, per regime (v3 set)
    by, consts, d = load("v3") if (RESULTS / SETS["v3"][0] / "per_episode.csv").exists() else (None, None, None)
    if by:
        fig, ax = plt.subplots(figsize=(COL2, 2.5))
        names = [("ppo", "best_constant"), ("best_constant_ext", "best_constant"), ("ppo_distilled", "best_constant"), ("scenario_fit", "best_constant"), ("ppo", "best_constant_ext")]
        w = 0.15
        for j, (A, B) in enumerate(names):
            meds, los, his = [], [], []
            for reg in REGIMES:
                dd = diff(by, reg, A, B)
                lo, hi = bootstrap_ci(dd, np.median)
                meds.append(np.median(dd)); los.append(np.median(dd) - lo); his.append(hi - np.median(dd))
            st = SENS_STYLE[A]
            ax.errorbar(np.arange(3) + (j - 2) * w, meds, yerr=[los, his], color=st["color"], marker=st["marker"], ls="none", capsize=2,
                        label=f"{LABEL[A]} $-$ {LABEL[B]}", mfc="white" if B != "best_constant" else st["color"])
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(range(3), REGIMES)
        ax.set_ylabel("paired median $\\Delta$ return")
        ax.legend(frameon=False, fontsize=6, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
        save(fig, "fig_sens", [f"results/{SETS['v3'][0]}/per_episode.csv"])
        # --- figure: do the policy's gains track the load?
        for gname, gi in (("Kp", "Kp"), ("Kd", "Kd")):
            fig, axes = plt.subplots(3, 4, figsize=(COL2, 4.8), sharey="row")
            for i, reg in enumerate(REGIMES):
                rows = by[reg]["ppo"]
                f = np.array([float(r["margin"]) >= 1.0 for r in rows])
                g = np.array([float(r[gi]) for r in rows])[f]
                base = float(by[reg]["best_constant"][0][gi])
                for j, (k, lab) in enumerate((("mass", "payload mass (kg)"), ("length", "arm length (m)"), ("gravity", "gravity flag"), ("target", "target (deg)"))):
                    x = np.array([float(r[k]) for r in rows])[f]
                    ax = axes[i, j]
                    ax.scatter(x + (np.random.default_rng(0).uniform(-0.05, 0.05, len(x)) if k == "gravity" else 0), g, s=5, color=STYLE["ppo"]["color"], alpha=0.6, linewidths=0)
                    ax.axhline(base, color="black", lw=0.8, ls="--")
                    if i == 2:
                        ax.set_xlabel(lab)
                    if j == 0:
                        ax.set_ylabel(f"{gname} ({reg})")
            save(fig, f"fig_gain_scatter_{gname.lower()}", [f"results/{SETS['v3'][0]}/per_episode.csv"])
    print("sensitivity macros/table/figures written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
