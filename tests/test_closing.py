"""G3B.6: Tier 1 -> Tier 2 -> Tier 3 on synthetic data from a hidden true motor."""

import copy
import math

import numpy as np
import pytest
import yaml

from models.derive import derive_model, to_config
from models.motor_profile import load_profile
from models.motors import get_cfg, load_base_config
from simulation.metrics import overshoot_pct, settling_time
from tuning import optimize
from tuning.closing import (
    RelayController,
    profile_with_identification,
    refine_with_relay,
    relay_analysis,
    save_profile,
    simulate_relay,
    tier_after_identification,
)
from tuning.loads import load_load
from tuning.recommend import recommend, verify_in_twin
from tuning.tiers import Tier
from validation import identify as idf
from validation import synthetic as syn

MOTOR = "synthetic_coreless_12v"
FAST = dict(popsize=6, maxiter=8, restarts=1, n_train_plants=6, n_test_plants=16)


@pytest.fixture(scope="module")
def world():
    base = load_base_config()
    prof = load_profile(MOTOR)
    m1 = derive_model(prof)
    cfg1 = to_config(m1, base)
    p = m1.params
    truth = dict(R=p["R"].value * 1.08, Ke=p["K"].value * 0.92, Kt=p["K"].value * 0.92, Jm=p["Jm"].value * 2.0, Bm=p["Bm"].value * 0.5)
    ratio, eta, cpr = cfg1["gearbox"]["ratio"], cfg1["gearbox"]["efficiency"], cfg1["encoder"]["output_cpr"]
    V = syn.prbs(2000, 6.0, 40, seed=1)
    JA = 0.5 * ratio ** 2 * truth["Jm"] * 1.2                  # added output inertia, 1.2 x the reflected rotor inertia
    kw = dict(ratio=ratio, eta=eta, cpr=cpr, i_noise=0.01, theta_noise_counts=0.3)
    runs = [syn.make_run(truth, V, 1e-3, seed=1, run_id="base", **kw), syn.make_run(truth, V, 1e-3, seed=2, J_added_out=JA, run_id="added", **kw)]
    ident = idf.identify(runs, cfg1, added_inertia=[0.0, JA], n_starts=1, seed=0, sigma_i=0.01)
    return dict(base=base, prof=prof, m1=m1, cfg1=cfg1, truth=truth, ident=ident, runs=runs)


def true_cfg(w):
    from simulation.sensitivity import perturbed_cfg
    t = w["truth"]
    return perturbed_cfg(w["cfg1"], {"R": t["R"], "Kt": t["Kt"], "Ke": t["Ke"], "Jm": t["Jm"], "Bm": t["Bm"]})


def test_identification_of_the_hidden_motor_is_complete(world):
    ident = world["ident"]
    assert ident.status == "ok"
    for k, v in world["truth"].items():
        assert ident.estimates[k].value == pytest.approx(v, rel=0.03), k


def test_identified_profile_is_a_separate_candidate_with_narrower_intervals(world, tmp_path):
    prof = world["prof"]
    before = copy.deepcopy(prof.data)
    new = profile_with_identification(prof, world["ident"])
    assert prof.data == before and new.data["electrical"]["winding_resistance"]["provenance"] == "measured"
    out = save_profile(new, tmp_path / "ident_profile.yaml")
    assert "CANDIDATE" in out.read_text() and yaml.safe_load(out.read_text())["mechanical"]["rotor_inertia"]["provenance"] == "measured"
    m2 = derive_model(new)
    for k in ("R", "K", "Jm"):
        w1 = world["m1"].params[k].hi / world["m1"].params[k].lo
        w2 = m2.params[k].hi / m2.params[k].lo
        assert w2 < w1, k                                                      # intervals narrowed
    assert m2.params["Jm"].provenance == "measured" and m2.params["Jm"].value == pytest.approx(world["truth"]["Jm"], rel=0.03)
    assert "Kt" in m2.params and "Ke" in m2.params                              # both constants measured: kept separate


def test_partial_identification_only_replaces_what_is_determined(world):
    partial = idf.identify([world["runs"][0]], world["cfg1"], n_starts=1, seed=0, sigma_i=0.01)       # no added inertia: Kt, Jm, Bm undetermined
    new = profile_with_identification(world["prof"], partial)
    assert new.data["electrical"]["winding_resistance"]["provenance"] == "measured"
    assert new.data["mechanical"].get("rotor_inertia", {}).get("provenance") != "measured"
    assert new.data["identification"]["not_identifiable"] == ["Kt", "Jm", "Bm"]


def test_tier_two_is_refused_unless_the_fit_passes(world):
    ident = world["ident"]
    assert tier_after_identification(ident, True) is Tier.IDENTIFIED
    assert tier_after_identification(ident, False) is Tier.ESTIMATE                  # failed thresholds: stays Tier 1
    assert tier_after_identification(ident, None) is Tier.ESTIMATE
    partial = idf.identify([world["runs"][0]], world["cfg1"], n_starts=1, seed=0, sigma_i=0.01)
    assert tier_after_identification(partial, True) is Tier.ESTIMATE                 # incomplete identification
    assert tier_after_identification(ident, True, has_bench_data=False) is Tier.ESTIMATE


def test_end_to_end_prediction_error_shrinks_and_bands_narrow_but_contain_the_truth(world):
    load = load_load("bare_shaft")
    tcfg = true_cfg(world)
    r1 = recommend(MOTOR, "bare_shaft", tier=Tier.ESTIMATE, model=world["m1"], cfg=world["cfg1"], load=load, **FAST)
    new = profile_with_identification(world["prof"], world["ident"])
    m2 = derive_model(new)
    r2 = recommend(MOTOR, "bare_shaft", tier=Tier.IDENTIFIED, model=m2, cfg=to_config(m2, world["base"]), load=load, **FAST)

    def truth_metrics(rec):
        tw = __import__("models.factory", fromlist=["x"]).build_twin_from_config(tcfg, *rec.gains)
        log = tw.run(math.radians(90), 2000)
        y = np.degrees(log["theta_out"])
        return overshoot_pct(y, 90.0), settling_time(log["t"], y, 90.0)

    def band(rec, key):
        p = rec.predictions[key]
        return p["p5"], p["p50"], p["p95"], p["p95"] - p["p5"]

    errs, widths, inside = [], [], []
    for rec in (r1, r2):
        os_t, st_t = truth_metrics(rec)
        lo, med, hi, w = band(rec, "settling time [s]")
        errs.append(abs(med - st_t)); widths.append(w); inside.append(lo - 0.02 <= st_t <= hi + 0.02)
    assert errs[1] < errs[0] or errs[1] < 0.02                                       # prediction error shrinks (or is already tiny)
    assert widths[1] < widths[0]                                                     # bands narrow with data
    assert inside[1]                                                                 # and still contain the truth
    assert r1.tier is Tier.ESTIMATE and r2.tier is Tier.IDENTIFIED and "TIER 2" in r2.format()
    print(f"settling-time prediction error Tier1 {errs[0]:.3f} s -> Tier2 {errs[1]:.3f} s; band width {widths[0]:.3f} -> {widths[1]:.3f} s; truth inside: {inside}")


# ----------------------------------------------------------------------------------------------- relay feedback (Tier 3)
def test_relay_analysis_is_consistent_and_validates_its_input():
    cfg = get_cfg("rmcs_3070")
    d, h = 3.0, math.radians(0.5)
    t, th = simulate_relay(cfg, d, h)
    r = relay_analysis(t, th, d)
    assert r.cycles >= 10 and 0.05 < r.Tu < 0.5 and r.Ku > 0 and r.amplitude > 0
    assert r.zn_gains[0] == pytest.approx(0.6 * r.Ku) and r.tyreus_luyben_gains[0] == pytest.approx(0.31 * r.Ku)
    r2 = relay_analysis(*simulate_relay(cfg, d, h), d)
    assert (r.Ku, r.Tu) == (r2.Ku, r2.Tu)                                         # deterministic
    with pytest.raises(ValueError, match="oscillation cycles"):
        relay_analysis(t[:60], th[:60], d)
    assert RelayController(2.0, 0.1).step(0.5) == 2.0 and RelayController(2.0, 0.1).step(-0.5) == -2.0
    c = RelayController(2.0, 0.1); c.step(0.5)
    assert c.step(0.05) == 2.0                                                    # inside the hysteresis band: holds its state


def test_relay_refinement_recovers_the_inertia_and_labels_tier_3():
    cfg_true = get_cfg("rmcs_3070")
    cfg_true["base_motor"]["estimated"]["Jm_kgm2"] *= 2.0                           # the real rotor is twice as heavy as the datasheet estimate
    d, h = 3.0, math.radians(0.5)
    measured = relay_analysis(*simulate_relay(cfg_true, d, h), d)
    rec1 = recommend("rmcs_3070", "bare_shaft", **FAST)                             # Tier 1 on the wrong inertia
    rec3 = refine_with_relay(rec1, measured, d_volts=d, hysteresis_rad=h, **FAST)
    assert rec3.tier is Tier.REFINED and "TIER 3" in rec3.format()
    assert rec3.model.params["Jm"].value == pytest.approx(rec1.model.params["Jm"].value * 2.0, rel=0.15)
    assert rec3.model.params["Jm"].hi / rec3.model.params["Jm"].lo < 1.2             # narrow band after refinement
    v = verify_in_twin(rec3)
    assert abs(v["sse_deg"]) < 0.5
    assert optimize is not None
