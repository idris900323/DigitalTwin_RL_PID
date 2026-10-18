"""Generate the paper's LaTeX tables (booktabs) into paper/generated/ from results/ and rl/ files only. PRE-VALIDATION: simulation only."""

from __future__ import annotations

import yaml
from analysis import GEN, REGIMES, ROOT, SETS, STYLE, Comparison, fmt_ci

ORDER = ["tuned", "bandit", "bandit_retune", "best_constant", "ppo", "random_search"]
NICE = {"ppo": "PPO residual (selected)", "sac": "SAC residual (selected)", "td3": "TD3 residual (selected)"}


def esc(s: str) -> str:
    return s.replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def tex_num(s: str) -> str:
    return s.replace("-", "$-$")


def write(name: str, text: str) -> None:
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN / name).write_text(text, encoding="utf-8", newline="\n")


def p_fmt(p: float) -> str:
    if p != p:
        return "--"
    if p < 1e-3:
        m, e = f"{p:.1e}".split("e")
        return rf"${m}{{\times}}10^{{{int(e)}}}$"
    return f"{p:.3f}"


def main_table(key: str, fname: str, caption: str, label: str) -> None:
    c = Comparison(key)
    hol = c.holm_table()
    lines = [r"\begin{table*}[t]", r"\centering", r"\small", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
             r"\begin{tabular}{llrrrrrr}", r"\toprule",
             r"Regime & Controller & Return, mean $\pm$ SD & $\Delta$ median [95\,\% CI] & $\Delta$ mean [95\,\% CI] & IQR of $\Delta$ & $p_{\mathrm{Holm}}$ & Success (desc.)\\",
             r"\midrule"]
    for reg in REGIMES:
        n_feas = int(c.feasible(reg).sum())
        first = True
        for name in ORDER:
            if name not in c.data[reg]:
                continue
            s = c.summary(reg, name)
            label_name = NICE["ppo"] if name == "ppo" else STYLE[name]["label"]
            ph = "ref." if name == "best_constant" else (p_fmt(hol[(reg, name)]) if (reg, name) in hol else "primary")
            if name == "ppo" and reg == "static":
                ph = "primary: " + p_fmt(s["p"])
            lines.append(
                f"{(reg + f' (n={n_feas})') if first else ''} & {esc(label_name)} & {tex_num(f'{s['mean_ret']:.2f}')} $\\pm$ {s['std_ret']:.2f} & "
                f"{'--' if name == 'best_constant' else tex_num(fmt_ci(s['med'], s['lo'], s['hi']))} & "
                f"{'--' if name == 'best_constant' else tex_num(fmt_ci(s['mean'], s['mlo'], s['mhi']))} & "
                f"{'--' if name == 'best_constant' else tex_num(f'[{s['q1']:+.2f}, {s['q3']:+.2f}]')} & {ph} & {100 * s['success']:.0f}\\,\\%\\\\")
            first = False
        lines.append(r"\midrule")
    lines[-1] = r"\bottomrule"
    lines += [r"\end{tabular}", r"\end{table*}"]
    write(fname, "\n".join(lines) + "\n")


def infeasible_table() -> None:
    c = Comparison("v3_conf")
    lines = [r"\begin{table}[t]", r"\centering", r"\small",
             r"\caption{Infeasible scenarios (torque margin $<1$ at any point), confirmatory seeds 60000--60099: mean return. No controller can hold these targets; "
             r"differences are not evidence of better control.}", r"\label{tab:infeasible}",
             r"\begin{tabular}{lrrrr}", r"\toprule", r"Controller & static & changes & ood & \\", r"\midrule"]
    ns = {reg: int((~c.feasible(reg)).sum()) for reg in REGIMES}
    for name in ["tuned", "bandit", "best_constant", "ppo", "random_search"]:
        vals = [c.arr(reg, name)[~c.feasible(reg)].mean() for reg in REGIMES]
        lines.append(f"{esc(NICE['ppo'] if name == 'ppo' else STYLE[name]['label'])} & " + " & ".join(tex_num(f"{v:.1f}") for v in vals) + r" & \\")
    lines += [r"\midrule", "$n$ infeasible & " + " & ".join(str(ns[r]) for r in REGIMES) + r" & \\", r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    write("tab_infeasible.tex", "\n".join(lines) + "\n")


def v4_table() -> None:
    lines = [r"\begin{table*}[t]", r"\centering", r"\small",
             r"\caption{Experiment v4 (smaller residual range; PPO, SAC, TD3), unseen seeds 70000--70099, feasible scenarios. Paired return difference to the best constant for the "
             r"validation-selected seed: median [95\,\% CI] / mean [95\,\% CI] / IQR, and the three per-seed medians. $p_{\mathrm{Holm}}$ over the secondary family of each algorithm.}",
             r"\label{tab:v4}", r"\begin{tabular}{llrrrr}", r"\toprule",
             r"Algorithm & Regime & $\Delta$ median [95\,\% CI] & $\Delta$ mean [95\,\% CI] & IQR & per-seed medians (s0/s1/s2)\\", r"\midrule"]
    for key in ("v4_ppo", "v4_sac", "v4_td3"):
        c = Comparison(key)
        algo = SETS[key]["algo"].upper()
        first = True
        for reg in REGIMES:
            s = c.summary(reg, "ppo")
            seeds = " / ".join(tex_num(f"{c.summary(reg, n)['med']:+.2f}") for n in c.learned(reg))
            lines.append(f"{algo if first else ''} & {reg} & {tex_num(fmt_ci(s['med'], s['lo'], s['hi']))} & {tex_num(fmt_ci(s['mean'], s['mlo'], s['mhi']))} & "
                         f"{tex_num(f'[{s['q1']:+.2f}, {s['q3']:+.2f}]')} & {seeds}\\\\")
            first = False
        lines.append(r"\midrule")
    lines[-1] = r"\bottomrule"
    lines += [r"\end{tabular}", r"\end{table*}"]
    write("tab_v4.tex", "\n".join(lines) + "\n")


def hparam_table() -> None:
    v2 = yaml.safe_load((ROOT / "rl/ppo.yaml").read_text(encoding="utf-8"))
    v3 = yaml.safe_load((ROOT / "rl/ppo_v3.yaml").read_text(encoding="utf-8"))
    v4 = yaml.safe_load((ROOT / "rl/ppo_v4.yaml").read_text(encoding="utf-8"))
    cfg = yaml.safe_load((ROOT / "config/motor_parameters.yaml").read_text(encoding="utf-8"))["rl_env"]
    rows = [("Action space", "multiplicative, $\\pm10\\,\\%$ / decision", "residual, $\\times2^{a}$ (Ki: $+20a$)", "residual, $\\times1.5^{a}$ (Ki: $+10a$)"),
            ("Decisions per seed", v2["common"]["total_timesteps"], v3["common"]["total_timesteps"], v4["common"]["total_timesteps"]),
            ("Seeds", len(v2["common"]["seeds"]), len(v3["common"]["seeds"]), len(v4["common"]["seeds"])),
            ("Learning rate (PPO)", v2["ppo"]["learning_rate"], v3["ppo"]["learning_rate"], v4["ppo"]["learning_rate"]),
            ("PPO log-std init", "default (0)", v3["ppo"]["log_std_init"], v4["ppo"]["log_std_init"]),
            ("Training reward extra term", "none", "time outside 2\\,\\% band ($w=1$)", "same as v3"),
            ("Checkpoint used", "best on training-eval seeds", "best on validation seeds 40000+", "best on validation seeds 40000+"),
            ("Net architecture", "64--64", "64--64", "64--64")]
    lines = [r"\begin{table}[t]", r"\centering", r"\small", r"\caption{RL experiments: settings that differ between versions. Common: Stable-Baselines3 PPO, "
             r"decision every 20\,ms over a 2\,s episode, 16-dimensional observation, reward weights from the YAML (error "
             f"{cfg['reward']['w_error']}, effort {cfg['reward']['w_effort']}, chatter {cfg['reward']['w_chatter']}, gain change {cfg['reward']['w_gain_change']}, overshoot "
             f"{cfg['reward']['w_overshoot']}).}}", r"\label{tab:hparams}", r"\begin{tabular}{llll}", r"\toprule", r" & v2 & v3 & v4\\", r"\midrule"]
    for r in rows:
        lines.append(" & ".join(str(x) for x in r) + r"\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    write("tab_hparams.tex", "\n".join(lines) + "\n")


def v2_table() -> None:
    c = Comparison("v2")
    lines = [r"\begin{table}[t]", r"\centering", r"\small",
             r"\caption{Experiment v2 (unconstrained multiplicative actions), training seeds 0--4: evaluation return peaks early and degrades, and the final gains pile up at the bounds "
             r"(share of feasible static scenarios with Ki at its maximum / Kp at its maximum).}", r"\label{tab:v2}",
             r"\begin{tabular}{rrrrrr}", r"\toprule", r"Seed & peak (step) & final & drop & Ki at max & Kp at max\\", r"\midrule"]
    import json

    macros = json.loads((GEN / "numbers.json").read_text(encoding="utf-8"))
    for i, w in enumerate("ABCDE"):
        m = lambda k: macros[f"VTwo{k}{w}"]["tex"]  # noqa: E731
        lines.append(f"{i} & {tex_num(m('Peak'))} ({m('PeakStep')}k) & {tex_num(m('Final'))} & {m('Drop')} & {m('GainKi')}\\,\\% & {m('GainKp')}\\,\\%\\\\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    del c
    write("tab_v2.tex", "\n".join(lines) + "\n")


def main() -> int:
    main_table("v3_conf", "tab_main_conf.tex",
               r"Confirmatory result (v3, fresh seeds 60000--60099, feasible scenarios). Paired return difference to the best constant (chosen on validation seeds); "
               r"return is the primary metric, success rate (within 2\,\% and overshoot $\le10\,\%$) is descriptive only. "
               r"$p_{\mathrm{Holm}}$: Wilcoxon signed-rank, Holm-adjusted over the secondary family; the primary comparison is the single unadjusted test.", "tab:main_conf")
    main_table("v3_expl", "tab_main_expl.tex",
               r"Exploratory result (v3, seeds 50000--50099; the design was chosen after seeing v2 results on these seeds). Same layout as Table~\ref{tab:main_conf}.", "tab:main_expl")
    infeasible_table()
    v4_table()
    hparam_table()
    v2_table()
    print("tables written to", GEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
