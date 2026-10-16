"""Phase 8: fixed-gain PID with voltage saturation, conditional-integration
anti-windup, and a filtered derivative term. Fixed discrete sample time
(matches the digital twin's control_loop_dt_s), per master prompt \xa715.
"""

from dataclasses import dataclass


@dataclass
class PIDParams:
    Kp: float
    Ki: float
    Kd: float
    dt: float
    output_min: float                    # V, physical supply limit: from the YAML (supply.V_rated), no default
    output_max: float
    derivative_filter_tau: float = 0.01  # s, ASSUMED, first-order filter on D term


class PID:
    def __init__(self, params: PIDParams):
        self.p = params
        self.integral = 0.0
        self.prev_error = 0.0
        self.filtered_derivative = 0.0

    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0
        self.filtered_derivative = 0.0

    def step(self, error: float) -> float:
        p = self.p

        raw_derivative = (error - self.prev_error) / p.dt
        alpha = p.dt / (p.derivative_filter_tau + p.dt)
        self.filtered_derivative += alpha * (raw_derivative - self.filtered_derivative)

        tentative_integral = self.integral + error * p.dt
        u_unsat = p.Kp * error + p.Ki * tentative_integral + p.Kd * self.filtered_derivative

        if u_unsat > p.output_max:
            u = p.output_max
            if error > 0.0:            # integrating further would only deepen saturation
                tentative_integral = self.integral
        elif u_unsat < p.output_min:
            u = p.output_min
            if error < 0.0:
                tentative_integral = self.integral
        else:
            u = u_unsat

        self.integral = tentative_integral
        self.prev_error = error
        return u
