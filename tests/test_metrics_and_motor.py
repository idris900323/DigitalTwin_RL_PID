"""G2.5: step-response metrics on synthetic signals with known answers, and the DC motor model."""

import math

import numpy as np
import pytest

from models.dc_motor import DCMotor, DCMotorParams
from simulation.metrics import overshoot_pct, rise_time, rmse, settling_time, steady_state_error
from tests.helpers import run_step_response

T = np.linspace(0.0, 2.0, 2001)          # dt = 1 ms


def first_order(tau, ref=90.0):
    return ref * (1 - np.exp(-T / tau))


# ----------------------------------------------------------------------------- metrics
def test_rise_time_of_first_order_response():
    tau = 0.2
    # 10-90 % rise of a first-order lag is tau*ln(9)
    assert rise_time(T, first_order(tau), 90.0) == pytest.approx(tau * math.log(9), abs=2e-3)


def test_rise_time_on_a_linear_ramp():
    y = np.clip(90.0 * T / 1.0, 0, 90.0)                 # reaches the target at t = 1 s
    assert rise_time(T, y, 90.0) == pytest.approx(0.8, abs=2e-3)


def test_overshoot_known_peak():
    y = np.full_like(T, 90.0)
    y[500] = 99.0
    assert overshoot_pct(y, 90.0) == pytest.approx(10.0)
    assert overshoot_pct(first_order(0.2), 90.0) == 0.0     # monotone response never overshoots


def test_settling_time_known_value():
    tau = 0.2
    # first-order lag enters the 2 % band at t = tau*ln(50)
    assert settling_time(T, first_order(tau), 90.0) == pytest.approx(tau * math.log(50), abs=3e-3)


def test_steady_state_error_and_rmse():
    y = np.full_like(T, 88.0)
    assert steady_state_error(y, 90.0) == pytest.approx(-2.0)
    assert rmse(y, 90.0) == pytest.approx(2.0)
    assert rmse(np.array([89.0, 91.0, 89.0, 91.0]), 90.0) == pytest.approx(1.0)


def test_never_rises():
    y = np.full_like(T, 5.0)
    assert math.isnan(rise_time(T, y, 90.0))


def test_never_settles():
    y = 90.0 + 10.0 * np.sin(2 * math.pi * 4.3 * T)      # keeps oscillating outside the 2 % band to the end
    assert math.isnan(settling_time(T, y, 90.0))


def test_already_settled_is_zero():
    assert settling_time(T, np.full_like(T, 90.0), 90.0) == 0.0


def test_zero_step_is_nan():
    y = np.zeros_like(T)
    for f in (lambda: rise_time(T, y, 0.0), lambda: overshoot_pct(y, 0.0), lambda: settling_time(T, y, 0.0)):
        assert math.isnan(f())


def test_negative_step_mirrors_positive_step():
    pos = first_order(0.2, 90.0)
    neg = -pos
    assert rise_time(T, neg, -90.0) == pytest.approx(rise_time(T, pos, 90.0))
    assert settling_time(T, neg, -90.0) == pytest.approx(settling_time(T, pos, 90.0))
    ov = pos.copy(); ov[500] = 99.0
    assert overshoot_pct(-ov, -90.0) == pytest.approx(overshoot_pct(ov, 90.0))
    assert overshoot_pct(-pos, -90.0) == 0.0
    assert steady_state_error(-np.full_like(T, 88.0), -90.0) == pytest.approx(2.0)


# ----------------------------------------------------------------------------- motor
def _motor(L=0.0):
    return DCMotor(DCMotorParams(R=1.6, L=L, Kt=1.974e-3, Ke=6.366e-3, Jm=5e-7, Bm=1e-6))


def test_open_loop_rk4_matches_solve_ivp():
    m = _motor(L=1e-3)                                    # with inductance both integrators solve the same ODE
    dt, T_end = 1e-5, 0.05
    state = np.zeros(3)
    for _ in range(int(T_end / dt)):
        state = m.step(state, dt, 12.0, 0.0)
    sol = m.simulate((0.0, T_end), np.zeros(3), lambda t: 12.0, lambda t: 0.0, t_eval=np.array([T_end]), method="Radau")
    assert state[1] == pytest.approx(sol.y[1][-1], rel=1e-4)
    assert state[0] == pytest.approx(sol.y[0][-1], rel=1e-3, abs=1e-4)


def test_open_loop_rk4_matches_solve_ivp_for_zero_inductance():
    m = _motor()
    dt, T_end = 1e-4, 0.5
    state = np.zeros(3)
    for _ in range(int(T_end / dt)):
        state = m.step(state, dt, 12.0, 0.0)
    sol = m.simulate((0.0, T_end), np.zeros(3), lambda t: 12.0, lambda t: 0.0, t_eval=np.array([T_end]))
    assert state[1] == pytest.approx(sol.y[1][-1], rel=1e-6)


def test_steady_state_no_load_speed_matches_algebra():
    p = DCMotorParams(R=1.6, L=0.0, Kt=1.974e-3, Ke=6.366e-3, Jm=5e-7, Bm=1e-6)
    m = DCMotor(p)
    state = np.zeros(3)
    for _ in range(20000):
        state = m.step(state, 1e-4, 12.0, 0.0)
    expected = 12.0 * p.Kt / (p.R * p.Bm + p.Kt * p.Ke)         # w = V*Kt / (R*Bm + Kt*Ke)
    assert state[1] == pytest.approx(expected, rel=1e-6)


def test_tiny_inductance_matches_zero_inductance():
    a, b = _motor(0.0), _motor(1e-7)
    sa = sb = np.zeros(3)
    for _ in range(5000):
        sa = a.step(sa, 1e-5, 12.0, 0.0)
        sb = b.step(sb, 1e-5, 12.0, 0.0)
    assert sb[1] == pytest.approx(sa[1], rel=1e-3)


def test_load_torque_slows_the_motor():
    m = _motor()
    free = loaded = np.zeros(3)
    for _ in range(3000):
        free = m.step(free, 1e-4, 12.0, 0.0)
        loaded = m.step(loaded, 1e-4, 12.0, 0.005)
    assert loaded[1] < free[1]


# ----------------------------------------------------------------------------- timestep convergence
def test_halving_dt_changes_metrics_by_less_than_a_stated_bound():
    a = run_step_response(15, 0, 0.3, dt=1e-3)
    b = run_step_response(15, 0, 0.3, dt=5e-4)
    assert abs(a.overshoot - b.overshoot) < 0.1                  # percentage points
    assert abs(a.settle - b.settle) < 0.005                      # seconds
    assert abs(a.theta_deg[-1] - b.theta_deg[-1]) < 0.002        # degrees
    c = run_step_response(45, 0, 0, dt=1e-3)
    d = run_step_response(45, 0, 0, dt=5e-4)
    assert abs(c.overshoot - d.overshoot) < 0.1 and abs(c.rise - d.rise) < 0.005


def test_stiff_inductance_is_substepped_and_stable():
    """L/R = 62 us is far below the 1 ms control period: plain RK4 would blow up; step() sub-steps instead."""
    stiff = _motor(L=1e-4)
    state = np.zeros(3)
    for _ in range(300):
        state = stiff.step(state, 1e-3, 12.0, 0.0)
    assert np.all(np.isfinite(state))
    ref = _motor(L=0.0)
    s0 = np.zeros(3)
    for _ in range(300):
        s0 = ref.step(s0, 1e-3, 12.0, 0.0)
    assert state[1] == pytest.approx(s0[1], rel=2e-2)             # electrical transient is fast; speeds agree closely


def test_well_resolved_inductance_takes_a_single_step(monkeypatch):
    m = _motor(L=1e-2)                                              # L/R = 6 ms >> dt
    calls = []
    orig = m._rk4
    monkeypatch.setattr(m, "_rk4", lambda *a, **k: (calls.append(1), orig(*a, **k))[1])
    m.step(np.zeros(3), 1e-3, 12.0, 0.0)
    assert len(calls) == 1


def test_too_stiff_inductance_raises_instead_of_returning_garbage():
    m = _motor(L=1e-9)                                              # L/R = 6e-10 s -> needs far more than MAX_SUBSTEPS
    with pytest.raises(RuntimeError, match="MAX_SUBSTEPS"):
        m.step(np.zeros(3), 1e-3, 12.0, 0.0)


def test_substep_cap_boundary():
    from models.dc_motor import MAX_SUBSTEPS
    tau_e = 1e-3 / (2.0 * MAX_SUBSTEPS)                              # exactly MAX_SUBSTEPS sub-steps at dt = 1 ms
    ok = _motor(L=tau_e * 1.6 * 1.0001)
    assert np.all(np.isfinite(ok.step(np.zeros(3), 1e-3, 12.0, 0.0)))
