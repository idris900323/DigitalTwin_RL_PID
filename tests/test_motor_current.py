"""G1.1: the armature current must be logged, not silently zero, when L = 0."""

import copy
import math

import numpy as np
import pytest

from models.dc_motor import DCMotor, DCMotorParams
from simulation.interactive_pid_twin import build_twin
from tests.helpers import run_step_response


def test_tuned_step_peak_current_is_real_and_bounded():
    r = run_step_response(15, 0, 0.3)
    peak = float(np.max(np.abs(r.i)))
    assert peak > 0.0
    assert peak <= 12.0 / 1.6 + 1e-9  # stall current = V / R = 7.5 A


def test_logged_current_matches_algebraic_relation(cfg):
    """i == (V_cmd - Ke*omega_m)/R with omega_m taken at the start of the step."""
    cfg = copy.deepcopy(cfg)
    d = cfg["base_motor"]["derived"]["method_c"]
    twin = build_twin(cfg, 15, 0, 0.3)
    ratio = cfg["gearbox"]["ratio"]
    omega_m_start = 0.0
    for k in range(400):
        row = twin.step(math.radians(90))
        expected = (row["V_cmd"] - d["Ke_V_s_per_rad"] * omega_m_start) / d["R_ohm"]
        assert row["i_motor"] == pytest.approx(expected, rel=1e-12, abs=1e-12), k
        omega_m_start = row["omega_out"] * ratio  # next step starts from this state


def test_electrical_power_balance(cfg):
    """V*i = R*i^2 + Ke*omega_m*i (copper loss + back-EMF power) at every step."""
    d = cfg["base_motor"]["derived"]["method_c"]
    r = run_step_response(15, 0, 0.3)
    ratio = cfg["gearbox"]["ratio"]
    omega_m_start = np.concatenate([[0.0], r.log["omega_out"][:-1] * ratio])
    V, i = r.V, r.i
    lhs = V * i
    rhs = d["R_ohm"] * i ** 2 + d["Ke_V_s_per_rad"] * omega_m_start * i
    assert np.allclose(lhs, rhs, rtol=1e-9, atol=1e-9)


def test_inductive_path_uses_state_current():
    p = DCMotorParams(R=1.6, L=1e-3, Kt=1.974e-3, Ke=6.366e-3, Jm=5e-7, Bm=1e-6)
    m = DCMotor(p)
    state = np.array([2.5, 100.0, 0.0])
    assert m.current(state, V=12.0) == 2.5  # taken from the state, not the algebraic formula
    # the state current actually evolves: di/dt = (V - R*i - Ke*w)/L
    d = m.derivatives(0.0, state, 12.0, 0.0)
    assert d[0] == pytest.approx((12.0 - 1.6 * 2.5 - 6.366e-3 * 100.0) / 1e-3)
    s1 = m.step(state, 1e-5, 12.0, 0.0)
    assert s1[0] > state[0]


def test_inductive_converges_to_algebraic_when_L_tiny():
    base = dict(R=1.6, Kt=1.974e-3, Ke=6.366e-3, Jm=5e-7, Bm=1e-6)
    a = DCMotor(DCMotorParams(L=0.0, **base))
    b = DCMotor(DCMotorParams(L=1e-6, **base))
    sa = a.simulate((0, 0.05), np.zeros(3), lambda t: 12.0, lambda t: 0.0, t_eval=np.array([0.05]))
    sb = b.simulate((0, 0.05), np.zeros(3), lambda t: 12.0, lambda t: 0.0, t_eval=np.array([0.05]), method="Radau")
    assert sb.y[1][-1] == pytest.approx(sa.y[1][-1], rel=2e-3)
