"""Synthetic bench data generated from the twin with KNOWN parameters, for testing the validation tooling.

Nothing here is real data: it exists so that identification and comparison can be tested before hardware exists
(and so the tools are demonstrably wired correctly). Runs are returned as ``validation.load_bench_csv.Run`` objects
and can be written to / re-read from CSV in the bench schema.
"""

from __future__ import annotations

import csv
import math
from typing import Optional

import numpy as np

from validation.load_bench_csv import Run


def simulate_open_loop(p: dict, V: np.ndarray, dt: float, *, ratio: float, eta: float, J_added_out: float = 0.0,
                       tau_ext: Optional[np.ndarray] = None, tau_c: float = 0.0, eps: float = 0.01):
    """Open-loop motor + gearbox driven by a voltage sequence (L = 0). Fast scalar RK4, mirrors ``models.dc_motor``.

    ``p``: dict with R, Ke, Kt, Jm, Bm. ``J_added_out``: extra load inertia on the OUTPUT shaft (reflected as /N^2).
    Returns (theta_out [rad] after each step, omega_out [rad/s] after each step, current [A] at the start of each step).
    """
    R, Ke, Kt, Bm = p["R"], p["Ke"], p["Kt"], p["Bm"]
    J = p["Jm"] + J_added_out / ratio ** 2
    n = len(V)
    th_out = np.empty(n)
    w_out = np.empty(n)
    cur = np.empty(n)
    w = 0.0
    th = 0.0
    inv_ne = 1.0 / (ratio * eta)
    for k in range(n):
        v = V[k]
        tau = 0.0 if tau_ext is None else tau_ext[k] * inv_ne
        cur[k] = (v - Ke * w) / R

        def f(ww):
            fric = tau_c * math.tanh(ww / ratio / eps) * inv_ne if tau_c else 0.0
            return (Kt * (v - Ke * ww) / R - Bm * ww - tau - fric) / J

        k1 = f(w)
        k2 = f(w + 0.5 * dt * k1)
        k3 = f(w + 0.5 * dt * k2)
        k4 = f(w + dt * k3)
        w_new = w + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
        th += dt / 6.0 * (w + 2 * (w + 0.5 * dt * k1) + 2 * (w + 0.5 * dt * k2) + (w + dt * k3))
        w = w_new
        th_out[k] = th / ratio
        w_out[k] = w / ratio
    return th_out, w_out, cur


def prbs(n: int, amplitude: float, hold: int, seed: int = 0) -> np.ndarray:
    """Pseudo-random binary voltage sequence (+-amplitude), each level held for ``hold`` samples."""
    rng = np.random.default_rng(seed)
    levels = rng.choice([-1.0, 1.0], size=(n + hold - 1) // hold)
    return amplitude * np.repeat(levels, hold)[:n]


def make_run(p: dict, V: np.ndarray, dt: float, *, ratio: float, eta: float, cpr: int, i_noise: float = 0.0, theta_noise_counts: float = 0.0,
             J_added_out: float = 0.0, seed: int = 0, run_id: str = "synthetic", with_current: bool = True) -> Run:
    """Open-loop bench-like run: quantised encoder angle (+ optional jitter) and noisy current from the true parameters."""
    th, w, i = simulate_open_loop(p, V, dt, ratio=ratio, eta=eta, J_added_out=J_added_out)
    rng = np.random.default_rng(seed)
    lsb = 2 * math.pi / cpr
    th_meas = np.round((th + theta_noise_counts * lsb * rng.standard_normal(len(th))) / lsb) * lsb
    t = (np.arange(len(V)) + 1) * dt
    return Run(run_id, t, np.asarray(V, float), np.degrees(th_meas),
               (i + i_noise * rng.standard_normal(len(i))) if with_current else None,
               meta={"experiment_id": "H-03", "method": "synthetic open loop"},
               extra={"omega_rad_s": w})


def closed_loop_run(cfg: dict, gains, target_deg: float, true_values: Optional[dict] = None, *, t_end: float = 2.0,
                    i_noise: float = 0.0, seed: int = 0, run_id: str = "synthetic-cl", joint=None) -> Run:
    """Closed-loop step response of the twin with the TRUE plant ``true_values`` (keys of simulation.sensitivity.PARAMS)."""
    from models.factory import build_twin_from_config
    from simulation.sensitivity import perturbed_cfg

    c = perturbed_cfg(cfg, true_values or {})
    tw = build_twin_from_config(c, *gains, joint=joint, seed=seed)
    log = tw.run(math.radians(target_deg), int(round(t_end / tw.dt)))
    rng = np.random.default_rng(seed + 100)
    i = np.asarray(log["i_motor"]) + i_noise * rng.standard_normal(len(log["t"]))
    return Run(run_id, np.asarray(log["t"]), np.asarray(log["V_applied"]), np.degrees(np.asarray(log["theta_out_meas"])), i,
               target_deg=target_deg, gains=tuple(gains), meta={"experiment_id": "H-04", "method": "synthetic closed loop"},
               extra={"omega_rad_s": np.asarray(log["omega_out"]), "v_cmd_V": np.asarray(log["V_cmd"])})


def write_bench_csv(runs, path, cpr: int) -> None:
    """Write runs in the bench schema (``theta_counts`` from the angle), readable by ``load_bench_csv``."""
    cols = ["t_s", "target_deg", "theta_counts", "v_applied_V", "i_A", "kp", "ki", "kd", "run_id", "experiment_id", "method"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in runs:
            counts = np.round(r.theta_deg * cpr / 360.0).astype(int)
            for k in range(len(r.t)):
                w.writerow([f"{r.t[k]:.9g}", "" if r.target_deg is None else r.target_deg, counts[k], f"{r.V[k]:.9g}",
                            "" if r.i is None else f"{r.i[k]:.9g}", *(r.gains or ("", "", "")), r.run_id,
                            r.meta.get("experiment_id", ""), r.meta.get("method", "")])
