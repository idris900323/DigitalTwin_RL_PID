"""Build the closed-loop digital twin from the YAML config (single place that wires models together).

All plant/controller constants come from ``config/motor_parameters.yaml``; nothing here hard-codes a
motor value. Used by the demos, the tests and the cross-implementation checks.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from controllers.pid import PID, PIDParams
from models.dc_motor import DCMotor, DCMotorParams
from models.digital_twin import DigitalTwin
from models.encoder import Encoder, EncoderParams
from models.gearbox import Gearbox, GearboxParams
from models.joint import Joint, JointParams

_UNSET = object()


def build_twin_from_config(
    cfg: dict, Kp: float, Ki: float, Kd: float, *,
    scenario: Optional[str] = None,
    joint: Optional[Joint] = None,
    v_pct: float = 100.0,
    noise_counts: Optional[float] = None,
    seed: int = 0,
    dt: Optional[float] = None,
    extra_Jm_kgm2: float = 0.0,
    current_limit_A=_UNSET,
    delay_steps=_UNSET,
) -> DigitalTwin:
    """Closed-loop twin for one scenario.

    scenario        electrical parameter set (method_a/b/c/...); default = ``simulation.active_electrical_scenario``
    joint           load model; default = the YAML ``joint:`` section (everything off unless configured)
    v_pct           motor speed limit as a percent of the supply voltage (a voltage cap on the PID output)
    noise_counts    RMS encoder jitter in counts; default = YAML ``encoder.noise_counts_rms`` (0)
    extra_Jm_kgm2   additional motor-side inertia, on top of the joint's reflected inertia
    current_limit_A optional driver current limit; default = YAML ``driver.current_limit_A`` (None)
    delay_steps     command latency in control samples; default = YAML ``driver.delay_steps`` (0)
    """
    scenario = scenario or cfg["simulation"]["active_electrical_scenario"]
    d = cfg["base_motor"]["derived"][scenario]
    e = cfg["base_motor"]["estimated"]
    ratio = cfg["gearbox"]["ratio"]
    joint = joint if joint is not None else Joint(JointParams.from_config(cfg))
    dt = dt if dt is not None else cfg["simulation"]["control_loop_dt_s"]
    cpr = cfg["encoder"]["output_cpr"]
    noise = cfg["encoder"].get("noise_counts_rms", 0.0) if noise_counts is None else noise_counts
    if current_limit_A is _UNSET:
        current_limit_A = cfg.get("driver", {}).get("current_limit_A")

    if delay_steps is _UNSET:
        delay_steps = cfg.get("driver", {}).get("delay_steps", 0)

    motor = DCMotor(DCMotorParams(
        R=d["R_ohm"], L=e["L_H"], Kt=d["Kt_Nm_per_A"], Ke=d["Ke_V_s_per_rad"],
        Jm=e["Jm_kgm2"] + extra_Jm_kgm2 + joint.reflected_inertia(ratio), Bm=d.get("Bm_Nms_per_rad", e["Bm_Nms_per_rad"])))
    # an alternative parameter set may carry its own Bm and gearbox efficiency (method_d*); the active sets use the global ones
    gearbox = Gearbox(GearboxParams(ratio=ratio, efficiency=d.get("gearbox_efficiency", cfg["gearbox"]["efficiency"])))
    encoder = Encoder(EncoderParams(counts_per_rev=cpr, noise_std_rad=noise * 2.0 * math.pi / cpr),
                      np.random.default_rng(seed))
    vmax = cfg["supply"]["V_rated"] * v_pct / 100.0
    pid = PID(PIDParams(Kp=Kp, Ki=Ki, Kd=Kd, dt=dt, output_min=-vmax, output_max=vmax,
                        derivative_filter_tau=cfg.get("controller", {}).get("derivative_filter_tau_s", 0.01)))
    return DigitalTwin(motor=motor, gearbox=gearbox, joint=joint, encoder=encoder, pid=pid, dt=dt,
                       current_limit_A=current_limit_A, delay_steps=delay_steps)
