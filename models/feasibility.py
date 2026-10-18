"""Torque feasibility of a payload on the joint (G1.5).

Gravity acts in a vertical plane with 0 deg = arm hanging, so the gravity
torque at output angle theta is

    tau_g(theta) = (m_payload*L + m_arm*L_cg) * g * sin(theta)

The motor can deliver at most its stall torque at the voltage cap,

    tau_avail = Kt * (V_cap / R) * N * eta        (output-shaft side)

This is an UPPER BOUND on the torque available. It is the stall value: while the joint
moves, the back-EMF Ke*omega_m reduces the armature current, so the torque the motor
can actually deliver falls with speed (tau = Kt*(V - Ke*omega_m)/R * N * eta). A case
reported as "ok" or "marginal" can therefore still stall mid-motion; "infeasible" is
reliable (it fails even at stall). A moving-state margin would need the speed profile and
is not computed. The driver's current limit (if any) would also lower the stall figure;
it is not included here yet.

Two margins are reported because both matter:
  * ``margin_target`` -- can the joint *hold* the target? (torque at the target angle)
  * ``margin_path``   -- can it *get there*? The step starts at 0 deg, so the arm
    must pass through the worst angle on [0, target]; for targets >= 90 deg
    that is the full |sin| = 1 point.

``status`` is derived from ``margin_path`` (the binding one): below 1.0 is
"infeasible", below ``marginal_margin`` (config, default 1.2) is "marginal".
With gravity off there is no holding torque and the margin is infinite.

All quantities are SI; torques in N*m, angles in degrees at the boundary.
"""

from __future__ import annotations

import numpy as np

G = 9.81  # m/s^2


def _peak_sin(target_deg):
    """max |sin(theta)| over theta in [0, target] (arm starts hanging at 0 deg)."""
    t = np.abs(np.asarray(target_deg, dtype=float))
    return np.where(t >= 90.0, 1.0, np.sin(np.radians(t)))


def available_torque(Kt, R, ratio, eta, V_rated, v_pct=100.0):
    """Output-side stall torque [N*m] at the voltage cap V_rated*v_pct/100."""
    return Kt * (V_rated * np.asarray(v_pct, dtype=float) / 100.0 / R) * ratio * eta


def feasibility_arrays(tau_avail, mass, length, target_deg, gravity=1.0, arm_mass=0.0, arm_cg=0.0,
                       marginal_margin=1.2):
    """Vectorised core. Returns dict of numpy arrays (see module docstring)."""
    moment = np.asarray(mass, dtype=float) * np.asarray(length, dtype=float) + arm_mass * arm_cg
    g_on = np.asarray(gravity, dtype=float)
    k = g_on * moment * G
    tau_hold_target = np.abs(k * np.sin(np.radians(target_deg)))
    tau_hold_target = np.where(tau_hold_target < 1e-9, 0.0, tau_hold_target)  # sin(180 deg) ~ 1e-16 is zero
    tau_hold_peak = np.abs(k) * _peak_sin(target_deg)
    with np.errstate(divide="ignore"):
        margin_target = np.where(tau_hold_target > 0, tau_avail / np.where(tau_hold_target > 0, tau_hold_target, 1.0), np.inf)
        margin_path = np.where(tau_hold_peak > 0, tau_avail / np.where(tau_hold_peak > 0, tau_hold_peak, 1.0), np.inf)
    status = np.where(margin_path < 1.0, "infeasible", np.where(margin_path < marginal_margin, "marginal", "ok"))
    return dict(tau_avail=np.broadcast_to(np.asarray(tau_avail, dtype=float), margin_path.shape).copy(), tau_hold_target=tau_hold_target,
                tau_hold_peak=tau_hold_peak, margin_target=margin_target, margin_path=margin_path, status=status)


def feasibility(cfg: dict, payload_mass_kg: float, arm_length_m: float, target_deg: float,
                gravity: bool = True, v_pct: float = 100.0, arm_mass_kg: float = 0.0,
                arm_cg_m: float = 0.0, scenario: str | None = None) -> dict:
    """Feasibility for one case from the YAML config (active scenario by default)."""
    scenario = scenario or cfg["simulation"]["active_electrical_scenario"]
    d = cfg["base_motor"]["derived"][scenario]
    tau_avail = available_torque(d["Kt_Nm_per_A"], d["R_ohm"], cfg["gearbox"]["ratio"],
                                 cfg["gearbox"]["efficiency"], cfg["supply"]["V_rated"], v_pct)
    marginal = cfg.get("feasibility", {}).get("marginal_margin", 1.2)
    out = feasibility_arrays(tau_avail, payload_mass_kg, arm_length_m, target_deg, 1.0 if gravity else 0.0,
                             arm_mass_kg, arm_cg_m, marginal)
    return {k: (v.item() if np.ndim(v) == 0 else v) for k, v in out.items()}


def warn_if_infeasible(f: dict, logger=None) -> bool:
    """Log a warning when ``f`` is infeasible or marginal. Returns True if a warning was issued."""
    import logging
    if f["status"] == "ok":
        return False
    (logger or logging.getLogger(__name__)).warning("payload torque check: %s", describe(f))
    return True


def describe(f: dict) -> str:
    """One-line human-readable summary of a ``feasibility()`` result."""
    if not np.isfinite(f["margin_path"]):
        return "torque margin: no gravity holding torque"
    s = (f"torque margin {f['margin_path']:.2f} ({f['status']}): peak hold {f['tau_hold_peak']:.2f} N*m "
         f"vs available {f['tau_avail']:.2f} N*m")
    return s
