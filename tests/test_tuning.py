"""G3B.4 / G3B.5: loads, linear model, analytic and optimised tuning, tiers, report and export."""

import math
import re

import numpy as np
import pytest

from controllers.pid import PID, PIDParams
from models.factory import build_twin_from_config
from tuning import analytic, export, optimize
from tuning.linear import LinearPlant, noise_voltage_rms
from tuning.loads import LoadError, check_drivable, load_load
from tuning.recommend import recommend, sanity_check, verify_in_twin
from tuning.report import write_report
from tuning.tiers import TIER_LABELS, Tier, tier_for

FAST = dict(popsize=6, maxiter=8, restarts=1, n_train_plants=6, n_test_plants=16)


@pytest.fixture(scope="module")
def rmcs():
    return recommend("rmcs_3070", "bare_shaft", **FAST)


# ----------------------------------------------------------------------------------------------- loads
def test_load_files_parse_and_validate():
    arm = load_load("arm_1kg_10cm")
    assert arm.gravity and arm.payload_min_kg == 0.2 and arm.payload_max_kg == 1.0 and arm.targets_deg == [30.0, 90.0]
    assert arm.payloads(3) == pytest.approx([0.2, 0.6, 1.0])
    bare = load_load("bare_shaft")
    assert not bare.gravity and bare.payloads() == [0.0]


def test_bad_load_files_fail_clearly(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("id: x\nload: {arm_length_m: 0.1, payload_mass_kg: {min: 2, max: 1}}\ntask: {target_deg: [90]}\n")
    with pytest.raises(LoadError, match="min exceeds max"):
        load_load(str(p))
    p.write_text("id: x\nload: {arm_length_m: 0.1}\ntask: {}\n")
    with pytest.raises(LoadError, match="missing field"):
        load_load(str(p))
    p.write_text("id: x\nload: {arm_length_m: 0.1, payload_mass_kg: 0}\ntask: {trajectory: sinusoid}\n")
    with pytest.raises(LoadError, match="not supported"):
        load_load(str(p))
    with pytest.raises(LoadError, match="no load file"):
        load_load("does_not_exist")


def test_infeasible_loads_are_rejected_with_numbers(cfg):
    heavy = load_load("arm_1kg_10cm")
    heavy.payload_max_kg, heavy.arm_length_m = 2.0, 0.15
    with pytest.raises(LoadError) as e:
        check_drivable(cfg, heavy)
    assert "2 kg to 90 deg needs 2.94" in str(e.value) and "gives 2.13" in str(e.value) and "margin 0.72" in str(e.value)
    ok = check_drivable(cfg, load_load("arm_1kg_10cm"))
    assert {r["status"] for r in ok} <= {"ok", "marginal"}
    with pytest.raises(LoadError):
        recommend("rmcs_3070", "bare_shaft", load=heavy, **FAST)


# ----------------------------------------------------------------------------------------------- linear model
def test_linear_model_predicts_the_nonlinear_step_and_margins(cfg):
    pl = LinearPlant.from_cfg(cfg)
    assert pl.b == pytest.approx(0.001974 / (1.6 * 5e-7)) and pl.a == pytest.approx((0.001974 * 0.006366 / 1.6 + 1e-6) / 5e-7)
    m = pl.margins(15, 0, 0.3)
    assert m["stable"] and m["phase_margin_deg"] == pytest.approx(70.0, abs=1.0) and m["gain_margin_db"] > 30
    assert pl.margins(200, 0, 0)["phase_margin_deg"] < 20                       # high gain: little margin
    assert not pl.is_stable(5e5, 0, 0)                                          # delay destabilises absurd gains
    assert pl.delay_s == pytest.approx(1.5e-3)


def test_gravity_stiffness_sign_flips_above_90_degrees(cfg):
    below = LinearPlant.from_cfg(cfg, payload_kg=1.0, arm_length_m=0.1, gravity=True, target_deg=45)
    above = LinearPlant.from_cfg(cfg, payload_kg=1.0, arm_length_m=0.1, gravity=True, target_deg=135)
    assert below.c > 0 > above.c
    assert LinearPlant.from_cfg(cfg, payload_kg=1.0, arm_length_m=0.1, gravity=False).c == 0


def test_noise_prediction_matches_simulation(cfg):
    pl = LinearPlant.from_cfg(cfg)
    sig = 0.29 * pl.lsb_rad
    pid = PID(PIDParams(Kp=15, Ki=0, Kd=0.3, dt=1e-3, output_min=-1e9, output_max=1e9, derivative_filter_tau=0.01))
    rng = np.random.default_rng(0)
    u = np.array([pid.step(sig * rng.standard_normal()) for _ in range(120000)])
    assert noise_voltage_rms(15, 0.3, pl) == pytest.approx(u.std(), rel=0.03)


# ----------------------------------------------------------------------------------------------- analytic
def test_pole_placement_puts_the_poles_where_asked(cfg):
    pl = LinearPlant.from_cfg(cfg)
    kp, ki, kd = analytic.pole_placement(pl, wn=20.0, zeta=1.0)
    # PD closed loop (no delay/filter): s^2 + (a + b*Kd/N) s + b*Kp/N
    assert pl.a + pl.b * kd / pl.N == pytest.approx(40.0, rel=1e-9) and pl.b * kp / pl.N == pytest.approx(400.0, rel=1e-9)
    assert ki == 0.0
    assert analytic.imc_lambda(pl, 0.05) == analytic.pole_placement(pl, 20.0, 1.0)
    d = analytic.design(pl, settle_s=0.3)
    assert d["margins"]["stable"] and d["margins"]["phase_margin_deg"] >= 45 and d["margins"]["gain_margin_db"] >= 6


def test_ziegler_nichols_finds_an_ultimate_gain_with_the_delay(cfg):
    pl = LinearPlant.from_cfg(cfg)
    kp, ki, kd = analytic.ziegler_nichols(pl)
    assert kp > 100 and ki > 0 and kd > 0
    assert not LinearPlant.from_cfg(cfg).is_stable(kp / 0.6 * 1.05, 0, 0)       # just above Ku is unstable


# ----------------------------------------------------------------------------------------------- tiers
def test_tier_labels_and_rules():
    assert set(TIER_LABELS) == {1, 2, 3} and "expect to re-tune" in Tier.ESTIMATE.label
    assert tier_for(has_bench_data=False, identification_passed=False, hardware_refined=False) is Tier.ESTIMATE
    assert tier_for(has_bench_data=True, identification_passed=False, hardware_refined=False) is Tier.ESTIMATE   # failing fit stays Tier 1
    assert tier_for(has_bench_data=True, identification_passed=True, hardware_refined=False) is Tier.IDENTIFIED
    assert tier_for(has_bench_data=True, identification_passed=True, hardware_refined=True) is Tier.REFINED
    assert tier_for(has_bench_data=False, identification_passed=False, hardware_refined=True) is Tier.ESTIMATE


# ----------------------------------------------------------------------------------------------- recommendation (RMCS-3070)
def test_recommendation_meets_the_spec_and_beats_the_tuned_preset(rmcs):
    assert rmcs.tier is Tier.ESTIMATE and rmcs.margins["stable"]
    assert rmcs.margins["phase_margin_deg"] >= 40 and rmcs.margins["gain_margin_db"] >= 6
    assert min(rmcs.constraint_probability.values()) >= 0.9
    tuned = next(r for r in rmcs.references if "Tuned preset" in r.name)
    win = next(m for m in rmcs.methods if m.name == rmcs.winner)
    assert win.cost <= tuned.cost + 1e-9                                      # beats or matches the Tuned preset on the chosen cost
    print(f"winner {rmcs.winner} cost {win.cost:.3f} vs Tuned preset {tuned.cost:.3f}; p_ok {win.p_ok:.2f} vs {tuned.p_ok:.2f}")


def test_output_never_shows_bare_gains_or_overclaims(rmcs):
    text = rmcs.format()
    assert text.startswith("TIER 1") and "expect to re-tune" in text and "PRELIMINARY" in text and "least certain parameters" in text
    assert not re.search(r"\b(perfect|optimal)\b", text, re.I)
    assert "5th / median / 95th" in text and "probability of meeting" in text


def test_recommendation_is_reproducible():
    a = recommend("rmcs_3070", "bare_shaft", seed=3, **FAST)
    b = recommend("rmcs_3070", "bare_shaft", seed=3, **FAST)
    assert a.gains == b.gains and a.winner == b.winner


def test_full_twin_confirms_the_prediction(rmcs):
    v = verify_in_twin(rmcs)
    assert v["overshoot_pct"] <= rmcs.load.max_overshoot_pct and v["settle_s"] <= rmcs.load.max_settling_s and abs(v["sse_deg"]) <= rmcs.load.accuracy_deg


@pytest.mark.parametrize("motor", ["synthetic_coreless_12v", "synthetic_brushed_48v"])
def test_other_motors_get_stable_constraint_satisfying_gains_without_hand_tuning(motor):
    r = recommend(motor, "bare_shaft", **FAST)
    assert r.margins["stable"] and r.margins["phase_margin_deg"] >= 40
    assert r.constraint_probability["settling"] >= 0.9 and r.constraint_probability["accuracy"] >= 0.9
    v = verify_in_twin(r)
    assert v["settle_s"] <= r.load.max_settling_s and abs(v["sse_deg"]) <= r.load.accuracy_deg and v["overshoot_pct"] <= r.load.max_overshoot_pct * 2


def test_loaded_arm_recommendation_has_integral_action_and_is_checked_under_gravity():
    r = recommend("rmcs_3070", "arm_1kg_10cm", **FAST)
    assert r.gains[1] > 0                                                      # gravity needs integral action
    assert r.constraint_probability["accuracy"] >= 0.7                           # FAST settings; the CLI defaults search longer
    v = verify_in_twin(r)
    assert abs(v["sse_deg"]) < 2.0


# ----------------------------------------------------------------------------------------------- sanity checker
def test_sanity_checker_catches_noise_amplification_and_windup(cfg):
    load = load_load("bare_shaft")
    lin = LinearPlant.from_cfg(cfg)
    good = sanity_check(cfg, load, (15, 0, 0.3), lin, None, lin.margins(15, 0, 0.3), 0.3)
    assert not good
    noisy = sanity_check(cfg, load, (15, 0, 120.0), lin, None, lin.margins(15, 0, 120.0), 0.3)
    assert any("quantisation noise" in w for w in noisy)
    windup = sanity_check(cfg, load, (15, 500.0, 0.3), lin, None, lin.margins(15, 500.0, 0.3), 0.3)
    assert any("integral time" in w for w in windup)
    edge = sanity_check(cfg, load, (15, 0, 0.3), lin, None, lin.margins(15, 0, 0.3), 0.3, bounds_hit=[True, False, False])
    assert any("edge of its search range" in w for w in edge)
    weak = sanity_check(cfg, load, (200, 0, 0), lin, None, lin.margins(200, 0, 0), 0.3)
    assert any("margins are below" in w for w in weak)
    assert any("does not settle" in w for w in sanity_check(cfg, load, (15, 0, 0.3), lin, None, lin.margins(15, 0, 0.3), math.inf))


def test_a_noisy_encoder_motor_triggers_the_noise_warning(cfg):
    import copy
    coarse = copy.deepcopy(cfg)
    coarse["encoder"]["output_cpr"] = 200                                       # very coarse encoder: large quantisation steps
    lin = LinearPlant.from_cfg(coarse)
    w = sanity_check(coarse, load_load("bare_shaft"), (15, 0, 0.3), lin, None, lin.margins(15, 0, 0.3), 0.3)
    assert any("quantisation noise" in x for x in w)


def test_a_motor_too_weak_for_its_load_is_rejected_up_front(cfg):
    weak = __import__("copy").deepcopy(cfg)
    weak["supply"]["V_rated"] = 3.0                                              # voltage cap: stall torque falls to a quarter
    with pytest.raises(LoadError, match="cannot be driven"):
        check_drivable(weak, load_load("arm_1kg_10cm"))


# ----------------------------------------------------------------------------------------------- export and report
def test_exported_python_controller_matches_the_twin_pid_exactly(rmcs):
    ns = {}
    code = export.to_python(rmcs, date="2026-01-01")
    exec(compile(code, "exported_controller.py", "exec"), ns)                  # noqa: S102 - our own generated code
    ctl = ns["Controller"]()
    ref = PID(PIDParams(Kp=rmcs.gains[0], Ki=rmcs.gains[1], Kd=rmcs.gains[2], dt=rmcs.cfg["simulation"]["control_loop_dt_s"],
                        output_min=-rmcs.cfg["supply"]["V_rated"], output_max=rmcs.cfg["supply"]["V_rated"],
                        derivative_filter_tau=rmcs.cfg["controller"]["derivative_filter_tau_s"]))
    rng = np.random.default_rng(1)
    seq = np.concatenate([np.full(300, 1.5), rng.normal(0, 0.2, 500), np.full(300, -2.0)])
    assert [ctl.step(e) for e in seq] == [ref.step(e) for e in seq]            # bit-identical


def test_exported_controller_in_the_twin_reproduces_the_simulated_response(rmcs):
    ns = {}
    exec(compile(export.to_python(rmcs, date="2026-01-01"), "x.py", "exec"), ns)                # noqa: S102
    load = rmcs.load
    tw_ref = build_twin_from_config(rmcs.cfg, *rmcs.gains)
    tw_exp = build_twin_from_config(rmcs.cfg, *rmcs.gains)
    tw_exp.pid = ns["Controller"]()
    a = tw_ref.run(math.radians(90), 1500)
    b = tw_exp.run(math.radians(90), 1500)
    assert np.array_equal(a["theta_out"], b["theta_out"]) and np.array_equal(a["V_cmd"], b["V_cmd"])
    assert load.id == "bare_shaft"


def test_export_headers_carry_tier_date_hash_and_the_retune_warning(rmcs):
    for text in (export.to_python(rmcs, date="2026-01-01"), export.to_c(rmcs, date="2026-01-01"), export.to_arduino(rmcs, date="2026-01-01")):
        assert "TIER 1" in text and "2026-01-01" in text and rmcs.profile_hash in text and "RE-TUNE AFTER VALIDATION" in text
    c = export.to_c(rmcs)
    assert "pid_step" in c and "fixed point" in c.lower() and "#define KP" in c
    assert "COUNTS_PER_REV = 9360" in export.to_arduino(rmcs) and "emergency stop" in export.to_arduino(rmcs)


def test_report_files_and_content(rmcs, tmp_path):
    paths = write_report(rmcs, tmp_path)
    assert {p.suffix for p in paths} == {".md", ".html", ".png"} and all(p.stat().st_size > 0 for p in paths)
    md = (tmp_path / "recommendation.md").read_text(encoding="utf-8")
    for s in ("TIER 1", "Recommended gains", "Method comparison", "Derived plant parameters", "Stability margins", "Warnings", "next measurement",
              "Why the winner won", "Predicted performance"):
        assert s in md, s
    page = (tmp_path / "recommendation.html").read_text(encoding="utf-8")
    assert "TIER 1" in page and "<table" in page and "recommendation_bode.png" in page
    assert not re.search(r"\b(perfect|optimal)\b", md, re.I)


def test_optimizer_helpers_are_consistent(cfg):
    load = load_load("arm_1kg_10cm")
    ctxs = optimize.contexts(load)
    assert ctxs == [(0.2, 30.0), (0.2, 90.0), (1.0, 30.0), (1.0, 90.0)]
    plants = optimize.plant_arrays(cfg, optimize.sample_factors({"R": (0.8, 1.2), "Jm": (0.2, 5.0), "K": (0.9, 1.1)}, 5, 0), 5)
    assert plants["Kt"].shape == (5,) and np.allclose(plants["Kt"] / 0.001974, plants["Ke"] / 0.006366)        # K moves Kt and Ke together
    ev = optimize.evaluate(cfg, load, np.array([[15.0, 5.0, 0.3], [1.0, 0.0, 0.0]]), ctxs, plants)
    assert ev["cost"].shape == (2,) and ev["cost"][0] < ev["cost"][1]                                         # sensible gains beat tiny ones
    assert optimize.risk(np.array([[1.0, 1.0, 1.0, 10.0]])) > np.mean([1.0, 1.0, 1.0, 10.0])               # risk penalises the worst case
