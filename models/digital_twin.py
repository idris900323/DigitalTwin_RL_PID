"""Phase 9: closed-loop digital twin -- motor + gearbox + (bare) joint +
encoder + PID, stepped at a fixed discrete sample time.

Per-step data flow:
  encoder reads theta_out (quantized, from the PREVIOUS step's true state)
  -> PID computes voltage command (saturated to the supply limit)
  -> optional driver current limit clamps the voltage actually applied
  -> joint's external torque (gravity + friction + disturbance, all output
     side, evaluated at the true output state) reflected through the
     gearbox into the motor ODE's tau_load term
  -> motor.step() advances [i, omega_m, theta_m] one dt via discrete RK4
  -> gearbox converts the new motor state to omega_out/theta_out

No PyBullet in this loop (Phase 10, not yet implemented) -- pure Python ODE
stepping; visualization is matplotlib-based (see simulation/).
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from controllers.pid import PID
from models.dc_motor import DCMotor
from models.encoder import Encoder
from models.gearbox import Gearbox
from models.joint import Joint


@dataclass
class TwinState:
    t: float = 0.0
    motor_state: np.ndarray = field(default_factory=lambda: np.zeros(3))  # [i, omega_m, theta_m]


class DigitalTwin:
    def __init__(self, motor: DCMotor, gearbox: Gearbox, joint: Joint, encoder: Encoder, pid: PID, dt: float,
                 current_limit_A: Optional[float] = None):
        """``current_limit_A``: optional driver current limit [A] (None = no limit, the default).
        The voltage actually applied is clamped to [Ke*omega - R*I_lim, Ke*omega + R*I_lim], which limits the
        armature current exactly when L = 0 and approximately (steady-state bound) when L > 0."""
        self.current_limit_A = current_limit_A
        self.motor = motor
        self.gearbox = gearbox
        self.joint = joint
        self.encoder = encoder
        self.pid = pid
        self.dt = dt
        self.state = TwinState()

    def reset(self):
        self.state = TwinState()
        self.pid.reset()

    def step(self, theta_ref: float) -> dict:
        t = self.state.t
        theta_m = self.state.motor_state[2]
        omega_m = self.state.motor_state[1]
        theta_out_true = self.gearbox.output_position(theta_m)
        omega_out_true = self.gearbox.output_speed(omega_m)

        theta_out_meas = self.encoder.read(theta_out_true)
        error = theta_ref - theta_out_meas
        V_cmd = self.pid.step(error)

        V_applied = V_cmd
        if self.current_limit_A is not None:
            p = self.motor.p
            lo, hi = p.Ke * omega_m - p.R * self.current_limit_A, p.Ke * omega_m + p.R * self.current_limit_A
            V_applied = min(max(V_cmd, lo), hi)

        tau_out = self.joint.external_torque(t, theta_out_true, omega_out_true)
        tau_load_motor = self.gearbox.reflect_load_torque_to_motor(tau_out)

        # Armature current at the instant V_cmd is applied, i.e. from the
        # motor state at the START of this step (before the RK4 update). It is
        # consistent with V_cmd: V_cmd*i = R*i^2 + Ke*omega_m*i. For L = 0 this
        # is algebraic and not part of the state vector (see DCMotor.current).
        i_motor = self.motor.current(self.state.motor_state, V_applied)

        new_motor_state = self.motor.step(self.state.motor_state, self.dt, V_applied, tau_load_motor)
        self.state = TwinState(t=t + self.dt, motor_state=new_motor_state)

        return {
            "t": self.state.t,
            "theta_out": self.gearbox.output_position(new_motor_state[2]),
            "theta_out_meas": theta_out_meas,
            "omega_out": self.gearbox.output_speed(new_motor_state[1]),
            "error": error,
            "V_cmd": V_cmd,
            "V_applied": V_applied,
            "tau_load_out": tau_out,
            "i_motor": i_motor,
        }

    def run(self, theta_ref: float, n_steps: int) -> dict:
        """Run n_steps from the current state and return stacked arrays."""
        log = {"t": [], "theta_out": [], "theta_out_meas": [], "omega_out": [], "error": [], "V_cmd": [], "V_applied": [],
               "tau_load_out": [], "i_motor": []}
        for _ in range(n_steps):
            row = self.step(theta_ref)
            for k, v in row.items():
                log[k].append(v)
        return {k: np.array(v) for k, v in log.items()}
