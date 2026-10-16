"""G1.2: the shipped default gains are the Tuned preset; the legacy gains stay available by name."""

import pytest

from tests.helpers import run_step_response


def test_default_gains_are_tuned_preset(cfg):
    d, p = cfg["pid_defaults"], cfg["pid_presets"]
    assert (d["Kp"], d["Ki"], d["Kd"]) == (p["tuned"]["Kp"], p["tuned"]["Ki"], p["tuned"]["Kd"]) == (15.0, 0.0, 0.3)


def test_default_config_run_reproduces_tuned_metrics(cfg):
    d = cfg["pid_defaults"]
    r = run_step_response(d["Kp"], d["Ki"], d["Kd"])
    assert r.overshoot == pytest.approx(1.73, abs=0.1)
    assert r.settle == pytest.approx(0.292, abs=0.005)


def test_legacy_default_preset_kept(cfg):
    p = cfg["pid_presets"]["legacy_default"]
    assert (p["Kp"], p["Ki"], p["Kd"]) == (5.0, 20.0, 0.05)
    r = run_step_response(p["Kp"], p["Ki"], p["Kd"])
    assert r.overshoot == pytest.approx(42.2, abs=0.1)
