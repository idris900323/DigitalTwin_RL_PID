"""G3.5: bench-data loader, identification and comparison, tested on SYNTHETIC data with known truth."""

import hashlib
import math
import pathlib

import numpy as np
import pytest

from models.dc_motor import DCMotor, DCMotorParams
from models.gearbox import Gearbox, GearboxParams
from validation import compare as cmpmod
from validation import identify as idf
from validation import synthetic as syn
from validation.load_bench_csv import Run, check_run, load_bench_csv

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRUTH = dict(R=2.0, Ke=4.5e-3, Kt=3.0e-3, Jm=8e-7, Bm=3e-6)
RATIO, ETA, CPR, DT = 180.0, 0.8, 9360, 1e-3
JA = 0.012                       # known added inertia on the output shaft [kg m^2] (about 0.5 kg at 15 cm)


@pytest.fixture(scope="module")
def runs():
    V = syn.prbs(2000, 6.0, 40, seed=1)
    kw = dict(ratio=RATIO, eta=ETA, cpr=CPR, i_noise=0.02, theta_noise_counts=0.3)
    return (syn.make_run(TRUTH, V, DT, seed=1, run_id="base", **kw),
            syn.make_run(TRUTH, V, DT, seed=2, J_added_out=JA, run_id="added", **kw))


# ------------------------------------------------------------------------------------------ synthetic plant
def test_fast_simulation_matches_the_twin_motor_and_gearbox():
    V = syn.prbs(500, 6.0, 25, seed=3)
    th, w, i = syn.simulate_open_loop(TRUTH, V, DT, ratio=RATIO, eta=ETA)
    m = DCMotor(DCMotorParams(R=TRUTH["R"], L=0.0, Kt=TRUTH["Kt"], Ke=TRUTH["Ke"], Jm=TRUTH["Jm"], Bm=TRUTH["Bm"]))
    g = Gearbox(GearboxParams(ratio=RATIO, efficiency=ETA))
    s = np.zeros(3)
    for k in range(500):
        assert i[k] == pytest.approx(m.current(s, V[k]), abs=1e-12)
        s = m.step(s, DT, V[k], 0.0)
        assert th[k] == pytest.approx(g.output_position(s[2]), abs=1e-12)
        assert w[k] == pytest.approx(g.output_speed(s[1]), abs=1e-12)


# ------------------------------------------------------------------------------------------ loader
def test_csv_round_trip_and_alias(tmp_path, runs):
    p = tmp_path / "bench.csv"
    syn.write_bench_csv(list(runs), p, cpr=CPR)
    loaded, issues = load_bench_csv(p, cpr=CPR)
    assert [r.run_id for r in loaded] == ["base", "added"] and not [i for i in issues if i.severity == "error"]
    assert np.allclose(loaded[0].t, runs[0].t, atol=1e-8) and np.allclose(loaded[0].V, runs[0].V, atol=1e-8)
    assert np.max(np.abs(loaded[0].theta_deg - runs[0].theta_deg)) < 360.0 / CPR           # quantised to counts
    assert loaded[0].meta["experiment_id"] == "H-03"
    # the voltage column may be called v_meas_V
    alias = tmp_path / "alias.csv"
    alias.write_text(p.read_text().replace("v_applied_V", "v_meas_V", 1))
    again, _ = load_bench_csv(alias, cpr=CPR)
    assert np.allclose(again[0].V, loaded[0].V)


def test_loader_rejects_files_missing_required_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("t_s,i_A\n0,1\n")
    with pytest.raises(ValueError, match="needs t_s"):
        load_bench_csv(bad, cpr=CPR)


def _run(**kw):
    n = 200
    base = dict(run_id="x", t=(np.arange(n) + 1) * 1e-3, V=np.linspace(-6, 6, n), theta_deg=np.linspace(0, 10, n), i=np.ones(n))
    base.update(kw)
    return Run(**base)


def test_sanity_checks_flag_problems():
    checks = lambda r, **k: {i.check for i in check_run(r, **k)}
    assert checks(_run()) == set()
    t = (np.arange(200) + 1) * 1e-3
    t_gap = t.copy(); t_gap[100:] += 0.01
    assert "missing_samples" in checks(_run(t=t_gap))
    t_back = t.copy(); t_back[50] = t_back[40]
    assert "time_order" in checks(_run(t=t_back))
    assert "voltage_range" in checks(_run(V=np.full(200, 20.0)))
    assert "current_range" in checks(_run(i=np.full(200, 20.0)))
    assert "saturation" in checks(_run(V=np.full(200, 12.0)))
    assert "no_motion" in checks(_run(theta_deg=np.zeros(200)))
    assert "nan" in checks(_run(V=np.where(np.arange(200) == 5, np.nan, 1.0)))
    assert "length" in checks(_run(t=t[:5], V=np.ones(5), theta_deg=np.zeros(5), i=np.ones(5)))
    jit = _run(extra={"loop_dt_us": np.concatenate([np.full(199, 1000.0), [1500.0]])})
    assert "loop_timing" in checks(jit)


# ------------------------------------------------------------------------------------------ identification
def test_identify_recovers_all_parameters_with_a_known_added_inertia(runs):
    res = idf.identify(list(runs), {**_cfg()}, added_inertia=[0.0, JA], n_starts=1, seed=0)
    assert res.status == "ok" and res.rank == 5
    for k, true in TRUTH.items():
        e = res.estimates[k]
        assert e.identifiable and e.value == pytest.approx(true, rel=0.01), k            # stated tolerance: 1 %
        assert e.ci95[0] < true < e.ci95[1] or abs(e.value / true - 1) < 0.01


def test_without_the_added_inertia_kt_jm_bm_are_reported_unidentifiable(runs):
    res = idf.identify([runs[0]], _cfg(), n_starts=1, seed=0)
    assert res.status == "partially_identifiable" and res.rank == 4
    for k in ("R", "Ke"):
        assert res.estimates[k].identifiable and res.estimates[k].value == pytest.approx(TRUTH[k], rel=0.02)
    for k in ("Kt", "Jm", "Bm"):
        e = res.estimates[k]
        assert not e.identifiable and e.value is None and e.ci95 is None               # no confident wrong number
    assert set(res.values()) == {"R", "Ke"}
    text = res.summary()
    assert "NOT IDENTIFIABLE" in text and "log(Kt)" in text and "log(Jm)" in text and "log(Bm)" in text
    lump = idf.lumped_estimates(res)
    assert lump["Jm/Kt"]["identifiable"] and lump["Jm/Kt"]["value"] == pytest.approx(TRUTH["Jm"] / TRUTH["Kt"], rel=0.02)
    assert lump["Bm/Kt"]["identifiable"] and lump["Bm/Kt"]["value"] == pytest.approx(TRUTH["Bm"] / TRUTH["Kt"], rel=0.05)


def test_ke_and_kt_cannot_be_separated_from_angle_data_alone(runs):
    """No current measurement: the data fix only two lumped dynamics parameters; the tool says so instead of guessing."""
    res = idf.identify([runs[0]], _cfg(), use_current=False, n_starts=1, seed=0)
    assert res.status == "unidentifiable" and res.rank == 2
    assert not res.estimates["Ke"].identifiable and not res.estimates["Kt"].identifiable
    assert res.values() == {} and any("no current data" in n for n in res.notes)
    lump = idf.lumped_estimates(res)
    assert lump["Kt/(R*Jm)"]["identifiable"] and lump["(Kt*Ke/R+Bm)/Jm"]["identifiable"]
    assert not lump["Jm/Kt"]["identifiable"]
    b = TRUTH
    assert lump["Kt/(R*Jm)"]["value"] == pytest.approx(b["Kt"] / (b["R"] * b["Jm"]), rel=0.02)
    assert lump["(Kt*Ke/R+Bm)/Jm"]["value"] == pytest.approx((b["Kt"] * b["Ke"] / b["R"] + b["Bm"]) / b["Jm"], rel=0.02)


def test_candidate_yaml_is_separate_and_never_touches_the_config(runs, tmp_path):
    cfg_path = ROOT / "config" / "motor_parameters.yaml"
    before = hashlib.sha256(cfg_path.read_bytes()).hexdigest()
    res = idf.identify([runs[0]], _cfg(), n_starts=1, seed=0)
    out = idf.write_candidate_yaml(res, tmp_path / "candidate.yaml", note="synthetic")
    text = out.read_text()
    assert "CANDIDATE" in text and "not applied" in text and "EXPERIMENTAL" in text and "not_identifiable" in text
    import yaml
    doc = yaml.safe_load(text)
    assert set(doc["identified"]) == {"R", "Ke"} and set(doc["not_identifiable"]) == {"Kt", "Jm", "Bm"}
    assert hashlib.sha256(cfg_path.read_bytes()).hexdigest() == before


# ------------------------------------------------------------------------------------------ comparison metrics
def test_signal_metrics_by_hand():
    y = np.array([0.0, 1.0, 2.0, 3.0])
    m = cmpmod.signal_metrics(y, y + 0.5)
    assert m["rmse"] == pytest.approx(0.5) and m["max_error"] == pytest.approx(0.5)
    assert m["nrmse"] == pytest.approx(0.5 / 3.0)
    assert m["fit_pct"] == pytest.approx(100 * (1 - 1.0 / math.sqrt(5.0)))              # ||e|| = 1, ||y - mean|| = sqrt(5)
    assert m["r2"] == pytest.approx(1 - 1.0 / 5.0)
    perfect = cmpmod.signal_metrics(y, y)
    assert perfect["rmse"] == 0 and perfect["fit_pct"] == pytest.approx(100.0) and perfect["r2"] == pytest.approx(1.0)


def test_ljung_box_distinguishes_white_from_structured_residuals():
    rng = np.random.default_rng(0)
    assert cmpmod.ljung_box(rng.standard_normal(2000))["p"] > 0.01
    structured = np.sin(np.arange(2000) * 0.05) + 0.1 * rng.standard_normal(2000)
    assert cmpmod.ljung_box(structured)["p"] < 1e-6
    assert math.isnan(cmpmod.ljung_box(np.zeros(500))["p"])


def test_cross_correlation_finds_a_delayed_input_leak():
    rng = np.random.default_rng(1)
    u = rng.standard_normal(3000)
    leak = np.roll(u, 5) * 0.8 + 0.1 * rng.standard_normal(3000)
    assert cmpmod.input_cross_correlation(leak, u) > 0.8
    assert cmpmod.input_cross_correlation(rng.standard_normal(3000), u) < 0.1


def test_compare_passes_for_the_true_model_and_fails_for_a_wrong_one(cfg):
    run = syn.closed_loop_run(cfg, (15, 0, 0.3), 90.0, true_values=TRUTH, i_noise=0.03, seed=3)
    good = cmpmod.compare_run(run, cmpmod.simulate_like(run, cfg, true_values=TRUTH), cfg["validation_thresholds"])
    assert good.passed and "all thresholds met" in good.table()
    bad = cmpmod.compare_run(run, cmpmod.simulate_like(run, cfg), cfg["validation_thresholds"])    # nominal model, wrong plant
    assert not bad.passed
    failed = {c.name for c in bad.checks if c.passed is False}
    assert {"overshoot difference [pp]", "peak current rel. error"} <= failed
    assert "FAIL" in bad.table() and "NOT met" in bad.table()
    assert any(c.passed is None for c in bad.checks)                                       # informational rows are not pass/fail


def test_compare_requires_gains_for_closed_loop_simulation(cfg):
    with pytest.raises(ValueError):
        cmpmod.simulate_like(_run(), cfg)


def test_identify_from_a_closed_loop_step_response_reports_what_it_can(cfg):
    run = syn.closed_loop_run(cfg, (15, 0, 0.3), 90.0, true_values=TRUTH, i_noise=0.03, seed=3)
    res = idf.identify([run], cfg, n_starts=2, seed=0)
    assert res.estimates["R"].identifiable and res.estimates["R"].value == pytest.approx(TRUTH["R"], rel=0.05)
    assert res.estimates["Ke"].identifiable and res.estimates["Ke"].value == pytest.approx(TRUTH["Ke"], rel=0.05)
    assert not res.estimates["Kt"].identifiable                                            # scale ambiguity remains


def _cfg():
    from tests.helpers import load_config
    return load_config()
