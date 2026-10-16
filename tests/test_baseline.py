"""Task 0.2: pin the baseline numbers measured in PROJECT_OVERVIEW.md.

These must pass on a clean checkout before any fix; later changes are
checked against them. Bare shaft, method_c, 90 deg step, 2 s, dt = 1 ms.
"""

import math

import numpy as np
import pytest

from models.dc_motor import DCMotor, DCMotorParams
from models.units import gcm_to_Nm, kgcm_to_Nm, rad_s_to_rpm, rpm_to_rad_s
from tests.helpers import run_step_response

NAN = float("nan")

# name, (Kp, Ki, Kd), rise_s, overshoot_pct, settle_s (nan = never), sse_deg
CASES = [
    ("low P", (1.5, 0, 0), 1.765, 0.0, NAN, -7.99),
    ("mid P", (15, 0, 0), 0.171, 6.65, 0.467, -0.003),
    ("high P", (45, 0, 0), 0.157, 11.2, 0.459, 0.012),
    ("P+D (Tuned)", (15, 0, 0.3), 0.190, 1.73, 0.292, -0.011),
    ("P+I", (15, 20, 0), 0.169, 9.72, 0.531, 0.145),
    ("PID (legacy default)", (5, 20, 0.05), 0.223, 42.2, 1.826, 1.351),
    ("PID", (15, 5, 0.3), 0.188, 3.04, 0.514, 0.690),
]


@pytest.mark.parametrize("name,gains,rise,os_,settle,sse", CASES, ids=[c[0] for c in CASES])
def test_closed_loop_baseline(name, gains, rise, os_, settle, sse):
    r = run_step_response(*gains)
    assert r.rise == pytest.approx(rise, abs=0.005)
    assert r.overshoot == pytest.approx(os_, abs=0.1)
    if math.isnan(settle):
        assert math.isnan(r.settle)
    else:
        assert r.settle == pytest.approx(settle, abs=0.005)
    assert r.sse_deg == pytest.approx(sse, abs=0.01)


def _motor(cfg, method, Jm=None):
    d = cfg["base_motor"]["derived"][method]
    e = cfg["base_motor"]["estimated"]
    return DCMotor(DCMotorParams(R=d["R_ohm"], L=0.0, Kt=d["Kt_Nm_per_A"], Ke=d["Ke_V_s_per_rad"],
                                 Jm=Jm or e["Jm_kgm2"], Bm=e["Bm_Nms_per_rad"]))


def _no_load_rpm(cfg, method):
    m = _motor(cfg, method)
    sol = m.simulate((0.0, 0.5), np.zeros(3), lambda t: cfg["supply"]["V_rated"], lambda t: 0.0)
    return rad_s_to_rpm(sol.y[1][-1])


def test_open_loop_no_load_speed(cfg):
    assert _no_load_rpm(cfg, "method_a") == pytest.approx(39827, rel=2e-3)
    assert _no_load_rpm(cfg, "method_c") == pytest.approx(15965, rel=2e-3)
    ke_b = cfg["base_motor"]["derived"]["method_b"]["Ke_V_s_per_rad"]
    assert rad_s_to_rpm(cfg["supply"]["V_rated"] / ke_b) == pytest.approx(18000.6, abs=0.2)
    pct_a = 100 * (_no_load_rpm(cfg, "method_a") - 18000) / 18000
    pct_c = 100 * (_no_load_rpm(cfg, "method_c") - 18000) / 18000
    assert pct_a == pytest.approx(121.3, abs=0.3)
    assert pct_c == pytest.approx(-11.3, abs=0.3)


@pytest.mark.parametrize("method,tau_ms", [("method_c", 56.0), ("method_a", 146.0)])
def test_mechanical_time_constant(cfg, method, tau_ms):
    d = cfg["base_motor"]["derived"][method]
    e = cfg["base_motor"]["estimated"]
    tau = e["Jm_kgm2"] / (e["Bm_Nms_per_rad"] + d["Kt_Nm_per_A"] * d["Ke_V_s_per_rad"] / d["R_ohm"])
    assert tau * 1e3 == pytest.approx(tau_ms, abs=0.6)


def test_unit_helpers():
    assert rpm_to_rad_s(18000) == pytest.approx(1884.96, abs=0.01)
    assert kgcm_to_Nm(27.18) == pytest.approx(2.6654, abs=1e-4)
    assert gcm_to_Nm(151) == pytest.approx(0.014808, abs=1e-6)
    assert rad_s_to_rpm(rpm_to_rad_s(100)) == pytest.approx(100)


def test_timestep_convergence():
    finals = [run_step_response(15, 0, 0.3, dt=dt).theta_deg[-1] for dt in (5e-4, 1e-3, 2e-3)]
    assert finals == pytest.approx([89.989, 89.989, 89.990], abs=0.002)


def test_method_a_vs_c_legacy_gains():
    a = run_step_response(5, 20, 0.05, params="method_a")
    c = run_step_response(5, 20, 0.05, params="method_c")
    assert a.overshoot == pytest.approx(66.8, abs=0.3)
    assert math.isnan(a.settle)
    assert c.overshoot == pytest.approx(42.2, abs=0.1)
