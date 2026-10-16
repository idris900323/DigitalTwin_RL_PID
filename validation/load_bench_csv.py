"""Load and sanity-check a bench log in the project raw-log schema (simulation/rawlog.py).

Required columns: ``t_s``, a voltage column (``v_applied_V``, alias ``v_meas_V``: the voltage MEASURED at the motor
terminals) and an angle column (``theta_counts`` of the output encoder, or ``theta_deg``). Optional: ``i_A``,
``omega_rad_s``, ``target_deg``, ``v_cmd_V``, ``temp_C``, ``vsupply_V``, gains and the hardware-only fields
``loop_dt_us``, ``sat_flag``, ``encoder_raw``, ``adc_raw_i``, ``adc_raw_v``. Several runs may share one file,
distinguished by ``run_id``.

``load_bench_csv`` never edits the file; it returns ``Run`` objects plus a list of ``Issue`` records from the automatic
sanity checks (the same checks the logging tool is meant to run after every run).
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

HARDWARE_ONLY = ("loop_dt_us", "sat_flag", "encoder_raw", "adc_raw_i", "adc_raw_v")
ALIASES = {"v_meas_V": "v_applied_V"}


@dataclass
class Issue:
    run_id: str
    severity: str          # "error" or "warning"
    check: str
    message: str


@dataclass
class Run:
    run_id: str
    t: np.ndarray
    V: np.ndarray                      # measured terminal voltage [V]
    theta_deg: np.ndarray              # output angle [deg]
    i: Optional[np.ndarray] = None     # armature current [A]
    target_deg: Optional[float] = None
    gains: Optional[Tuple[float, float, float]] = None
    meta: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def dt(self) -> float:
        return float(np.median(np.diff(self.t)))


def _f(x: str) -> float:
    return float("nan") if x == "" else float(x)


def load_bench_csv(path, cpr: int, v_limit: float = 12.0, i_limit: float = 7.5, max_jitter_us: float = 100.0,
                   sat_fraction: float = 0.5) -> Tuple[List[Run], List[Issue]]:
    """Read ``path``; returns (runs, issues). ``cpr`` converts ``theta_counts`` to degrees."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("empty file")
        cols = [ALIASES.get(c, c) for c in reader.fieldnames]
        if "t_s" not in cols or "v_applied_V" not in cols or not ({"theta_counts", "theta_deg"} & set(cols)):
            raise ValueError("bench CSV needs t_s, a voltage column (v_applied_V or v_meas_V) and theta_counts or theta_deg; "
                             f"found {reader.fieldnames}")
        raw: Dict[str, Dict[str, list]] = {}
        for row in reader:
            rid = row.get("run_id") or "run0"
            d = raw.setdefault(rid, {c: [] for c in cols})
            for k, v in row.items():
                d[ALIASES.get(k, k)].append(v)
    runs, issues = [], []
    for rid, d in raw.items():
        t = np.array([_f(x) for x in d["t_s"]])
        V = np.array([_f(x) for x in d["v_applied_V"]])
        if "theta_counts" in d and any(x != "" for x in d["theta_counts"]):
            theta = np.array([_f(x) for x in d["theta_counts"]]) * 360.0 / cpr
        else:
            theta = np.array([_f(x) for x in d["theta_deg"]])
        i = np.array([_f(x) for x in d["i_A"]]) if "i_A" in d and any(x != "" for x in d["i_A"]) else None
        tgt = None
        if "target_deg" in d and d["target_deg"] and d["target_deg"][0] != "":
            tgt = float(d["target_deg"][0])
        gains = None
        if all(k in d and d[k] and d[k][0] != "" for k in ("kp", "ki", "kd")):
            gains = (float(d["kp"][0]), float(d["ki"][0]), float(d["kd"][0]))
        extra = {k: np.array([_f(x) for x in d[k]]) for k in HARDWARE_ONLY + ("temp_C", "vsupply_V", "omega_rad_s", "v_cmd_V") if k in d}
        meta = {k: d[k][0] for k in ("experiment_id", "session_id", "unit_id", "method") if k in d and d[k]}
        run = Run(rid, t, V, theta, i, tgt, gains, meta, extra)
        runs.append(run)
        issues += check_run(run, v_limit, i_limit, max_jitter_us, sat_fraction)
    return runs, issues


def check_run(run: Run, v_limit: float = 12.0, i_limit: float = 7.5, max_jitter_us: float = 100.0, sat_fraction: float = 0.5) -> List[Issue]:
    """Automatic sanity checks: ordering, gaps, NaNs, signal ranges, saturation, loop timing."""
    out: List[Issue] = []
    add = lambda sev, chk, msg: out.append(Issue(run.run_id, sev, chk, msg))
    t = run.t
    if len(t) < 10:
        add("error", "length", f"only {len(t)} samples")
        return out
    if np.any(~np.isfinite(t)) or np.any(~np.isfinite(run.V)) or np.any(~np.isfinite(run.theta_deg)):
        add("error", "nan", "NaN/empty values in t, voltage or angle")
    dts = np.diff(t)
    if np.any(dts <= 0):
        add("error", "time_order", "time is not strictly increasing")
        return out
    dt = float(np.median(dts))
    gaps = int(np.sum(dts > 1.5 * dt))
    if gaps:
        add("warning", "missing_samples", f"{gaps} gaps longer than 1.5 x the median step ({dt * 1e3:.3f} ms)")
    jitter = (np.max(dts) - np.min(dts)) * 1e6
    if "loop_dt_us" in run.extra:
        ld = run.extra["loop_dt_us"]
        if np.nanmax(np.abs(ld - np.nanmedian(ld))) > max_jitter_us:
            add("warning", "loop_timing", f"loop period jitter above {max_jitter_us:g} us")
    elif jitter > max_jitter_us and gaps == 0:
        add("warning", "timestamp_jitter", f"timestamp spacing varies by {jitter:.0f} us")
    if np.nanmax(np.abs(run.V)) > 1.05 * v_limit:
        add("error", "voltage_range", f"|V| reaches {np.nanmax(np.abs(run.V)):.2f} V, above the {v_limit:g} V limit")
    if run.i is not None and np.nanmax(np.abs(run.i)) > 1.2 * i_limit:
        add("error", "current_range", f"|i| reaches {np.nanmax(np.abs(run.i)):.2f} A, above 1.2 x the {i_limit:g} A rating")
    if np.nanmax(np.abs(run.V)) > 0:
        sat = float(np.mean(np.abs(run.V) >= 0.98 * np.nanmax(np.abs(run.V))))
        if sat > sat_fraction:
            add("warning", "saturation", f"voltage is at its maximum for {sat * 100:.0f} % of the run (weak excitation)")
    if "sat_flag" in run.extra and np.nanmean(run.extra["sat_flag"]) > sat_fraction:
        add("warning", "saturation_flag", "controller saturation flag set for most of the run")
    if np.ptp(run.theta_deg) == 0:
        add("warning", "no_motion", "the angle never changes")
    return out
