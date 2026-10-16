"""Command latency (delay_steps) in the digital twin, added for the sensitivity study (G3.2)."""

import math

import numpy as np

from models.factory import build_twin_from_config


def run(cfg, delay, gains=(15, 0, 0.3), n=2000):
    tw = build_twin_from_config(cfg, *gains, delay_steps=delay)
    return tw.run(math.radians(90.0), n)


def test_zero_delay_is_unchanged(cfg):
    a, b = run(cfg, 0), build_twin_from_config(cfg, 15, 0, 0.3).run(math.radians(90.0), 2000)
    assert np.array_equal(a["theta_out"], b["theta_out"])


def test_applied_voltage_is_the_delayed_command(cfg):
    for d in (1, 2, 3):
        log = run(cfg, d, n=200)
        assert np.all(log["V_applied"][:d] == 0.0)                       # buffer starts empty
        assert np.array_equal(log["V_applied"][d:], log["V_cmd"][:-d])    # then V_cmd shifted by d samples


def test_delay_degrades_the_response_and_reset_clears_the_buffer(cfg):
    base, delayed = run(cfg, 0), run(cfg, 3)
    from simulation.metrics import overshoot_pct
    assert overshoot_pct(np.degrees(delayed["theta_out"]), 90.0) > overshoot_pct(np.degrees(base["theta_out"]), 90.0)
    tw = build_twin_from_config(cfg, 15, 0, 0.3, delay_steps=2)
    tw.run(math.radians(90.0), 50)
    tw.reset()
    assert list(tw._v_buffer) == [0.0, 0.0]


def test_delay_composes_with_current_limit(cfg):
    tw = build_twin_from_config(cfg, 15, 0, 0.3, delay_steps=2, current_limit_A=2.0)
    log = tw.run(math.radians(90.0), 500)
    assert np.max(np.abs(log["i_motor"])) <= 2.0 + 1e-9
