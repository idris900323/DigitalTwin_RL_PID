"""Fixed-gain PID test sequence (master prompt section 15) on the preliminary digital twin.

Runs: low P -> higher P -> P+D -> P+I -> full PID, plus the legacy default gains for context, and writes

    <out-dir>/pid_test_sequence.csv          every metric per case
    <out-dir>/pid_test_sequence.md           the same as a Markdown table plus an auto-generated summary
    <out-dir>/pid_test_sequence_raw.csv      raw per-tick logs in the project schema (simulation/rawlog.py)
    <out-dir>/pid_sequence_{angle,error,voltage,current}.png
    <out-dir>/pid_sequence_manifest.json     script, arguments, commit, config hash, seeds, file checksums

PRELIMINARY: the plant parameters are datasheet-derived and not validated on hardware.

    python simulation/simulate_pid.py --out-dir results
    python simulation/simulate_pid.py --params method_a          # the Ke != Kt "Method A" parameter set
    python simulation/simulate_pid.py --arm-mass 0.5 --arm-length 0.10 --gravity --target-deg 180

Outputs are deterministic: the same inputs regenerate byte-identical CSV/MD/PNG files (fixed backend, no
timestamps or software tags in the images; the manifest has no timestamp unless --stamp is given).
"""

from __future__ import annotations

import argparse
import csv
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402

from models.factory import build_twin_from_config  # noqa: E402
from models.joint import Joint, JointParams  # noqa: E402
from models.motors import add_motor_argument, get_cfg, motor_from_argv  # noqa: E402
from simulation import plotstyle, rawlog  # noqa: E402
from simulation.metrics import METRIC_NAMES, all_metrics  # noqa: E402

CONFIG_PATH = ROOT / "config" / "motor_parameters.yaml"
SIMULATABLE_KEY = ("R_ohm", "Kt_Nm_per_A")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def simulatable_sets(cfg: dict) -> list:
    """Parameter sets that define R and Kt (method_b has only Ke, so it cannot be simulated)."""
    return [k for k, v in cfg["base_motor"]["derived"].items() if all(v.get(x) is not None for x in SIMULATABLE_KEY)]


def run_case(cfg, gains, *, target_deg, t_end, dt, params, joint, noise_counts, seed):
    """One closed-loop step response; returns (log, metrics)."""
    tw = build_twin_from_config(cfg, *gains, scenario=params, joint=joint, noise_counts=noise_counts, seed=seed, dt=dt)
    log = tw.run(math.radians(target_deg), int(round(t_end / dt)))
    theta = np.degrees(log["theta_out"])
    m = all_metrics(log["t"], theta, target_deg, log["V_applied"], log["i_motor"], error_deg=np.degrees(log["error"]))
    return log, m


def fmt(v: float, nd: int = 3) -> str:
    return "never" if isinstance(v, float) and math.isnan(v) else f"{v:.{nd}f}"


def summary_text(cases, results, target_deg, t_end) -> str:
    """Plain-language reading of the sequence, with every statement computed from the results."""
    by = {n: m for n, m in zip([c[0] for c in cases], results)}
    n = list(by)
    low, hp, hhp, pd, pi_, pid_ = (by[x] for x in n[:6])
    lines = []
    lines.append(f"Low P (Kp = {cases[0][1][0]:g}) is too slow: after {t_end:g} s the joint is still "
                 f"{abs(low['sse_deg']):.2f} deg from the {target_deg:g} deg target and the command only reaches "
                 f"{low['effort_abs_Vs'] / t_end:.1f} V on average, far below the 12 V limit.")
    lines.append(f"Raising Kp to {cases[1][1][0]:g} and {cases[2][1][0]:g} cuts the rise time to {fmt(hp['rise_s'])} s and "
                 f"{fmt(hhp['rise_s'])} s but overshoot grows to {hp['overshoot_pct']:.2f} % and {hhp['overshoot_pct']:.2f} %; "
                 f"the voltage saturates at the supply limit, so the rise time is saturation-limited and tripling Kp "
                 f"buys little ({fmt(hp['rise_s'])} s to {fmt(hhp['rise_s'])} s).")
    lines.append(f"Adding D (Kd = {cases[3][1][2]:g}) damps the response: overshoot falls from {hp['overshoot_pct']:.2f} % to "
                 f"{pd['overshoot_pct']:.2f} % and the settling time from {fmt(hp['settle_s'])} s to {fmt(pd['settle_s'])} s.")
    if abs(pi_['sse_deg']) > abs(hp['sse_deg']) + 1e-3:
        lines.append(f"Adding I (Ki = {cases[4][1][1]:g}) does not help on the bare shaft: there is no load torque to remove "
                     f"(P-only steady-state error {hp['sse_deg']:+.3f} deg), so the integral only adds overshoot "
                     f"({pi_['overshoot_pct']:.2f} %) and a slower settle ({fmt(pi_['settle_s'])} s); its steady-state "
                     f"error after {t_end:g} s is {pi_['sse_deg']:+.3f} deg because it is still unwinding.")
    else:
        lines.append(f"Adding I (Ki = {cases[4][1][1]:g}) reduces the steady-state error to {pi_['sse_deg']:+.3f} deg at the "
                     f"cost of overshoot ({pi_['overshoot_pct']:.2f} %).")
    lines.append(f"The full PID ({cases[5][1][0]:g} / {cases[5][1][1]:g} / {cases[5][1][2]:g}) gives {pid_['overshoot_pct']:.2f} % "
                 f"overshoot, {fmt(pid_['settle_s'])} s settling and {pid_['sse_deg']:+.3f} deg error at {t_end:g} s. "
                 f"The legacy default gains give {by[n[6]]['overshoot_pct']:.1f} % overshoot for comparison.")
    return " ".join(lines)


def write_outputs(out_dir, cases, results, logs, args, cfg):
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []

    # --- table CSV and Markdown
    header = ["case", "Kp", "Ki", "Kd", *METRIC_NAMES]
    csv_path = out / "pid_test_sequence.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for (name, g), m in zip(cases, results):
            w.writerow([name, *g, *["" if math.isnan(m[k]) else f"{m[k]:.6g}" for k in METRIC_NAMES]])
    files.append(csv_path)

    units = {"rise_s": "s", "overshoot_pct": "%", "settle_s": "s", "time_to_2pct_s": "s", "sse_deg": "deg", "rmse_deg": "deg",
             "mae_deg": "deg", "iae_deg_s": "deg s", "ise_deg2_s": "deg^2 s", "itae_deg_s2": "deg s^2",
             "effort_abs_Vs": "V s", "effort_sq_V2s": "V^2 s", "peak_current_A": "A", "energy_J": "J"}
    md = ["# Fixed-PID test sequence (preliminary twin)", "",
          f"Parameter set `{args.params or cfg['simulation']['active_electrical_scenario']}`, target {args.target_deg:g} deg, "
          f"{args.t_end:g} s, dt {args.dt * 1e3:g} ms, arm {args.arm_mass:g} kg x {args.arm_length:g} m, "
          f"gravity {'on' if args.gravity else 'off'}, encoder noise {args.noise_counts:g} counts RMS (seed {args.seed}). "
          "Datasheet-derived parameters, not validated on hardware.", "",
          "| case | Kp | Ki | Kd | " + " | ".join(f"{k} [{units[k]}]" for k in METRIC_NAMES) + " |",
          "|---|---|---|---|" + "---|" * len(METRIC_NAMES)]
    for (name, g), m in zip(cases, results):
        md.append(f"| {name} | {g[0]:g} | {g[1]:g} | {g[2]:g} | " + " | ".join(fmt(m[k], 4) for k in METRIC_NAMES) + " |")
    md += ["", "## What the sequence shows", "", summary_text(cases, results, args.target_deg, args.t_end), ""]
    md_path = out / "pid_test_sequence.md"
    md_path.write_text("\n".join(md), encoding="utf-8", newline="\n")
    files.append(md_path)

    # --- raw logs
    blocks = []
    cpr = cfg["encoder"]["output_cpr"]
    for k, ((name, g), log) in enumerate(zip(cases, logs)):
        blocks.append(rawlog.rows_from_twin_log(
            log, target_deg=args.target_deg, gains=g, cpr=cpr, v_supply=cfg["supply"]["V_rated"], run_id=f"S-01-{k}",
            experiment_id="S-01", seed=args.seed, method=name, payload_kg=args.arm_mass, arm_len_m=args.arm_length,
            gravity_on=args.gravity, true_params={"params": args.params or cfg["simulation"]["active_electrical_scenario"]}))
    raw_path = out / "pid_test_sequence_raw.csv"
    rawlog.write_raw_csv(raw_path, blocks)
    files.append(raw_path)

    # --- figures (one fixed style per case; the paper figures carry captions instead of titles)
    panels = [("angle", "Output angle [deg]", lambda lg: np.degrees(lg["theta_out"])),
              ("error", "Tracking error [deg]", lambda lg: np.degrees(lg["error"])),
              ("voltage", "Applied voltage [V]", lambda lg: lg["V_applied"]),
              ("current", "Armature current [A]", lambda lg: lg["i_motor"])]
    for key, ylabel, getter in panels:
        fig, ax = plt.subplots(figsize=(7.0, 4.2))
        for (name, _g), log in zip(cases, logs):
            ax.plot(log["t"], getter(log), label=name, linewidth=1.4, **{k: v for k, v in plotstyle.style(name).items() if k != "marker"})
        if key == "angle":
            ax.axhline(args.target_deg, color="gray", linewidth=0.8, linestyle=":", label="target")
        if key == "voltage":
            v = cfg["supply"]["V_rated"]
            ax.axhline(v, color="red", linewidth=0.6, linestyle=":"); ax.axhline(-v, color="red", linewidth=0.6, linestyle=":")
        ax.set_xlabel("Time [s]"); ax.set_ylabel(ylabel)
        ax.set_title(f"Fixed-PID test sequence, preliminary twin ({args.params or cfg['simulation']['active_electrical_scenario']}, simulated)", fontsize=9)
        ax.grid(alpha=0.3); ax.legend(fontsize=7, ncol=2)
        fig.tight_layout()
        path = out / f"pid_sequence_{key}.png"
        fig.savefig(path, dpi=150, metadata={"Software": None})
        plt.close(fig)
        files.append(path)

    shown = dict(vars(args))
    try:                                                    # keep local absolute paths out of committed artefacts
        shown["out_dir"] = pathlib.Path(args.out_dir).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        shown["out_dir"] = pathlib.Path(args.out_dir).name
    manifest = rawlog.write_manifest(out, script="simulation/simulate_pid.py", args=shown, seeds=args.seed, files=files,
                                     stamp=args.stamp, name="pid_sequence_manifest.json")
    return files + [manifest]


def build_parser(cfg):
    ap = argparse.ArgumentParser(description="Fixed-PID test sequence on the preliminary digital twin.")
    add_motor_argument(ap)
    ap.add_argument("--target-deg", type=float, default=cfg["simulation"]["theta_ref_default_deg"])
    ap.add_argument("--t-end", type=float, default=cfg["simulation"]["run_duration_s"])
    ap.add_argument("--dt", type=float, default=cfg["simulation"]["control_loop_dt_s"])
    ap.add_argument("--params", choices=simulatable_sets(cfg), default=None, help="electrical parameter set (default: YAML active set)")
    ap.add_argument("--arm-mass", type=float, default=0.0, help="payload point mass at the arm tip [kg]")
    ap.add_argument("--arm-length", type=float, default=0.0, help="arm length [m]")
    ap.add_argument("--gravity", action="store_true", help="vertical-plane gravity (0 deg = hanging)")
    ap.add_argument("--noise-counts", type=float, default=0.0, help="RMS encoder jitter in counts")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default=str(ROOT / "results"))
    ap.add_argument("--stamp", action="store_true", help="add a UTC timestamp to the manifest (breaks byte-identity of the manifest only)")
    return ap


def main(argv=None):
    cfg = get_cfg(motor_from_argv(argv))
    args = build_parser(cfg).parse_args(argv)
    cases = [(c["name"], (c["Kp"], c["Ki"], c["Kd"])) for c in cfg["pid_test_sequence"]]
    joint = Joint(JointParams(payload_mass_kg=args.arm_mass, arm_length_m=args.arm_length, gravity_on=args.gravity))
    logs, results = [], []
    for name, g in cases:
        log, m = run_case(cfg, g, target_deg=args.target_deg, t_end=args.t_end, dt=args.dt, params=args.params, joint=joint,
                          noise_counts=args.noise_counts, seed=args.seed)
        logs.append(log); results.append(m)
        print(f"{name:16s} rise {fmt(m['rise_s'])} s  overshoot {m['overshoot_pct']:.2f} %  settle {fmt(m['settle_s'])} s  "
              f"sse {m['sse_deg']:+.3f} deg  IAE {m['iae_deg_s']:.3f} deg s  peak I {m['peak_current_A']:.2f} A")
    files = write_outputs(args.out_dir, cases, results, logs, args, cfg)
    print("wrote:", ", ".join(pathlib.Path(f).name for f in files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
