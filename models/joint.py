"""Phase 6: single revolute joint -- arm/payload inertia, gravity, friction and disturbances.

Everything is output-shaft side and SI. Every term defaults to OFF (zero) because the real values are
unknown (provenance: ASSUMED / UNKNOWN in config/motor_parameters.yaml `joint:`).

Conventions (must match the browser page and the trainer exactly):
  * theta_out = 0 means the arm hangs straight down; gravity acts in a vertical plane, so the gravity
    torque the load exerts on the output shaft is  tau_g = (m_payload*L + m_arm*L_cg) * g * sin(theta).
    Positive torque OPPOSES positive rotation (it is a load torque, the `tau_load` side of the motor ODE).
  * Payload is a point mass at the arm tip (distance L from the pivot): J = m_payload * L^2.
  * The arm itself (optional) is a uniform thin rod of mass m_arm and length L: J = m_arm * L^2 / 3,
    centre of gravity L/2 (override with arm_cg_m).
  * Inertia is reflected to the MOTOR shaft as J_out / N^2 (the demos use the same m*L^2/ratio^2 form).
  * Friction: viscous B_joint*omega_out and smooth Coulomb tau_c*tanh(omega_out/omega_eps); the smooth sign
    avoids a discontinuity that would upset fixed-step RK4.

Not implemented (TODO, deliberately OFF everywhere): gearbox backlash (dead zone) and torsional
compliance. They have no parameters in the YAML yet; add them with tests when sim-to-real work needs them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional

G = 9.81  # m/s^2


@dataclass
class JointParams:
    """Payload, arm, gravity and friction parameters of the joint (all default to off)."""
    payload_mass_kg: float = 0.0
    arm_length_m: float = 0.0
    arm_mass_kg: float = 0.0
    arm_cg_m: Optional[float] = None      # None -> L/2 (uniform rod)
    gravity_on: bool = False
    B_joint: float = 0.0                  # N*m*s/rad, UNKNOWN (0 = off)
    tau_coulomb: float = 0.0              # N*m, UNKNOWN (0 = off)
    omega_eps: float = 0.01               # rad/s, width of the smooth sign function

    @classmethod
    def from_config(cls, cfg: dict, **overrides) -> "JointParams":
        """Read the YAML `joint:` section; keyword overrides win (e.g. payload_mass_kg=1.0)."""
        j = dict(cfg.get("joint", {}))
        base = dict(
            payload_mass_kg=j.get("payload_mass_kg", 0.0), arm_length_m=j.get("arm_length_m", 0.0),
            arm_mass_kg=j.get("arm_mass_kg", 0.0), arm_cg_m=j.get("arm_cg_m"),
            gravity_on=bool(j.get("gravity_on", False)), B_joint=j.get("B_joint_Nms_per_rad", 0.0),
            tau_coulomb=j.get("tau_coulomb_Nm", 0.0), omega_eps=j.get("omega_eps_rad_s", 0.01))
        base.update(overrides)
        return cls(**base)


class Joint:
    """Output-side load model: arm/payload inertia, gravity, friction and a disturbance hook."""
    def __init__(self, params: Optional[JointParams] = None,
                 disturbance: Optional[Callable[[float], float]] = None,
                 external_torque_func: Optional[Callable[[float], float]] = None):
        """``disturbance`` / ``external_torque_func``: callable t -> N*m added to the output-side load torque
        (see models/disturbances.py). ``external_torque_func`` is the old name, kept for compatibility."""
        self.p = params or JointParams()
        self.disturbance = disturbance or external_torque_func or (lambda t: 0.0)

    # --- geometry ----------------------------------------------------------------------------
    @property
    def arm_cg(self) -> float:
        """Arm centre-of-gravity distance from the pivot [m]."""
        p = self.p
        return p.arm_length_m / 2.0 if p.arm_cg_m is None else p.arm_cg_m

    def output_inertia(self) -> float:
        """Total load inertia about the output shaft [kg*m^2] (payload point mass + thin-rod arm)."""
        p = self.p
        return p.payload_mass_kg * p.arm_length_m ** 2 + p.arm_mass_kg * p.arm_length_m ** 2 / 3.0

    def reflected_inertia(self, ratio: float) -> float:
        """Load inertia reflected to the motor shaft [kg*m^2] = J_out / N^2."""
        return self.output_inertia() / ratio ** 2

    def gravity_moment(self) -> float:
        """(m_payload*L + m_arm*L_cg) [kg*m], the lever for gravity torque (0 if gravity is off)."""
        p = self.p
        if not p.gravity_on:
            return 0.0
        return p.payload_mass_kg * p.arm_length_m + p.arm_mass_kg * self.arm_cg

    # --- torques -----------------------------------------------------------------------------
    def gravity_torque(self, theta_out: float) -> float:
        """Gravity torque [N*m] on the output shaft at angle theta_out [rad] (0 = hanging)."""
        return self.gravity_moment() * G * math.sin(theta_out)

    def friction_torque(self, omega_out: float) -> float:
        """Viscous + smooth Coulomb friction torque [N*m] at output speed omega_out [rad/s]."""
        p = self.p
        tau = p.B_joint * omega_out
        if p.tau_coulomb != 0.0:
            tau += p.tau_coulomb * math.tanh(omega_out / p.omega_eps)
        return tau

    def external_torque(self, t: float, theta_out: float = 0.0, omega_out: float = 0.0) -> float:
        """Total load torque on the output shaft [N*m], positive = opposes positive rotation."""
        return self.gravity_torque(theta_out) + self.friction_torque(omega_out) + self.disturbance(t)
