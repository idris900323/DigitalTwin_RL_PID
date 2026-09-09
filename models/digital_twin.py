"""Phase 9: closed-loop digital twin -- motor + gearbox + (bare) joint +
encoder + PID, stepped at a fixed discrete sample time.

Per-step data flow:
  encoder reads theta_out (quantized, from the PREVIOUS step's true state)
  -> PID computes voltage command (saturated +-12V)
  -> joint's external torque (0 in this build) reflected through the
     gearbox into the motor ODE's tau_load term
  -> motor.step() advances [i, omega_m, theta_m] one dt via discrete RK4
  -> gearbox converts the new motor state to omega_out/theta_out

No PyBullet in this loop (Phase 10, not yet implemented) -- pure Python ODE
stepping; visualization is matplotlib-based (see simulation/).
"""

from dataclasses import dataclass, field

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
    def __init__(self, motor: DCMotor, gearbox: Gearbox, joint: Joint, encoder: Encoder, pid: PID, dt: float):
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
        theta_out_true = self.gearbox.output_position(theta_m)

        theta_out_meas = self.encoder.read(theta_out_true)
        error = theta_ref - theta_out_meas
        V_cmd = self.pid.step(error)

        tau_out = self.joint.external_torque(t)
        tau_load_motor = self.gearbox.reflect_load_torque_to_motor(tau_out)

        new_motor_state = self.motor.step(self.state.motor_state, self.dt, V_cmd, tau_load_motor)
        self.state = TwinState(t=t + self.dt, motor_state=new_motor_state)

        return {
            "t": self.state.t,
            "theta_out": self.gearbox.output_position(new_motor_state[2]),
            "theta_out_meas": theta_out_meas,
            "omega_out": self.gearbox.output_speed(new_motor_state[1]),
            "error": error,
            "V_cmd": V_cmd,
            "i_motor": new_motor_state[0],
        }

    def run(self, theta_ref: float, n_steps: int) -> dict:
        """Run n_steps from the current state and return stacked arrays."""
        log = {"t": [], "theta_out": [], "theta_out_meas": [], "omega_out": [], "error": [], "V_cmd": [], "i_motor": []}
        for _ in range(n_steps):
            row = self.step(theta_ref)
            for k, v in row.items():
                log[k].append(v)
        return {k: np.array(v) for k, v in log.items()}
