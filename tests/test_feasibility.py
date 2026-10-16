"""G1.5: torque-infeasible payloads are detected (Python side)."""

import math

import numpy as np
import pytest

from models.feasibility import describe, feasibility, feasibility_arrays


def test_2kg_15cm_gravity_90deg_is_infeasible(cfg):
    f = feasibility(cfg, 2.0, 0.15, 90.0, gravity=True)
    assert f["tau_hold_peak"] == pytest.approx(2.943, abs=1e-3)
    assert f["tau_avail"] == pytest.approx(2.1317, abs=1e-3)
    assert f["margin_path"] == pytest.approx(0.724, abs=5e-3)
    assert f["status"] == "infeasible"
    print(describe(f))


def test_no_gravity_never_flagged(cfg):
    for m in (0.0, 1.0, 2.0):
        for L in (0.02, 0.15):
            for tgt in (5, 90, 180, 360):
                f = feasibility(cfg, m, L, tgt, gravity=False)
                assert f["status"] == "ok" and math.isinf(f["margin_path"])


def test_1p5kg_12cm_180deg_path_vs_target(cfg):
    f = feasibility(cfg, 1.5, 0.12, 180.0, gravity=True)
    # holding at 180 deg (straight up) needs ~0 torque for sin(180)=0 ...
    assert math.isinf(f["margin_target"])
    # ... but the path crosses 90 deg: 1.5*0.12*9.81 = 1.766 N*m vs 2.132 available
    assert f["tau_hold_peak"] == pytest.approx(1.7658, abs=1e-3)
    assert f["margin_path"] == pytest.approx(2.1317 / 1.7658, abs=2e-3)
    assert f["status"] == "ok"  # 1.207 > 1.2 marginal threshold (barely)
    print(f"1.5kg x 12cm @180deg: margin_path={f['margin_path']:.3f}, margin_target={f['margin_target']}")


def test_marginal_band(cfg):
    f = feasibility(cfg, 1.8, 0.12, 90.0)
    assert 1.0 <= f["margin_path"] < 1.2 and f["status"] == "marginal"


def test_speed_cap_reduces_available_torque(cfg):
    full = feasibility(cfg, 1.0, 0.10, 90.0, v_pct=100)
    half = feasibility(cfg, 1.0, 0.10, 90.0, v_pct=50)
    assert half["tau_avail"] == pytest.approx(0.5 * full["tau_avail"])


def test_target_below_90deg_uses_sin_of_target(cfg):
    f = feasibility(cfg, 2.0, 0.15, 30.0)
    assert f["tau_hold_peak"] == pytest.approx(2.943 * 0.5, abs=1e-3)


def test_vectorised_matches_scalar(cfg):
    m = np.array([0.0, 1.0, 2.0]); L = np.array([0.05, 0.1, 0.15]); tgt = np.array([90.0, 180.0, 90.0])
    ta = feasibility(cfg, 1.0, 0.1, 90.0)["tau_avail"]
    v = feasibility_arrays(ta, m, L, tgt, 1.0)
    for i in range(3):
        s = feasibility(cfg, m[i], L[i], tgt[i])
        assert v["margin_path"][i] == pytest.approx(s["margin_path"]) or (np.isinf(v["margin_path"][i]) and np.isinf(s["margin_path"]))


def test_warning_logged_for_infeasible(cfg, caplog):
    from models.feasibility import warn_if_infeasible
    with caplog.at_level("WARNING"):
        assert warn_if_infeasible(feasibility(cfg, 2.0, 0.15, 90.0)) is True
        assert "0.72" in caplog.text
    assert warn_if_infeasible(feasibility(cfg, 0.0, 0.15, 90.0)) is False


def test_trainer_threshold_matches_config(cfg):
    import autotune_360.train_autotune_360 as T
    assert T.MARGINAL_MARGIN == cfg["feasibility"]["marginal_margin"]
    # trainer's plant constants agree with the active config scenario (until G2.1 removes the duplication)
    d = cfg["base_motor"]["derived"][cfg["simulation"]["active_electrical_scenario"]]
    assert (T.CFG["R"], T.CFG["Kt"], T.CFG["Ke"]) == (d["R_ohm"], d["Kt_Nm_per_A"], d["Ke_V_s_per_rad"])


def test_trainer_context_sampling_is_feasible_by_default():
    import numpy as np

    import autotune_360.train_autotune_360 as T
    stats = {}
    ctx = T.sample_context(2000, np.random.default_rng(0), feasible_only=True, stats=stats)
    assert np.all(T.context_margin(*ctx) >= T.MARGINAL_MARGIN)
    assert 0.05 < stats["infeasible"] / stats["drawn"] < 0.5      # ~15-19 % of raw draws are infeasible/marginal
    full = T.sample_context(2000, np.random.default_rng(0), feasible_only=False)
    assert np.any(T.context_margin(*full) < 1.0)
