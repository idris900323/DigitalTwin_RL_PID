"""Numerical PID tuning on the nonlinear simulation, nominal or robust across plant uncertainty.

The plant is simulated with the vectorised batch simulator of ``autotune_360/train_autotune_360.py`` (encoder quantisation,
filtered derivative, anti-windup, voltage cap, RK4, gravity, optional driver current limit). It does not model command delay
or joint friction, so final gains are re-checked in the full Python twin by ``tuning.recommend``.

Cost per scenario (documented, weights in ``COST_WEIGHTS``):
    iae * IAE/|ref| + overshoot * overshoot/cap + settle * settling/cap + sse * |final error|/accuracy
    + effort * mean(V^2)/Vmax^2 + chatter * mean|dV|/Vmax
plus a large penalty for every violated constraint (overshoot cap, settling cap, accuracy, current limit, margins).
Robust cost over a set of plants and payload/target contexts: mean + 0.5 * mean of the worst 10 %.

Search: ``scipy.optimize.differential_evolution`` (derivative-free, seeded) on log-scaled gains with bounds around the analytic
design; several restarts.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import differential_evolution

import autotune_360.train_autotune_360 as T
from tuning.linear import LinearPlant, noise_voltage_rms
from tuning.loads import Load

COST_WEIGHTS = dict(iae=3.0, overshoot=2.0, settle=1.0, sse=5.0, effort=0.3, chatter=0.5)
PENALTY = 20.0
RISK_FRACTION, RISK_WEIGHT = 0.10, 0.5


def plant_arrays(cfg: dict, factors: Optional[Dict[str, np.ndarray]] = None, n: int = 1) -> Dict[str, np.ndarray]:
    """Plant parameters as arrays of length ``n``: the config nominal times optional multiplicative ``factors``."""
    sc = cfg["simulation"]["active_electrical_scenario"]
    d, e = cfg["base_motor"]["derived"][sc], cfg["base_motor"]["estimated"]
    nom = {"R": d["R_ohm"], "Kt": d["Kt_Nm_per_A"], "Ke": d["Ke_V_s_per_rad"], "Jm": e["Jm_kgm2"],
           "Bm": d.get("Bm_Nms_per_rad", e["Bm_Nms_per_rad"]), "eta": d.get("gearbox_efficiency", cfg["gearbox"]["efficiency"])}
    f = factors or {}
    out = {k: np.full(n, v, dtype=float) * np.asarray(f.get(k, 1.0)) for k, v in nom.items()}
    # Kt and Ke move together when a shared "K" factor is supplied (an ideal motor has Ke = Kt)
    if "K" in f:
        out["Kt"] = np.full(n, nom["Kt"]) * np.asarray(f["K"])
        out["Ke"] = np.full(n, nom["Ke"]) * np.asarray(f["K"])
    out["eta"] = np.minimum(out["eta"], 0.99)
    return out


def sample_factors(intervals: Dict[str, Tuple[float, float]], n: int, seed: int) -> Dict[str, np.ndarray]:
    """Multiplicative factors drawn inside the derived intervals: uniform, or log-uniform when the interval spans more than 2x."""
    rng = np.random.default_rng(seed)
    out = {}
    for k, (lo, hi) in intervals.items():
        if hi <= lo:
            out[k] = np.full(n, lo)
        elif hi / max(lo, 1e-12) > 2.0 and lo > 0:
            out[k] = np.exp(rng.uniform(math.log(lo), math.log(hi), n))
        else:
            out[k] = rng.uniform(lo, hi, n)
    return out


def batch_cfg(cfg: dict, plants: Dict[str, np.ndarray]) -> dict:
    """Config dict for ``simulate_batch`` with array-valued plant parameters."""
    return dict(V_rated=cfg["supply"]["V_rated"], ratio=cfg["gearbox"]["ratio"], eff=plants["eta"], cpr=cfg["encoder"]["output_cpr"],
                R=plants["R"], Kt=plants["Kt"], Ke=plants["Ke"], Jm=plants["Jm"], Bm=plants["Bm"], dt=cfg["simulation"]["control_loop_dt_s"],
                duration=cfg["simulation"]["run_duration_s"], ref_deg=90.0,
                tau_f=cfg.get("controller", {}).get("derivative_filter_tau_s", 0.01), current_limit=cfg.get("driver", {}).get("current_limit_A"))


def contexts(load: Load, payloads: Optional[Sequence[float]] = None) -> List[Tuple[float, float]]:
    """(payload mass, target angle) pairs the tuning must serve: payload extremes (or the given list) x task targets."""
    ps = list(payloads) if payloads is not None else sorted({load.payload_min_kg, load.payload_max_kg})
    return [(m, t) for m in ps for t in load.targets_deg]


def simulate(cfg: dict, load: Load, gains: np.ndarray, ctxs: List[Tuple[float, float]], plants: Dict[str, np.ndarray]):
    """Simulate every (gain row x context x plant). Returns arrays and the index layout (M, C, S)."""
    gains = np.atleast_2d(gains)
    M, C, S = len(gains), len(ctxs), len(plants["R"])
    B = M * C * S
    kp, ki, kd = (np.repeat(gains[:, j], C * S) for j in range(3))
    mass = np.tile(np.repeat([c[0] for c in ctxs], S), M)
    ref = np.tile(np.repeat([c[1] for c in ctxs], S), M)
    sel = lambda a: np.tile(a, M * C)
    pl = {k: sel(v) for k, v in plants.items()}
    vpct = np.full(B, 100.0 if load.max_voltage_V is None else 100.0 * load.max_voltage_V / cfg["supply"]["V_rated"])
    length = np.full(B, load.arm_length_m)
    grav = np.full(B, 1.0 if load.gravity else 0.0)
    th, V, I = T.simulate_batch(kp, ki, kd, mass, length, grav, vpct, ref, cfg=batch_cfg(cfg, pl), noise=0.0, return_current=True)
    return np.degrees(th), V, I, ref, vpct, (M, C, S)


def metrics(th_deg, V, I, ref, vpct, cfg: dict, load: Load) -> Dict[str, np.ndarray]:
    """Per-simulation metrics (vectorised over columns)."""
    N, B = th_deg.shape
    dt = cfg["simulation"]["control_loop_dt_s"]
    t = (np.arange(1, N + 1) * dt)[:, None]
    e = ref - th_deg
    tol = np.maximum(0.02 * ref, load.accuracy_deg)
    outside = np.abs(e) > tol
    last_out = N - 1 - np.argmax(outside[::-1], axis=0)
    settle = np.where(outside.any(axis=0), (last_out + 1) * dt, 0.0)
    settle = np.where(outside[-1], np.inf, settle)
    vmax = cfg["supply"]["V_rated"] * vpct / 100.0
    return {
        "iae": np.sum(np.abs(e), axis=0) * dt / ref,
        "overshoot": np.maximum(0.0, (th_deg.max(axis=0) - ref) / ref * 100.0),
        "settle": settle,
        "sse": np.abs(e[-N // 10:]).mean(axis=0),
        "effort": np.mean(V ** 2, axis=0) / vmax ** 2,
        "chatter": np.mean(np.abs(np.diff(V, axis=0)), axis=0) / vmax,
        "peak_i": np.max(np.abs(I), axis=0),
        "t": t,
    }


def scenario_cost(m: Dict[str, np.ndarray], load: Load, cfg: dict) -> Tuple[np.ndarray, np.ndarray]:
    """(cost, violations) per simulation. Violations count the constraints broken (as a graded amount)."""
    w = COST_WEIGHTS
    settle = np.minimum(m["settle"], 4.0 * load.max_settling_s)
    cost = (w["iae"] * m["iae"] / (0.25 * load.max_settling_s) + w["overshoot"] * m["overshoot"] / max(load.max_overshoot_pct, 1.0)
            + w["settle"] * settle / load.max_settling_s + w["sse"] * m["sse"] / load.accuracy_deg + w["effort"] * m["effort"]
            + w["chatter"] * m["chatter"])
    viol = (np.maximum(0.0, m["overshoot"] / load.max_overshoot_pct - 1.0) + np.maximum(0.0, m["settle"] / load.max_settling_s - 1.0).clip(max=5.0)
            + np.maximum(0.0, m["sse"] / load.accuracy_deg - 1.0).clip(max=5.0))
    if load.max_current_A is not None:
        viol = viol + np.maximum(0.0, m["peak_i"] / load.max_current_A - 1.0)
    return cost, viol


def risk(values: np.ndarray, fraction: float = RISK_FRACTION, weight: float = RISK_WEIGHT) -> np.ndarray:
    """Mean plus ``weight`` x mean of the worst ``fraction``, along the last axis."""
    k = max(1, int(math.ceil(fraction * values.shape[-1])))
    worst = np.sort(values, axis=-1)[..., -k:].mean(axis=-1)
    return values.mean(axis=-1) + weight * worst


def evaluate(cfg: dict, load: Load, gains: np.ndarray, ctxs, plants) -> Dict[str, np.ndarray]:
    """Risk cost and violation per gain row over all contexts x plants."""
    th, V, I, ref, vpct, (M, C, S) = simulate(cfg, load, gains, ctxs, plants)
    m = metrics(th, V, I, ref, vpct, cfg, load)
    cost, viol = scenario_cost(m, load, cfg)
    cost, viol = cost.reshape(M, C * S), viol.reshape(M, C * S)
    return {"cost": risk(cost), "mean_cost": cost.mean(axis=1), "worst_cost": cost.max(axis=1), "violation": risk(viol),
            "p_ok": (viol <= 1e-9).mean(axis=1), "metrics": {k: v.reshape(M, C * S) for k, v in m.items() if k != "t"}}


def margin_violation(plant: LinearPlant, g, min_pm: float, min_gm: float) -> float:
    m = plant.margins(*g, n=3000)
    if not m["stable"]:
        return 5.0
    return max(0.0, (min_pm - m["phase_margin_deg"]) / min_pm) + max(0.0, (min_gm - m["gain_margin_db"]) / min_gm)


def optimize(cfg: dict, load: Load, ref_gains: Sequence[float], ctxs, plants, lin_plants: Sequence[LinearPlant], *, seed: int = 0,
             popsize: int = 10, maxiter: int = 25, restarts: int = 2, min_pm: float = 45.0, min_gm: float = 6.0,
             noise_limit_v: Optional[float] = None, kd_floor: float = 1e-6) -> Dict[str, object]:
    """Differential evolution on (log Kp, log Kd, log10 of Ki / (Kp0*wn0)). Returns gains and the evaluation of the best."""
    kp0, ki0, kd0 = ref_gains
    kp0, kd0 = max(kp0, 1e-6), max(kd0, kd_floor)
    ki_scale = kp0 * 8.0                                           # Ki = ki_scale * 10**u with u in [-3, 0]
    bounds = [(math.log10(kp0 / 10.0), math.log10(kp0 * 10.0)), (math.log10(kd0 / 30.0), math.log10(kd0 * 10.0)), (-3.0, 0.0)]

    def to_gains(x):
        return np.stack([10 ** x[:, 0], ki_scale * 10 ** x[:, 2], 10 ** x[:, 1]], axis=1)

    def objective(x):
        x = np.atleast_2d(x.T)
        g = to_gains(x)
        ev = evaluate(cfg, load, g, ctxs, plants)
        pen = np.array([max(margin_violation(lp, gi, min_pm, min_gm) for lp in lin_plants) for gi in g])
        if noise_limit_v is not None:
            pen = pen + np.array([max(0.0, noise_voltage_rms(gi[0], gi[2], lin_plants[0]) / noise_limit_v - 1.0) for gi in g])
        return ev["cost"] + PENALTY * (ev["violation"] + pen)

    best = None
    for r in range(restarts):
        res = differential_evolution(objective, bounds, seed=seed + 1000 * r, popsize=popsize, maxiter=maxiter, tol=1e-6, polish=False,
                                     updating="deferred", vectorized=True, init="sobol")
        if best is None or res.fun < best.fun:
            best = res
    g = to_gains(np.atleast_2d(best.x))[0]
    return {"gains": tuple(float(v) for v in g), "objective": float(best.fun), "bounds_log10": bounds, "ki_scale": ki_scale,
            # Ki at its LOWER bound just means "no integral action wanted" (legitimate without gravity), so only the other edges count
            "at_bound": [bool(best.x[0] < bounds[0][0] + 0.02 * (bounds[0][1] - bounds[0][0]) or best.x[0] > bounds[0][1] - 0.02 * (bounds[0][1] - bounds[0][0])),
                         bool(best.x[1] > bounds[1][1] - 0.02 * (bounds[1][1] - bounds[1][0])),
                         bool(best.x[2] > bounds[2][1] - 0.02 * (bounds[2][1] - bounds[2][0]))]}
