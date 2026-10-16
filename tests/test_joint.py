"""G2.2: joint model (inertia, gravity, friction, disturbance) and the optional driver current limit."""

import copy
import math

import numpy as np
import pytest

from models import disturbances
from models.factory import build_twin_from_config
from models.feasibility import feasibility
from models.joint import G, Joint, JointParams
from simulation.metrics import overshoot_pct, settling_time

TUNED = (15, 0, 0.3)


def _step(cfg, joint=None, gains=TUNED, target_deg=90.0, t_end=2.0, **kw):
    tw = build_twin_from_config(cfg, *gains, joint=joint, **kw)
    n = int(round(t_end / tw.dt))
    return tw, tw.run(math.radians(target_deg), n)


@pytest.mark.parametrize("m,L,os_,settle", [(0.0, 0.0, 1.73, 0.292), (0.5, 0.10, 4.75, 0.512), (2.0, 0.15, 22.4, 1.198)])
def test_arm_inertia_reproduces_overview_table(cfg, m, L, os_, settle):
    joint = Joint(JointParams(payload_mass_kg=m, arm_length_m=L))
    _, log = _step(cfg, joint)
    y = np.degrees(log["theta_out"])
    assert overshoot_pct(y, 90.0) == pytest.approx(os_, abs=0.2)
    assert settling_time(log["t"], y, 90.0) == pytest.approx(settle, abs=0.01)


def test_default_joint_is_all_off(cfg):
    j = Joint(JointParams.from_config(cfg))
    assert j.output_inertia() == 0 and j.gravity_moment() == 0 and j.external_torque(0.0, 1.0, 5.0) == 0


def test_inertia_conventions():
    j = Joint(JointParams(payload_mass_kg=0.5, arm_length_m=0.10, arm_mass_kg=0.3))
    assert j.output_inertia() == pytest.approx(0.5 * 0.01 + 0.3 * 0.01 / 3)       # point mass + thin rod
    assert j.reflected_inertia(180.0) == pytest.approx(j.output_inertia() / 180.0 ** 2)


def test_gravity_torque_analytic_at_90deg_and_sign(cfg):
    p = JointParams(payload_mass_kg=1.0, arm_length_m=0.10, arm_mass_kg=0.2, gravity_on=True)
    j = Joint(p)
    expected = (1.0 * 0.10 + 0.2 * 0.05) * G                                       # arm CG at L/2
    assert j.gravity_torque(math.pi / 2) == pytest.approx(expected)
    assert j.gravity_torque(0.0) == pytest.approx(0.0, abs=1e-12)                  # hanging
    assert j.gravity_torque(math.pi) == pytest.approx(0.0, abs=1e-9)               # straight up (unstable equilibrium)
    assert j.gravity_torque(-math.pi / 2) == pytest.approx(-expected)              # opposes motion on the other side
    # through the twin: at theta_out = 90 deg with zero command the logged load torque is the analytic value
    tw = build_twin_from_config(cfg, 0, 0, 0, joint=j)
    tw.state.motor_state[2] = (math.pi / 2) * cfg["gearbox"]["ratio"]
    row = tw.step(0.0)
    assert row["tau_load_out"] == pytest.approx(expected, rel=1e-9)


def _pendulum_energy(j, J, theta0, T=1.0, dt=1e-4, B=0.0):
    """RK4 of the bare joint (no motor): J*w' = -tau_g(theta) - B*w. Returns energies over time."""
    def f(th, w):
        return w, (-j.gravity_torque(th) - B * w) / J
    th, w = theta0, 0.0
    E = []
    for _ in range(int(T / dt)):
        E.append(0.5 * J * w * w - j.gravity_moment() * G * math.cos(th))
        k1 = f(th, w)
        k2 = f(th + .5 * dt * k1[0], w + .5 * dt * k1[1])
        k3 = f(th + .5 * dt * k2[0], w + .5 * dt * k2[1])
        k4 = f(th + dt * k3[0], w + dt * k3[1])
        th += dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        w += dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
    return np.array(E), th


def test_pendulum_conserves_energy_without_dissipation_and_decays_with_it():
    j = Joint(JointParams(payload_mass_kg=0.5, arm_length_m=0.15, gravity_on=True))
    J = j.output_inertia()
    E, _ = _pendulum_energy(j, J, math.radians(60))
    assert abs(E[-1] - E[0]) / abs(E[0]) < 1e-6                                     # conservative
    # small-angle natural frequency squared = m g L / J = g / L for a point mass
    assert j.gravity_moment() * G / J == pytest.approx(G / 0.15)
    Ed, _ = _pendulum_energy(j, J, math.radians(60), B=0.05)
    assert np.all(np.diff(Ed) <= 1e-12)                                             # energy only decays through friction
    assert Ed[-1] < Ed[0]


def test_friction_terms():
    j = Joint(JointParams(B_joint=0.02, tau_coulomb=0.05, omega_eps=0.01))
    assert j.friction_torque(0.0) == 0.0
    assert j.friction_torque(1.0) == pytest.approx(0.02 + 0.05 * math.tanh(100.0))
    assert j.friction_torque(-1.0) == pytest.approx(-j.friction_torque(1.0))        # odd function
    assert 0 < j.friction_torque(0.001) < 0.02 * 0.001 + 0.05 * 0.1 + 1e-9          # smooth near zero


def test_friction_slows_the_response(cfg):
    base = _step(cfg)[1]
    fr = _step(cfg, Joint(JointParams(B_joint=0.05, tau_coulomb=0.05)))[1]
    assert fr["theta_out"][100] < base["theta_out"][100]


def test_disturbance_generators():
    assert disturbances.step(0.5, 1.0)(0.4) == 0 and disturbances.step(0.5, 1.0)(0.5) == 1.0
    assert disturbances.ramp(1.0, 2.0)(1.5) == pytest.approx(1.0)
    assert disturbances.pulse(1.0, 0.2, 3.0)(1.1) == 3.0 and disturbances.pulse(1.0, 0.2, 3.0)(1.2) == 0.0
    assert disturbances.sinusoid(2.0, 1.0)(0.25) == pytest.approx(2.0)
    assert disturbances.combine(disturbances.step(0, 1), disturbances.step(0, 2))(1.0) == 3.0


def test_disturbance_steady_state_error_matches_analytic(cfg):
    """P-only control, constant load torque: e_ss = tau * R / (Kt * N * eta * Kp)."""
    tau, Kp = 0.2, 20.0
    d = cfg["base_motor"]["derived"][cfg["simulation"]["active_electrical_scenario"]]
    expected_deg = math.degrees(
        tau * d["R_ohm"] / (d["Kt_Nm_per_A"] * cfg["gearbox"]["ratio"] * cfg["gearbox"]["efficiency"] * Kp))
    _, log = _step(cfg, Joint(disturbance=disturbances.step(0.0, tau)), gains=(Kp, 0, 0), t_end=3.0)
    sse = 90.0 - np.degrees(log["theta_out"][-1])
    assert sse == pytest.approx(expected_deg, rel=0.03)


def test_pulse_disturbance_recovers(cfg):
    _, log = _step(cfg, Joint(disturbance=disturbances.pulse(1.0, 0.1, 0.5)), t_end=3.0)
    y = np.degrees(log["theta_out"])
    assert abs(y[-1] - 90.0) < 0.5 and np.min(y[1000:1200]) < 89.9                  # deflected, then recovered


def test_driver_current_limit(cfg):
    free_tw, free = _step(cfg)
    _, lim = _step(cfg, current_limit_A=2.0)
    assert np.max(np.abs(free["i_motor"])) == pytest.approx(7.5, abs=1e-6)
    assert np.max(np.abs(lim["i_motor"])) <= 2.0 + 1e-9
    assert np.max(np.abs(lim["i_motor"])) == pytest.approx(2.0, abs=1e-6)           # actually reaches the limit
    assert np.any(lim["V_applied"] != lim["V_cmd"])                                  # the driver clamped the voltage
    assert lim["theta_out"][300] < free["theta_out"][300]                            # so it is slower
    assert free_tw.current_limit_A is None
    base = _step(cfg, current_limit_A=None)[1]                                      # no limit -> identical to baseline
    assert np.array_equal(base["theta_out"], free["theta_out"])


def test_current_limit_lowers_feasibility_margin(cfg):
    c = copy.deepcopy(cfg)
    free = feasibility(c, 1.0, 0.10, 90.0)
    c["driver"]["current_limit_A"] = 3.0
    lim = feasibility(c, 1.0, 0.10, 90.0)
    assert lim["tau_avail"] == pytest.approx(free["tau_avail"] * 3.0 / 7.5)
    assert lim["margin_path"] < free["margin_path"]
