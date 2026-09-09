"""Phase 5: ideal fixed-ratio gearbox.

No compliance/backlash modeled (master prompt \xa77: "start simple, no
gearbox compliance/backlash unless it becomes necessary"). Efficiency only
matters when reflecting an output-side load torque back to the motor shaft;
it has no effect while tau_out = 0 (this build's bare-shaft scope).
"""

from dataclasses import dataclass


@dataclass
class GearboxParams:
    ratio: float             # N, motor turns per output turn. DATASHEET: 180
    efficiency: float = 1.0  # ESTIMATED (0.70-0.85 typical); only affects load reflection


class Gearbox:
    def __init__(self, params: GearboxParams):
        self.p = params

    def output_speed(self, omega_m: float) -> float:
        return omega_m / self.p.ratio

    def output_position(self, theta_m: float) -> float:
        return theta_m / self.p.ratio

    def reflect_load_torque_to_motor(self, tau_out: float) -> float:
        """tau_motor = tau_out / (N * eta). Unexercised while tau_out = 0."""
        return tau_out / (self.p.ratio * self.p.efficiency)
