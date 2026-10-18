"""Generate paper/generated/numbers.tex (LaTeX macros) and numbers.json (macro -> value + source file) from results/ only.

Every number quoted in the manuscript text is a macro defined here, so the text cannot drift from the data. PRE-VALIDATION: simulation only.
"""

from __future__ import annotations

import json
import subprocess

import numpy as np
from analysis import GEN, RESULTS, ROOT, SETS, Comparison

PREFIX = {"v2": "VTwo", "v3_expl": "ExplThree", "v3_conf": "ConfThree", "v4_ppo": "VFourPpo", "v4_sac": "VFourSac", "v4_td3": "VFourTd"}
REG = {"static": "Static", "changes": "Changes", "ood": "Ood"}
SEEDWORD = ["A", "B", "C", "D", "E"]

macros: dict = {}


def add(name: str, value, source: str, fmt: str = "{}") -> None:
    tex = fmt.format(value)
    if isinstance(value, str):
        tex = tex.replace("_", r"\_")
    macros[name] = dict(value=value if isinstance(value, (int, float, str)) else str(value), tex=tex, source=source)


def sgn(x: float, nd: int = 2) -> str:
    return f"{x:+.{nd}f}".replace("-", "$-$")


def main() -> int:
    GEN.mkdir(parents=True, exist_ok=True)
    for key, pre in PREFIX.items():
        c = Comparison(key)
        src = f"results/{SETS[key]['dir']}/per_episode.csv"
        for reg, R in REG.items():
            sel = c.selected_seed(reg)
            s = c.summary(reg, "ppo")
            for k, name in [("med", "Med"), ("lo", "Lo"), ("hi", "Hi"), ("mean", "Mean"), ("mlo", "Mlo"), ("mhi", "Mhi"), ("q1", "Qone"), ("q3", "Qthree")]:
                add(f"{pre}{R}{name}", s[k], src, "{}" if False else sgn(s[k]))
            add(f"{pre}{R}N", s["n"], src)
            add(f"{pre}{R}NInf", int(len(c.feasible(reg)) - c.feasible(reg).sum()), src)
            add(f"{pre}{R}Succ", 100 * s["success"], src, "{:.0f}")
            b = c.summary(reg, "best_constant")
            add(f"{pre}{R}SuccBase", 100 * b["success"], src, "{:.0f}")
            add(f"{pre}{R}Cap", c.headroom_captured(reg, "ppo"), src, "{:.0f}")
            f = c.feasible(reg)
            orc = c.arr(reg, "random_search")[f].mean() - c.arr(reg, "best_constant")[f].mean()
            add(f"{pre}{R}OrcAbs", orc, src, "{:.2f}")
            add(f"{pre}{R}OrcPct", 100 * orc / abs(c.arr(reg, "best_constant")[f].mean()), src, "{:.0f}")
            learned = c.learned(reg)
            add(f"{pre}{R}CapMean", float(np.mean([c.headroom_captured(reg, n) for n in learned])), src, "{:.0f}")
            hol = c.holm_table()
            for i, n in enumerate(learned):
                ss = c.summary(reg, n)
                add(f"{pre}{R}Seed{SEEDWORD[i]}Med", ss["med"], src, sgn(ss["med"]))
                add(f"{pre}{R}Seed{SEEDWORD[i]}Holm", hol.get((reg, n), float("nan")), src, "{:.2g}")
            add(f"{pre}{R}Selected", sel, src)
            inf = c.summary(reg, "ppo", "infeasible")
            add(f"{pre}{R}InfPpo", inf["mean_ret"], src, "{:.1f}")
            add(f"{pre}{R}InfBase", b["mean_ret"] if False else c.arr(reg, "best_constant")[~f].mean(), src, "{:.1f}")
            add(f"{pre}{R}InfOrc", c.arr(reg, "random_search")[~f].mean(), src, "{:.1f}")
        add(f"{pre}Commit", c.manifest["commit"][:10], f"results/{SETS[key]['dir']}/comparison_manifest.json")
    # how much do the learned policies' final gains vary across scenarios? (feasible scenarios; best constant for reference)
    for key, pre in (("v3_conf", "ConfThree"), ("v4_ppo", "VFourPpo")):
        c = Comparison(key)
        src = f"results/{SETS[key]['dir']}/per_episode.csv"
        for reg, R in REG.items():
            f = c.feasible(reg)
            for gi, gname in enumerate(("Kp", "Ki", "Kd")):
                g = np.array([float(r[gname]) for r in c.data[reg]["ppo"]])[f]
                b = float(c.data[reg]["best_constant"][0][gname])
                add(f"{pre}{R}Gain{gname}Med", float(np.median(g)), src, "{:.2f}")
                add(f"{pre}{R}Gain{gname}Plo", float(np.percentile(g, 10)), src, "{:.2f}")
                add(f"{pre}{R}Gain{gname}Phi", float(np.percentile(g, 90)), src, "{:.2f}")
                add(f"{pre}{R}Gain{gname}Base", b, src, "{:.2f}")
    c3 = Comparison("v3_conf")
    for reg, R in REG.items():
        bs = c3.summary(reg, "bandit")
        add(f"ConfThree{R}BanditMed", bs["med"], "results/controller_comparison_v3_fresh/per_episode.csv", sgn(bs["med"]))
        add(f"ConfThree{R}BanditMean", bs["mean"], "results/controller_comparison_v3_fresh/per_episode.csv", sgn(bs["mean"]))
    # v2 specifics: bandit versus best constant, and where the v2 PPO gains ended up
    c2 = Comparison("v2")
    for reg, R in REG.items():
        bs = c2.summary(reg, "bandit")
        add(f"VTwo{R}BanditMed", bs["med"], "results/controller_comparison/per_episode.csv", sgn(bs["med"]))
    for i in range(5):
        rows = c2.data["static"][f"ppo_s{i}"]
        g = np.array([[float(r["Kp"]), float(r["Ki"]), float(r["Kd"])] for r in rows if float(r["margin"]) >= 1.0])
        add(f"VTwoGainKi{SEEDWORD[i]}", 100 * np.mean(g[:, 1] >= 198), "results/controller_comparison/per_episode.csv", "{:.0f}")
        add(f"VTwoGainKp{SEEDWORD[i]}", 100 * np.mean(g[:, 0] >= 49.5), "results/controller_comparison/per_episode.csv", "{:.0f}")
        ev = np.load(ROOT / f"rl/policies/ppo_v2/seed_{i}/evaluations.npz")
        r, t = ev["results"].mean(axis=1), ev["timesteps"]
        k = int(np.argmax(r))
        add(f"VTwoPeak{SEEDWORD[i]}", r[k], f"rl/policies/ppo_v2/seed_{i}/evaluations.npz", "{:.1f}")
        add(f"VTwoPeakStep{SEEDWORD[i]}", int(t[k]) // 1000, f"rl/policies/ppo_v2/seed_{i}/evaluations.npz")
        add(f"VTwoFinal{SEEDWORD[i]}", r[-1], f"rl/policies/ppo_v2/seed_{i}/evaluations.npz", "{:.1f}")
        add(f"VTwoDrop{SEEDWORD[i]}", r[k] - r[-1], f"rl/policies/ppo_v2/seed_{i}/evaluations.npz", "{:.1f}")
    drops = [macros[f"VTwoDrop{w}"]["value"] for w in SEEDWORD]
    add("VTwoDropMean", float(np.mean(drops)), "rl/policies/ppo_v2/seed_*/evaluations.npz", "{:.1f}")
    for tag, folder in (("ConfThree", "ppo_v3"), ("VFourPpo", "ppo_v4"), ("VFourSac", "sac_v4"), ("VFourTd", "td3_v4")):
        for i in range(3):
            vc = json.loads((ROOT / f"rl/policies/{folder}/seed_{i}/val_curve.json").read_text())
            add(f"{tag}ValDeg{SEEDWORD[i]}", vc["degradation_peak_to_final"], f"rl/policies/{folder}/seed_{i}/val_curve.json", "{:.2f}")
            add(f"{tag}SelStep{SEEDWORD[i]}", vc["selected_step"] // 1000, f"rl/policies/{folder}/seed_{i}/val_curve.json")
    # provenance
    man = json.loads((RESULTS / "controller_comparison_v3_fresh" / "comparison_manifest.json").read_text())
    for k, v in man["rl_software"].items():
        add("Ver" + {"torch": "Torch", "stable_baselines3": "Sbthree", "gymnasium": "Gym"}[k], v, "results/controller_comparison_v3_fresh/comparison_manifest.json")
    add("VerPython", man["software"]["python"], "results/controller_comparison_v3_fresh/comparison_manifest.json")
    add("VerNumpy", man["software"]["numpy"], "results/controller_comparison_v3_fresh/comparison_manifest.json")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    add("PaperCommit", head[:10] or "unknown", "git rev-parse HEAD")
    (GEN / "numbers.tex").write_text("% generated by paper/make_numbers.py - do not edit\n" + "\n".join(f"\\newcommand{{\\{k}}}{{{v['tex']}}}" for k, v in sorted(macros.items())) + "\n",
                                     encoding="utf-8", newline="\n")
    (GEN / "numbers.json").write_text(json.dumps(macros, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(macros)} macros")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
