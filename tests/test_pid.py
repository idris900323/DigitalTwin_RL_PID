"""G2.5: PID controller -- saturation, anti-windup, derivative filter, gain changes, reset."""

import math

import pytest

from controllers.pid import PID, PIDParams

DT = 1e-3


def make(Kp=1.0, Ki=0.0, Kd=0.0, vmax=12.0, tau=0.01):
    return PID(PIDParams(Kp=Kp, Ki=Ki, Kd=Kd, dt=DT, output_min=-vmax, output_max=vmax, derivative_filter_tau=tau))


def test_pid_params_require_output_limits():
    with pytest.raises(TypeError):
        PIDParams(Kp=1, Ki=0, Kd=0, dt=DT)


def test_proportional_only_and_saturation():
    pid = make(Kp=2.0)
    assert pid.step(1.0) == pytest.approx(2.0)
    assert make(Kp=2.0).step(100.0) == 12.0
    assert make(Kp=2.0).step(-100.0) == -12.0
    assert make(Kp=2.0, vmax=5.0).step(100.0) == 5.0


def test_integral_accumulates_error_times_dt():
    pid = make(Kp=0.0, Ki=10.0)
    for _ in range(100):
        u = pid.step(1.0)
    assert u == pytest.approx(10.0 * 100 * DT)           # Ki * integral(e dt) = 10 * 0.1


def test_anti_windup_stops_integrating_while_saturated_and_resumes():
    pid = make(Kp=1.0, Ki=10.0)
    for _ in range(300):
        pid.step(5.0)                                     # P gives 5 V; the integral term pushes u past 12 V at I ~ 0.7
    frozen = pid.integral
    assert frozen == pytest.approx(0.7, abs=0.01)
    assert pid.step(5.0) == 12.0                          # saturated
    for _ in range(500):
        pid.step(5.0)
    assert pid.integral == frozen                         # did not wind up further while saturated
    assert 5.0 * 0.8 > 3.5                                # (an unclamped integral would be ~4.0 after 0.8 s)
    # reversing the error: integral resumes immediately and the output leaves saturation with no windup delay
    u = pid.step(-5.0)
    assert u == pytest.approx(-5.0 + 10.0 * (frozen - 5.0 * DT)) and -12.0 < u < 12.0
    assert pid.integral < frozen


def test_derivative_filter_step_response_matches_first_order_lag():
    """Constant error rate of 1 /s: the filtered derivative output follows 1 - (tau/(tau+dt))^n ~ 1 - exp(-t/tau)."""
    tau = 0.01
    pid = make(Kp=0.0, Kd=1.0, tau=tau)
    err, outs = 0.0, []
    for n in range(1, 101):
        err += DT * 1.0                                    # e(t) = t
        outs.append(pid.step(err))
    for n in (1, 5, 10, 30, 100):
        discrete = 1 - (tau / (tau + DT)) ** n
        assert outs[n - 1] == pytest.approx(discrete, rel=1e-9)
    t63 = next(i for i, u in enumerate(outs, 1) if u >= 1 - math.exp(-1)) * DT
    assert t63 == pytest.approx(tau, abs=3 * DT)           # time constant is tau within a few samples
    assert outs[-1] == pytest.approx(1 - math.exp(-100 * DT / tau), abs=0.01)


def test_gain_change_takes_effect_immediately_and_is_documented_non_bumpless_for_ki():
    """The integral state is the plain integral of e (not Ki*integral), so changing Kp or Kd acts at once and
    changing Ki rescales the accumulated integral term in one step. This is by design for the fixed-gain twin,
    but a gain-adapting controller (RL, G4) must either rate-limit Ki changes or store the integral of Ki*e."""
    pid = make(Kp=1.0, Ki=10.0)
    for _ in range(200):
        u_before = pid.step(1.0)
    integral = pid.integral
    pid.p.Kp = 3.0
    assert pid.step(1.0) == pytest.approx(3.0 * 1.0 + 10.0 * (integral + DT))        # Kp change: immediate, = formula
    pid2 = make(Kp=1.0, Ki=10.0)
    for _ in range(200):
        pid2.step(1.0)
    i2 = pid2.integral
    pid2.p.Ki = 40.0
    u_after = pid2.step(1.0)
    assert u_after == pytest.approx(1.0 + 40.0 * (i2 + DT))
    assert abs(u_after - u_before) > 1.0                                               # the Ki step produced a bump


def test_reset_clears_state():
    pid = make(Kp=1.0, Ki=5.0, Kd=0.5)
    for _ in range(50):
        pid.step(2.0)
    pid.reset()
    assert pid.integral == 0.0 and pid.prev_error == 0.0 and pid.filtered_derivative == 0.0
    fresh = make(Kp=1.0, Ki=5.0, Kd=0.5)
    assert pid.step(1.0) == fresh.step(1.0)
