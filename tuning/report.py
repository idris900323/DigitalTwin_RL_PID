"""One-page Markdown + HTML report for a recommendation, with Bode and step-response-band figures (G3B.5.8)."""

from __future__ import annotations

import html
import math
import pathlib
from typing import List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from tuning import optimize  # noqa: E402
from tuning.recommend import Recommendation, corner_plants, intervals_as_factors, verify_in_twin  # noqa: E402


def _fmt(v, nd=4):
    if isinstance(v, float) and (math.isnan(v)):
        return "n/a"
    if isinstance(v, float) and math.isinf(v):
        return "inf"
    return f"{v:.{nd}g}" if isinstance(v, float) else str(v)


def bode_figure(rec: Recommendation, path) -> None:
    load = rec.load
    plants = corner_plants(rec.cfg, load, intervals_as_factors(rec.model), load.payload_max_kg, max(load.targets_deg))
    w = np.logspace(-0.5, math.log10(0.8 * math.pi / rec.cfg["simulation"]["control_loop_dt_s"]), 800)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.5, 5.5), sharex=True)
    for k, p in enumerate(plants):
        L, _, _ = p.frequency_response(*rec.gains, w)
        kw = dict(color="#0072B2" if k == 0 else "#999999", linewidth=1.6 if k == 0 else 0.7, label="nominal" if k == 0 else ("plant corners" if k == 1 else None))
        a1.semilogx(w, 20 * np.log10(np.abs(L)), **kw)
        a2.semilogx(w, np.degrees(np.unwrap(np.angle(L))), **kw)
    a1.axhline(0, color="k", linewidth=0.6); a2.axhline(-180, color="r", linewidth=0.6, linestyle=":")
    a1.set_ylabel("|L| [dB]"); a2.set_ylabel("phase [deg]"); a2.set_xlabel("frequency [rad/s]")
    a1.legend(fontsize=7); a1.grid(alpha=0.3); a2.grid(alpha=0.3)
    fig.suptitle("Open-loop Bode plot of the recommended gains (linear model, preliminary)", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130, metadata={"Software": None})
    plt.close(fig)


def step_band_figure(rec: Recommendation, path, n: int = 24, seed: int = 5) -> None:
    load, cfg = rec.load, rec.cfg
    plants = optimize.plant_arrays(cfg, optimize.sample_factors(intervals_as_factors(rec.model), n, seed), n)
    ctx = [(load.payload_max_kg, max(load.targets_deg))]
    th, _V, _I, ref, _v, _ = optimize.simulate(cfg, load, np.array([rec.gains]), ctx, plants)
    t = np.arange(1, th.shape[0] + 1) * cfg["simulation"]["control_loop_dt_s"]
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.fill_between(t, np.percentile(th, 5, axis=1), np.percentile(th, 95, axis=1), color="#0072B2", alpha=0.25, label="5th-95th percentile over plausible plants")
    ax.plot(t, np.median(th, axis=1), color="#0072B2", label="median")
    ax.axhline(ref[0], color="gray", linestyle=":", linewidth=0.8)
    ax.set_xlabel("time [s]"); ax.set_ylabel("output angle [deg]"); ax.grid(alpha=0.3); ax.legend(fontsize=7)
    ax.set_title(f"Predicted step response, payload {ctx[0][0]:g} kg (simulated, preliminary)", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=130, metadata={"Software": None}); plt.close(fig)


def markdown(rec: Recommendation, bode_name: str, band_name: str, twin: dict) -> str:
    m, kp = rec.model, rec.gains
    L: List[str] = [f"# PID recommendation: {rec.motor_id} on {rec.load_id}", "", f"**{rec.tier.label}**", "",
                    "Computed on a model derived from the datasheet; nothing here is validated on hardware. "
                    "\"Best\" means lowest robust cost for the stated objective and constraints below, not a global optimum.", "",
                    "## Recommended gains", "", "| Kp | Ki | Kd | method |", "|---|---|---|---|",
                    f"| {kp[0]:.4g} | {kp[1]:.4g} | {kp[2]:.4g} | {rec.winner} |", "",
                    f"Runner-up: {rec.runner_up or 'none'}. Re-tune after validation. Profile hash `{rec.profile_hash}`.", "",
                    "## Derived plant parameters (with intervals)", "", "| parameter | value | interval | provenance / confidence | basis |", "|---|---|---|---|---|"]
    for k, p in m.params.items():
        L.append(f"| {k} | {p.value:.4g} | [{p.lo:.3g}, {p.hi:.3g}] | {p.provenance} / {p.confidence} | {p.method} |")
    L += ["", "Least certain parameters: " + ", ".join(m.least_certain()), ""]
    if m.conflicts:
        L += ["## Datasheet conflicts", ""] + [f"- **{c['what']}**: {c['detail']}" for c in m.conflicts] + [""]
    L += ["## Method comparison (same held-out plants and contexts)", "", "| method | Kp | Ki | Kd | robust cost | fraction meeting all constraints | phase margin [deg] | gain margin [dB] | delay margin [ms] | stable |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for x in rec.methods + rec.references:
        L.append(f"| {x.name} | {x.gains[0]:.4g} | {x.gains[1]:.4g} | {x.gains[2]:.4g} | {_fmt(x.cost, 4)} | {_fmt(x.p_ok, 3)} | {_fmt(x.pm_deg, 3)} | "
                 f"{_fmt(x.gm_db, 3)} | {_fmt(x.delay_margin_s * 1e3 if x.delay_margin_s == x.delay_margin_s else float('nan'), 3)} | {x.stable} |")
    L += ["", "Why the winner won:", ""] + [f"- {k}: {_fmt(float(v), 4)}" for k, v in rec.cost_breakdown.items()] + [""]
    L += ["## Predicted performance (held-out plausible plants x payload/target contexts)", "", "| metric | 5th | median | 95th |", "|---|---|---|---|"]
    for k, p in rec.predictions.items():
        L.append(f"| {k} | {p['p5']:.3g} | {p['p50']:.3g} | {p['p95']:.3g} |")
    L += ["", "Probability of meeting each constraint: " + ", ".join(f"{k} {v * 100:.0f} %" for k, v in rec.constraint_probability.items()), "",
          f"![step response band]({band_name})", "",
          "## Stability margins", "", f"Worst of nominal and corner plants (linear model with filter and delay): gain margin {_fmt(rec.margins['gain_margin_db'], 3)} dB, "
          f"phase margin {_fmt(rec.margins['phase_margin_deg'], 3)} deg, delay margin {_fmt(rec.margins['delay_margin_s'] * 1e3, 3)} ms.", "", f"![bode]({bode_name})", "",
          "## Check in the full twin (command delay, quantisation)", "",
          f"Overshoot {twin['overshoot_pct']:.2f} %, settling {_fmt(twin['settle_s'], 3)} s, steady-state error {twin['sse_deg']:+.3f} deg, peak current {twin['peak_current_A']:.2f} A "
          f"(nominal plant, payload {rec.load.payload_max_kg:g} kg).", "", "## Warnings", ""]
    L += [f"- {w}" for w in rec.warnings] or ["- none"]
    L += ["", "## Constraints and objective", "",
          f"Overshoot <= {rec.load.max_overshoot_pct:g} %, settling <= {rec.load.max_settling_s:g} s, accuracy <= {rec.load.accuracy_deg:g} deg, "
          f"noise <= {rec.load.max_noise_V_rms:g} V RMS, margins >= {rec.settings['min_pm_deg']:g} deg / {rec.settings['min_gm_db']:g} dB. "
          f"Cost weights {rec.settings['cost_weights']}; risk = {rec.settings['risk']}. Seed {rec.settings['seed']}.", "",
          "## Most valuable next measurement", "", rec.next_measurement, ""]
    return "\n".join(L)


def to_html(md: str) -> str:
    """Tiny Markdown-to-HTML for this report's constructs (headers, tables, lists, images, bold, paragraphs)."""
    out, table = ["<!doctype html><meta charset='utf-8'><title>PID recommendation</title><body style='font-family:sans-serif;max-width:60rem;margin:2rem auto'>"], []
    def flush():
        if table:
            out.append("<table border='1' cellpadding='4' style='border-collapse:collapse'>")
            for i, row in enumerate(table):
                tag = "th" if i == 0 else "td"
                out.append("<tr>" + "".join(f"<{tag}>{html.escape(c.strip())}</{tag}>" for c in row.strip().strip("|").split("|")) + "</tr>")
            out.append("</table>")
            table.clear()
    for line in md.splitlines():
        if line.startswith("|"):
            if set(line.replace("|", "").strip()) <= set("-: "):
                continue
            table.append(line)
            continue
        flush()
        if line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("!["):
            alt, src = line[2:].split("](")
            out.append(f"<img alt='{html.escape(alt)}' src='{html.escape(src.rstrip(')'))}' style='max-width:100%'>")
        elif line.startswith("- "):
            out.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.strip():
            body = html.escape(line)
            while "**" in body:
                body = body.replace("**", "<b>", 1).replace("**", "</b>", 1)
            out.append(f"<p>{body}</p>")
    flush()
    return "\n".join(out)


def write_report(rec: Recommendation, out_dir, name: str = "recommendation") -> List[pathlib.Path]:
    """Write ``<name>.md``, ``<name>.html`` and the two figures into ``out_dir``; returns the paths."""
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bode, band = out / f"{name}_bode.png", out / f"{name}_step_band.png"
    bode_figure(rec, bode)
    step_band_figure(rec, band)
    twin = verify_in_twin(rec)
    md = markdown(rec, bode.name, band.name, twin)
    p_md, p_html = out / f"{name}.md", out / f"{name}.html"
    p_md.write_text(md + "\n", encoding="utf-8", newline="\n")
    p_html.write_text(to_html(md) + "\n", encoding="utf-8", newline="\n")
    return [p_md, p_html, bode, band]
