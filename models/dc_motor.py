"""Phase 4: DC motor electrical + mechanical ODE (base motor side only).

No gearbox, no joint, no encoder here -- those are separate modules
(gearbox.py, joint.py, encoder.py). This module must not be used to
represent output-side (post-gearbox) quantities.

State vector x = [i, omega_m, theta_m]:
    i       armature current [A]
    omega_m motor angular velocity [rad/s]
    theta_m motor shaft angle [rad] (tracked here since it does not feed
             back into the electrical/mechanical ODE, but downstream
             modules -- gearbox/joint/encoder/PID -- need it)

Equations (all SI):
    V = R*i + L*(di/dt) + Ke*omega_m
    Jm*(domega_m/dt) = Kt*i - Bm*omega_m - tau_load
    dtheta_m/dt = omega_m
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.integrate import solve_ivp


@dataclass
class DCMotorParams:
    R: float          # ohm
    L: float           # H
    Kt: float          # N*m/A
    Ke: float          # V*s/rad
    Jm: float          # kg*m^2
    Bm: float          # N*m*s/rad


class DCMotor:
    """Base-motor-side electrical + mechanical dynamics only."""

    def __init__(self, params: DCMotorParams):
        self.p = params

    def current(self, state: np.ndarray, V: float) -> float:
        """Armature current [A] at ``state`` under applied voltage ``V``.

        L > 0: the current is a state variable, so this returns ``state[0]``.
        L = 0 (ASSUMED, see config): electrical dynamics collapse to the
        algebraic relation ``i = (V - Ke*omega_m) / R``, which is *not* stored
        in the state vector -- use this method to read it.
        """
        if self.p.L > 0.0:
            return float(state[0])
        return float((V - self.p.Ke * state[1]) / self.p.R)

    def derivatives(self, t: float, state: np.ndarray, V: float, tau_load: float) -> np.ndarray:
        _i, omega_m, _theta_m = state
        p = self.p
        i = self.current(state, V)
        if p.L > 0.0:
            di_dt = (V - p.R * i - p.Ke * omega_m) / p.L
        else:
            di_dt = 0.0
        domega_dt = (p.Kt * i - p.Bm * omega_m - tau_load) / p.Jm
        dtheta_dt = omega_m
        return np.array([di_dt, domega_dt, dtheta_dt])

    def simulate(
        self,
        t_span: tuple[float, float],
        x0: np.ndarray,
        V_func: Callable[[float], float],
        tau_load_func: Callable[[float], float],
        t_eval: np.ndarray | None = None,
        method: str = "RK45",
    ):
        """Continuous-time, open-loop simulation via scipy.integrate.solve_ivp.

        Adaptive-step solve_ivp is appropriate here for characterizing the
        plant on its own (Phase 4 sanity checks). It is NOT used for the
        closed-loop digital twin -- see step() below.
        """

        def ode(t, state):
            return self.derivatives(t, state, V_func(t), tau_load_func(t))

        return solve_ivp(
            ode,
            t_span,
            x0,
            method=method,
            t_eval=t_eval,
            max_step=1.0e-4,
        )

    def step(self, state: np.ndarray, dt: float, V: float, tau_load: float) -> np.ndarray:
        """Discrete fixed-step update via classic 4th-order Runge-Kutta.

        A real-time closed-loop controller runs on a fixed sample time (the
        PID's dt), not an adaptive solver step -- so the closed-loop digital
        twin (Phase 9) uses this instead of simulate()/solve_ivp. RK4 is used
        (rather than forward Euler) because it is 4th-order accurate at a
        modest cost (4 derivative evaluations/step), which matters here since
        V and tau_load are held constant only within a single dt and the
        electrical/mechanical time constants are not known to be large
        relative to dt.
        """
        k1 = self.derivatives(0.0, state, V, tau_load)
        k2 = self.derivatives(0.0, state + 0.5 * dt * k1, V, tau_load)
        k3 = self.derivatives(0.0, state + 0.5 * dt * k2, V, tau_load)
        k4 = self.derivatives(0.0, state + dt * k3, V, tau_load)
        return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
