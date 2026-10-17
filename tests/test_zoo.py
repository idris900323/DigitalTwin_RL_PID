"""G3B.8: synthetic motor zoo pipeline and the failure cases (contradiction, missing field, wrong shaft side, unit typo, stall current that is a max)."""

import math

import pytest

from models import ingest
from models.derive import derive_model
from models.motor_profile import ProfileError
from models.motors import load_base_config
from tuning import zoo

GOOD = """T-1 gearmotor
Voltage 12 V
Gear ratio 100:1
Base motor
No-load speed 10000 rpm
No-load current 0.2 A
Terminal resistance 2.0 ohm
Stall current 6.0 A
Stall torque 60 mN.m
Weight 120 g
Efficiency 70 %
Encoder 64 ppr
"""
# K from no-load: (12 - 2*0.2) / (10000*2pi/60) = 0.01108; stall torque / stall current = 0.060 / 6 = 0.010 (within 15 %: consistent)


def answers(**kw):
    return {"stall_current": "stall", "stall_torque": "theoretical", **kw}


def profile_from(text, **ans):
    cands = ingest.extract_candidates(text)
    rev = ingest.Review().accept(*[c.id for c in cands])
    rev.answers.update(answers(**ans))
    return ingest.build_profile("t", cands, rev)


def test_baseline_datasheet_is_consistent():
    m = derive_model(profile_from(GOOD), answers())
    assert m.conflicts == [] and m.params["R"].value == pytest.approx(2.0) and m.out_counts_per_rev == 64 * 4 * 100


def test_contradictory_datasheet_reports_a_conflict_not_a_silent_choice():
    text = GOOD + "Torque constant 40 mN.m/A\n"
    m = derive_model(profile_from(text), answers())
    assert any("K (= Kt = Ke)" in c["what"] for c in m.conflicts)
    assert m.params["K"].hi / m.params["K"].lo > 1.5                                  # the interval spans the disagreeing sources


def test_missing_required_field_fails_import():
    text = GOOD.replace("Voltage 12 V\n", "")
    with pytest.raises(ProfileError, match="electrical.nominal_voltage: required field is missing"):
        profile_from(text)
    with pytest.raises(ProfileError, match="mechanical.no_load_speed: required"):
        profile_from(GOOD.replace("No-load speed 10000 rpm\n", ""))


def test_wrong_encoder_shaft_changes_the_counts_and_is_asked_about():
    cands = ingest.extract_candidates(GOOD)
    assert "encoder_mounted_on" in {q["key"] for q in ingest.ambiguities(cands)}      # the wizard asks instead of guessing
    on_motor = derive_model(profile_from(GOOD, encoder_mounted_on="motor"), answers())
    on_output = derive_model(profile_from(GOOD, encoder_mounted_on="output"), answers())
    assert on_motor.out_counts_per_rev == 64 * 4 * 100 and on_output.out_counts_per_rev == 64 * 4      # 100x different resolution


def test_torque_unit_typo_is_caught_either_at_import_or_as_a_conflict():
    typo = GOOD.replace("Stall torque 60 mN.m", "Stall torque 60 kg.cm")          # mN.m vs kg.cm: a factor of 1.6e3
    try:
        m = derive_model(profile_from(typo), answers())
    except ProfileError as e:
        assert "implausible" in str(e) or "plausible range" in str(e)
        return
    assert any("K (= Kt = Ke)" in c["what"] for c in m.conflicts)
    # and the confirmation table flags the unit for the user in every case
    flags = " ".join(f for c in ingest.extract_candidates(typo) for f in c.flags)
    assert "check the unit" in flags


def test_stall_current_that_is_really_a_max_rating_is_flagged_and_widens_R():
    text = GOOD.replace("Stall current 6.0 A", "Load current up to 6.0 A (Max)").replace("Terminal resistance 2.0 ohm\n", "")
    cands = ingest.extract_candidates(text)
    sc = next(c for c in cands if c.field == "electrical.stall_current")
    assert sc.meaning == "max_continuous" and any("not stall" in f for f in sc.flags)
    q = [a for a in ingest.ambiguities(cands) if a["key"] == "stall_current"]
    assert q and q[0]["options"] == ["stall", "max_continuous"]
    m = derive_model(profile_from(text, stall_current="max_continuous"), {"stall_current": "max_continuous"})
    R = m.params["R"]
    assert R.provenance == "assumed" and R.lo < R.value / 3.9                           # R only bounded above by V / I_max
    assert any(c["what"] == "meaning of the current rating" for c in m.conflicts)


# ----------------------------------------------------------------------------------------------- the zoo itself
def test_zoo_motors_are_physically_consistent_and_deterministic():
    a, b = zoo.make_motor(7), zoo.make_motor(7)
    assert a == b and zoo.make_motor(8) != a
    assert a.Is * a.R == pytest.approx(a.V) and a.K * a.w0 + a.R * a.I0 == pytest.approx(a.V)
    assert a.Bm * a.w0 <= a.K * a.I0 * (1 + 1e-9)                                       # friction torque cannot exceed the no-load torque
    assert zoo.make_datasheet(a, 7) == zoo.make_datasheet(a, 7)
    assert zoo.make_datasheet(a, 7, "torque_unit_typo") != zoo.make_datasheet(a, 7)


def test_zoo_datasheets_import_back_to_the_truth_within_rounding():
    ok = 0
    for seed in range(10):
        m = zoo.make_motor(seed)
        prof, model = zoo.pipeline(zoo.make_datasheet(m, seed), m.id, {"stall_current": "stall", "stall_torque": "theoretical"})
        assert model.params["K"].value == pytest.approx(m.K, rel=0.06)                 # 3-significant-digit rounding plus stall/no-load cross-check
        assert model.gear_ratio == m.N and model.V == m.V
        ok += model.params["K"].lo <= m.K <= model.params["K"].hi
    assert ok >= 9


def test_zoo_pipeline_end_to_end_on_two_motors():
    fast = dict(popsize=5, maxiter=5, restarts=1, n_train_plants=4, n_test_plants=8)
    base = load_base_config()
    rows = [zoo.run_one(s, base=base, fast=fast) for s in (0, 2)]
    assert all(r["status"] == "ok" for r in rows)
    s = zoo.summarise(rows)
    assert s["stable_fraction"] == 1.0 and s["imported"] == 2 and math.isfinite(s["price_of_uncertainty_median"])
    assert set(s["band_coverage"]) == {"overshoot [%]", "settling time [s]", "peak current [A]"}


def test_zoo_reports_an_import_failure_instead_of_raising():
    fast = dict(popsize=5, maxiter=5, restarts=1, n_train_plants=4, n_test_plants=8)
    row = zoo.run_one(0, base=load_base_config(), fast=fast, mistake="torque_unit_typo")
    assert row["status"] in ("ok", "import failed")                                    # never an unhandled exception
    if row["status"] == "ok":
        assert row["conflicts"]                                                          # the typo shows up as a datasheet conflict
