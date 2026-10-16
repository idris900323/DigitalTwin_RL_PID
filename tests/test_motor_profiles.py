"""G3B.1 / G3B.3: motor profiles, unit handling, derivation engine, and --motor plumbing."""

import copy
import math

import numpy as np
import pytest
import yaml

from models.derive import derive_model, to_config
from models.factory import build_twin_from_config
from models.motor_profile import FIELDS, UNITS, ProfileError, list_motors, load_profile, to_si, validate_profile
from models.motors import DEFAULT_MOTOR, get_cfg, load_base_config, motor_from_argv

GOOD = {
    "id": "t", "electrical": {"nominal_voltage": {"value": 12, "unit": "V", "provenance": "datasheet", "source": "x", "confidence": "high"}},
    "mechanical": {"no_load_speed": {"value": 1000, "unit": "rpm", "shaft": "motor", "provenance": "datasheet", "source": "x", "confidence": "high"}},
    "gearbox": {"ratio": {"value": 10, "unit": "", "provenance": "datasheet", "source": "x", "confidence": "high"}, "stated_figures_at": "motor"},
}


def good():
    return copy.deepcopy(GOOD)


def test_library_lists_the_three_profiles():
    assert {"rmcs_3070", "synthetic_coreless_12v", "synthetic_brushed_48v"} <= set(list_motors())
    for m in list_motors():
        p = load_profile(m)
        assert p.synthetic == m.startswith("synthetic_")


def test_valid_minimal_profile_passes():
    validate_profile(good())


def test_unknown_unit_is_rejected_naming_field_and_allowed_units():
    d = good()
    d["electrical"]["nominal_voltage"]["unit"] = "volts"
    with pytest.raises(ProfileError) as e:
        validate_profile(d)
    msg = str(e.value)
    assert "electrical.nominal_voltage" in msg and "'volts'" in msg and "'V'" in msg and "'mV'" in msg


def test_unit_typo_between_gcm_and_kgcm_is_caught_by_range_check():
    d = good()
    d["mechanical"]["stall_torque"] = {"value": 27180, "unit": "kg.cm", "shaft": "output", "provenance": "datasheet", "source": "x", "confidence": "high"}
    with pytest.raises(ProfileError, match="mechanical.stall_torque.*plausible range"):
        validate_profile(d)
    d["mechanical"]["stall_torque"]["value"] = 27.18
    validate_profile(d)


def test_shaft_side_is_required_for_speed_and_torque():
    d = good()
    del d["mechanical"]["no_load_speed"]["shaft"]
    with pytest.raises(ProfileError, match="mechanical.no_load_speed.*shaft"):
        validate_profile(d)


@pytest.mark.parametrize("mutate,match", [
    (lambda d: d["electrical"].pop("nominal_voltage"), "electrical.nominal_voltage: required"),
    (lambda d: d["gearbox"].pop("stated_figures_at"), "stated_figures_at"),
    (lambda d: d["electrical"]["nominal_voltage"].update(provenance="guess"), "provenance"),
    (lambda d: d["electrical"]["nominal_voltage"].update(confidence="great"), "confidence"),
    (lambda d: d["electrical"]["nominal_voltage"].pop("source"), "source"),
    (lambda d: d["electrical"]["nominal_voltage"].update(value="twelve"), "not a number"),
    (lambda d: d["gearbox"]["ratio"].update(value=0.5), "gearbox.ratio"),
    (lambda d: d["electrical"].update(stall_current={"value": 5, "unit": "A", "provenance": "datasheet", "source": "x", "confidence": "high", "meaning": "peak"}), "meaning"),
    (lambda d: d.update(feedback={"counts_per_rev": {"value": 100, "unit": "ppr", "provenance": "datasheet", "source": "x", "confidence": "high"}}), "feedback.mounted_on"),
])
def test_invalid_profiles_fail_with_a_specific_message(mutate, match):
    d = good()
    mutate(d)
    with pytest.raises(ProfileError, match=match):
        validate_profile(d)


def test_profile_id_must_match_folder(tmp_path):
    (tmp_path / "abc").mkdir()
    d = good()
    (tmp_path / "abc" / "profile.yaml").write_text(yaml.safe_dump(d))
    with pytest.raises(ProfileError, match="does not match its folder"):
        load_profile("abc", tmp_path)
    with pytest.raises(FileNotFoundError, match="available"):
        load_profile("nope", tmp_path)


def test_unit_conversions():
    assert to_si("mechanical.no_load_speed", {"value": 60, "unit": "rpm"}) == pytest.approx(2 * math.pi)
    assert to_si("mechanical.stall_torque", {"value": 4.5, "unit": "oz.in"}) == pytest.approx(0.0317770, rel=1e-5)
    assert to_si("mechanical.stall_torque", {"value": 1000, "unit": "g.cm"}) == pytest.approx(to_si("mechanical.stall_torque", {"value": 1, "unit": "kg.cm"}))
    assert to_si("electrical.no_load_current", {"value": 120, "unit": "mA"}) == pytest.approx(0.12)
    assert to_si("constants.back_emf_constant", {"value": 10, "unit": "V/krpm"}) == pytest.approx(0.0954930, rel=1e-5)
    assert to_si("constants.speed_constant", {"value": 100, "unit": "rpm/V"}) == pytest.approx(10.4719755, rel=1e-6)
    assert to_si("gearbox.efficiency", {"value": 72, "unit": "%"}) == pytest.approx(0.72)
    assert to_si("mechanical.rotor_inertia", {"value": 5, "unit": "g.cm2"}) == pytest.approx(5e-7)
    assert set(UNITS) >= {FIELDS[p][0] for p in FIELDS}                   # every field's dimension has a unit table


def test_derivation_log_records_every_conversion():
    p = load_profile("synthetic_coreless_12v")
    derive_model(p)
    text = "\n".join(p.derivation_log)
    assert "13100 rpm" in text and "4.5 oz.in" in text and "120 mA" in text


# ----------------------------------------------------------------------------------------------- derivation
def test_coreless_motor_is_derived_consistently():
    m = derive_model(load_profile("synthetic_coreless_12v"))
    R, K, eta = m.params["R"], m.params["K"], m.params["eta"]
    assert R.value == pytest.approx(3.2) and eta.value == pytest.approx(0.72)
    assert K.value == pytest.approx((12 - 3.2 * 0.12) / (13100 * 2 * math.pi / 60), rel=1e-9)
    assert K.value == pytest.approx(4.5 * 0.00706155 / 3.75, rel=0.01)           # stall torque / stall current agrees (no conflict)
    assert m.conflicts == [] and m.out_counts_per_rev == 6400 and m.gear_ratio == 100.0
    assert m.params["Bm"].value == pytest.approx(K.value * 0.12 / (13100 * 2 * math.pi / 60))
    assert all(v.lo <= v.value <= v.hi for v in m.params.values())


def test_brushed_48v_encoder_counts_use_quadrature_and_motor_mounting():
    m = derive_model(load_profile("synthetic_brushed_48v"))
    assert m.out_counts_per_rev == 2000 * 4 * 30                                  # PPR x quadrature x gear ratio
    assert m.params["R"].value == pytest.approx(48 / 20) and m.conflicts == []


def test_rmcs_derivation_surfaces_the_documented_conflicts():
    m = derive_model(load_profile("rmcs_3070"))
    assert m.params["K"].value == pytest.approx(5.687137e-3, rel=1e-6)           # the method_d family constant
    whats = " | ".join(c["what"] + " " + c["detail"] for c in m.conflicts)
    assert "meaning of the current rating" in whats and "0.347" in whats and "62.63" in whats
    assert m.params["R"].provenance == "assumed" and m.params["R"].lo < m.params["R"].value
    assert "Jm" in m.least_certain() and len(m.least_certain()) == 3


def test_answers_resolve_the_stall_current_ambiguity():
    p = load_profile("rmcs_3070")
    plain = derive_model(p)
    answered = derive_model(load_profile("rmcs_3070"), {"stall_current": "stall"})
    assert plain.params["R"].provenance == "assumed" and answered.params["R"].provenance == "calculated"
    assert not any(c["what"] == "meaning of the current rating" for c in answered.conflicts)


def test_contradictory_inputs_produce_a_conflict_report_not_a_silent_choice():
    d = yaml.safe_load(open("motors/synthetic_coreless_12v/profile.yaml"))
    d["id"] = "x"
    d["constants"] = {"torque_constant": {"value": 25, "unit": "mN.m/A", "provenance": "datasheet", "source": "typed", "confidence": "high"}}
    validate_profile(d)
    from models.motor_profile import Profile
    m = derive_model(Profile("x", d))
    assert any("K (= Kt = Ke)" in c["what"] for c in m.conflicts)
    assert m.params["K"].value == pytest.approx(25e-3)                            # stated constant wins, but the disagreement is reported
    assert m.params["K"].hi >= (12 - 3.2 * 0.12) / (13100 * 2 * math.pi / 60)    # interval spans the sources


def test_missing_resistance_and_stall_current_uses_a_wide_class_prior():
    d = yaml.safe_load(open("motors/synthetic_coreless_12v/profile.yaml"))
    d["id"] = "x"
    del d["electrical"]["winding_resistance"], d["electrical"]["stall_current"]
    from models.motor_profile import Profile
    m = derive_model(Profile("x", d))
    R = m.params["R"]
    assert R.provenance == "assumed" and R.hi / R.lo > 5 and R.method.startswith("class prior")


def test_output_shaft_speed_is_converted_to_the_motor_shaft():
    d = yaml.safe_load(open("motors/synthetic_coreless_12v/profile.yaml"))
    d["id"] = "x"
    d["mechanical"]["no_load_speed"] = {"value": 131, "unit": "rpm", "shaft": "output", "provenance": "datasheet", "source": "typed", "confidence": "high"}
    from models.motor_profile import Profile
    m = derive_model(Profile("x", d))
    assert m.params["K"].value == pytest.approx(derive_model(load_profile("synthetic_coreless_12v")).params["K"].value, rel=1e-3)
    assert any("OUTPUT shaft" in line for line in m.trail)


# ----------------------------------------------------------------------------------------------- --motor plumbing
def test_default_motor_config_is_the_unchanged_project_config():
    assert DEFAULT_MOTOR == "rmcs_3070"
    assert get_cfg() == load_base_config() | {"motor_id": "rmcs_3070"}
    assert get_cfg("rmcs_3070")["simulation"]["active_electrical_scenario"] == "method_c"


def test_motor_flag_parsing():
    assert motor_from_argv(["--out-dir", "x", "--motor", "synthetic_brushed_48v"]) == "synthetic_brushed_48v"
    assert motor_from_argv([]) == "rmcs_3070"


def test_other_motor_changes_the_plant_everywhere():
    base = get_cfg("rmcs_3070")
    for m in ("synthetic_coreless_12v", "synthetic_brushed_48v"):
        c = get_cfg(m)
        assert c["simulation"]["active_electrical_scenario"] == "derived" and c["motor_id"] == m
        assert c["gearbox"]["ratio"] != base["gearbox"]["ratio"] and c["encoder"]["output_cpr"] != base["encoder"]["output_cpr"]
        tw = build_twin_from_config(c, 1.0, 0.0, 0.0)
        log = tw.run(math.radians(10), 200)
        assert np.all(np.isfinite(log["theta_out"])) and log["theta_out"][-1] > 0
        assert tw.pid.p.output_max == c["supply"]["V_rated"]


def test_derived_config_agrees_between_twin_and_batch_simulator():
    import autotune_360.train_autotune_360 as T
    c = get_cfg("synthetic_coreless_12v")
    d, e = c["base_motor"]["derived"]["derived"], c["base_motor"]["estimated"]
    bcfg = dict(V_rated=c["supply"]["V_rated"], ratio=c["gearbox"]["ratio"], eff=c["gearbox"]["efficiency"], cpr=c["encoder"]["output_cpr"],
                R=d["R_ohm"], Kt=d["Kt_Nm_per_A"], Ke=d["Ke_V_s_per_rad"], Jm=e["Jm_kgm2"], Bm=e["Bm_Nms_per_rad"], dt=c["simulation"]["control_loop_dt_s"],
                duration=2.0, ref_deg=90.0, tau_f=c["controller"]["derivative_filter_tau_s"], current_limit=None)
    tw = build_twin_from_config(c, 2.0, 0.0, 0.01)
    py = np.degrees(tw.run(math.radians(90), 2000)["theta_out"])
    th, _ = T.simulate_batch([2.0], [0.0], [0.01], [0.0], [0.0], [0.0], [100.0], [90.0], cfg=bcfg, noise=0.0)
    assert np.max(np.abs(py - np.degrees(th[:, 0]))) < 1e-6


def test_trainer_can_be_pointed_at_another_motor_and_restored():
    import autotune_360.train_autotune_360 as T
    saved = (dict(T.CFG), T.LO.copy(), T.HI.copy())
    try:
        T.use_motor("synthetic_brushed_48v")
        assert T.CFG["V_rated"] == 48.0 and T.CFG["ratio"] == 30.0 and T.HI[0] == pytest.approx(50.0 * 4)
    finally:
        T.CFG.clear(); T.CFG.update(saved[0]); T.LO[:], T.HI[:] = saved[1], saved[2]
    assert T.CFG["V_rated"] == 12.0


def test_to_config_does_not_mutate_the_base():
    base = load_base_config()
    before = copy.deepcopy(base)
    to_config(derive_model(load_profile("synthetic_coreless_12v")), base)
    assert base == before
