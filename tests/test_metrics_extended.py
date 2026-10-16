"""G3.1: integral/effort/energy metrics against hand-computed signals."""

import math

import numpy as np
import pytest

from simulation import metrics as M

DT = 1e-3
T = np.arange(1, 1001) * DT           # 0.001 .. 1.000 s (the twin's time base), T = 1 s


def test_constant_error_integrals():
    e = np.full_like(T, 2.0)
    assert M.iae(T, e) == pytest.approx(2.0, abs=1e-9)                    # 2 * 1 s
    assert M.ise(T, e) == pytest.approx(4.0, abs=1e-9)                    # 4 * 1 s
    assert M.itae(T, e) == pytest.approx(2.0 * 0.5, abs=2e-3)             # 2 * integral of t dt = 1.0
    assert M.mae(e) == pytest.approx(2.0)


def test_sign_does_not_matter_for_abs_metrics():
    e = np.full_like(T, -2.0)
    assert M.iae(T, e) == pytest.approx(2.0) and M.ise(T, e) == pytest.approx(4.0) and M.mae(e) == pytest.approx(2.0)


def test_exponential_error_closed_form():
    tau = 0.2
    e = 90.0 * np.exp(-T / tau)
    assert M.iae(T, e) == pytest.approx(90.0 * tau * (1 - math.exp(-1 / tau)), rel=6e-3)
    assert M.ise(T, e) == pytest.approx(90.0 ** 2 * tau / 2 * (1 - math.exp(-2 / tau)), rel=6e-3)
    expect_itae = 90.0 * tau ** 2 * (1 - math.exp(-1 / tau) * (1 + 1 / tau))
    assert M.itae(T, e) == pytest.approx(expect_itae, rel=1e-2)


def test_effort_metrics():
    u = np.full_like(T, 12.0)
    assert M.control_effort_abs(T, u) == pytest.approx(12.0)              # 12 V * 1 s
    assert M.control_effort_sq(T, u) == pytest.approx(144.0)
    assert M.control_effort_abs(T, -u) == pytest.approx(12.0)


def test_peak_current_and_energy():
    i = np.zeros_like(T); i[10] = -7.5; i[20] = 3.0
    assert M.peak_current(i) == 7.5
    V = np.full_like(T, 12.0)
    i2 = np.full_like(T, 2.0)
    assert M.energy_drawn(T, V, i2) == pytest.approx(24.0)                # 12 V * 2 A * 1 s = 24 J
    assert M.energy_drawn(T, V, -i2) == 0.0                               # regeneration is clamped to zero
    half = np.where(T < 0.5, 2.0, -2.0)
    assert M.energy_drawn(T, V, half) == pytest.approx(12.0, abs=0.1)     # only the driving half counts


def test_time_to_band():
    y = 90.0 * (1 - np.exp(-T / 0.1))
    assert M.time_to_band(T, y, 90.0) == pytest.approx(0.1 * math.log(50), abs=2e-3)
    assert math.isnan(M.time_to_band(T, np.zeros_like(T), 90.0))
    assert math.isnan(M.time_to_band(T, y, 0.0))
    ring = 90.0 + 10 * np.sin(2 * math.pi * 3 * T) * np.exp(-3 * T)
    assert M.time_to_band(T, ring, 90.0) < M.settling_time(T, ring, 90.0)  # first entry precedes final settling


def test_all_metrics_keys_and_values():
    y = 90.0 * (1 - np.exp(-T / 0.1))
    m = M.all_metrics(T, y, 90.0, np.full_like(T, 6.0), np.full_like(T, 1.0))
    assert tuple(m) == M.METRIC_NAMES
    assert m["effort_abs_Vs"] == pytest.approx(6.0) and m["energy_J"] == pytest.approx(6.0)
    assert m["iae_deg_s"] == pytest.approx(M.iae(T, 90.0 - y))
    assert m["overshoot_pct"] == 0.0
