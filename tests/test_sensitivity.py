"""G3.2: sensitivity study -- design, determinism, outputs, and the physical sanity check on Jm."""

import copy
import csv
import json

import numpy as np
import pytest

from models.dc_motor import DCMotor, DCMotorParams
from models.joint import Joint, JointParams
from simulation import rawlog
from simulation import sensitivity as S


def test_halving_jm_halves_the_mechanical_time_constant(cfg):
    """Open-loop speed step: time to 63 % of the final speed is Jm / (Bm + Kt*Ke/R) and scales with Jm."""
    nom = S.nominal(cfg)

    def tau63(Jm):
        m = DCMotor(DCMotorParams(R=nom["R"], L=0.0, Kt=nom["Kt"], Ke=nom["Ke"], Jm=Jm, Bm=nom["Bm"]))
        state, dt, w = np.zeros(3), 1e-5, []
        for _ in range(30000):
            state = m.step(state, dt, 12.0, 0.0)
            w.append(state[1])
        w = np.array(w)
        return (np.argmax(w >= 0.632 * w[-1]) + 1) * dt, Jm / (nom["Bm"] + nom["Kt"] * nom["Ke"] / nom["R"])

    t1, a1 = tau63(nom["Jm"])
    t2, a2 = tau63(nom["Jm"] / 2)
    assert t1 == pytest.approx(a1, rel=0.03) and t2 == pytest.approx(a2, rel=0.03)      # matches the analytic constant
    assert t2 / t1 == pytest.approx(0.5, rel=0.03)                                     # proportional to Jm


def test_perturbed_cfg_does_not_mutate_and_validates(cfg):
    before = copy.deepcopy(cfg)
    c = S.perturbed_cfg(cfg, {"R": 3.0, "L": 1e-3, "delay_steps": 2, "eta": 0.6, "V_supply": 11.5})
    assert cfg == before
    assert c["base_motor"]["derived"]["method_c"]["R_ohm"] == 3.0 and c["driver"]["delay_steps"] == 2
    assert c["gearbox"]["efficiency"] == 0.6 and c["supply"]["V_rated"] == 11.5
    assert c["base_motor"]["estimated"]["L_H"] == 1e-3
    with pytest.raises(KeyError):
        S.perturbed_cfg(cfg, {"nope": 1})


def test_ranges_come_from_the_yaml_and_L_stays_in_the_stable_range(cfg):
    spec = S.ranges(cfg)
    nom = S.nominal(cfg)
    assert spec["R"]["lo"] == pytest.approx(nom["R"] * 0.8) and spec["V_supply"]["hi"] == pytest.approx(nom["V_supply"] * 1.05)
    assert spec["Jm"]["lo"] == pytest.approx(nom["Jm"] / 3) and spec["Jm"]["hi"] == pytest.approx(nom["Jm"] * 3)
    assert spec["eta"]["clip"] == [0.2, 1.0]
    assert (spec["L"]["lo"], spec["L"]["hi"]) == (1e-4, 5e-3)                          # 0.1 ... 5 mH
    assert S.L_LEVELS_H[0] >= 1e-4 and S.L_LEVELS_H[-1] <= 5e-3
    for L in (1e-4, 1e-3, 5e-3):                                                       # sub-stepped, stays finite
        m, _ = S.run(S.perturbed_cfg(cfg, {"L": L}), t_end=0.5)
        assert np.isfinite(m["overshoot_pct"]) and np.isfinite(m["peak_current_A"])


def test_from_unit_endpoints_and_clip(cfg):
    spec = S.ranges(cfg)
    lo = S.from_unit(spec, {p: 0.0 for p in S.PARAMS})
    hi = S.from_unit(spec, {p: 1.0 for p in S.PARAMS})
    assert lo["delay_steps"] == 0 and hi["delay_steps"] == 3 and isinstance(hi["delay_steps"], int)
    assert hi["eta"] == 1.0                                                           # clipped, not 1.2
    assert lo["Jm"] < hi["Jm"] and lo["L"] == 1e-4


def test_morris_design_properties():
    rng = np.random.default_rng(0)
    X, order, delta = S.morris_design(5, 10, rng)
    assert X.shape == (10, 6, 5) and delta == pytest.approx(2 / 3)
    assert X.min() >= -1e-12 and X.max() <= 1 + 1e-12
    for t in range(10):
        assert sorted(order[t]) == list(range(5))                                      # every factor moved exactly once
        for s in range(5):
            d = X[t, s + 1] - X[t, s]
            assert np.count_nonzero(np.abs(d) > 1e-12) == 1 and abs(d[order[t, s]]) == pytest.approx(delta)


def test_oat_case_list(cfg):
    cases = S.oat_cases(cfg)
    names = [c[0] for c in cases]
    assert names[0] == "nominal"
    for p in ("R", "Kt", "Ke", "Jm", "Bm", "eta"):
        assert names.count(p) == 4
    assert names.count("L") == 5 and names.count("delay_steps") == 3
    assert max(c[2]["eta"] for c in cases if c[0] == "eta") <= 1.0


@pytest.fixture(scope="module")
def smoke_dirs(tmp_path_factory):
    a, b = tmp_path_factory.mktemp("sens_a"), tmp_path_factory.mktemp("sens_b")
    assert S.main(["--smoke", "--out-dir", str(a), "--seed", "0"]) == 0
    assert S.main(["--smoke", "--out-dir", str(b), "--seed", "0", "--no-raw"]) == 0
    return a, b


def test_smoke_outputs_exist(smoke_dirs):
    a, _ = smoke_dirs
    for f in ("sensitivity_oat.csv", "sensitivity_table.md", "sensitivity_tornado.png", "sensitivity_morris.png",
              "sensitivity_morris.csv", "sensitivity_morris_samples.csv", "sensitivity_keKt.csv",
              "sensitivity_rl_robustness.csv", "sensitivity_ranking.md", "oat_raw.csv", "sensitivity_manifest.json"):
        assert (a / f).exists() and (a / f).stat().st_size > 0, f
    md = (a / "sensitivity_table.md").read_text()
    assert "Recommendation: measure" in md and "Ke / Kt consistency" in md and "preliminary" in md.lower()


def test_same_seed_is_reproducible_and_different_seed_differs(smoke_dirs, tmp_path):
    a, b = smoke_dirs
    for f in ("sensitivity_oat.csv", "sensitivity_morris.csv", "sensitivity_morris_samples.csv", "sensitivity_keKt.csv",
              "sensitivity_rl_robustness.csv", "sensitivity_table.md", "sensitivity_morris.png", "sensitivity_tornado.png"):
        assert (a / f).read_bytes() == (b / f).read_bytes(), f
    S.main(["--smoke", "--out-dir", str(tmp_path), "--seed", "7", "--no-raw"])
    assert (a / "sensitivity_morris_samples.csv").read_bytes() != (tmp_path / "sensitivity_morris_samples.csv").read_bytes()


def test_manifest_logs_versions_and_no_local_paths(smoke_dirs):
    m = json.loads((smoke_dirs[0] / "sensitivity_manifest.json").read_text())
    sw = m["software"]
    assert sw["python"].startswith("3.") and sw["numpy"] and sw["scipy"] and sw["pyyaml"] and sw["platform"]
    assert m["seeds"] == [0] and len(m["config_sha256"]) == 64 and m["files_sha256"]["sensitivity_oat.csv"]
    assert "Users" not in json.dumps(m) and "C:\\" not in json.dumps(m)


def test_raw_log_follows_the_schema(smoke_dirs):
    with open(smoke_dirs[0] / "oat_raw.csv", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        first = next(reader)
    assert tuple(header) == rawlog.RAW_COLUMNS
    row = dict(zip(header, first))
    assert row["experiment_id"] == "S-03" and row["run_id"].startswith("S-03-oat-") and row["target_deg"] == "90"


def test_eta_is_irrelevant_on_the_bare_shaft_but_matters_when_loaded(cfg):
    """No load torque -> the gearbox efficiency cannot change the response; with gravity it must."""
    base = S.run(S.perturbed_cfg(cfg, {}), t_end=1.0)[0]
    low = S.run(S.perturbed_cfg(cfg, {"eta": 0.4}), t_end=1.0)[0]
    assert low["iae_deg_s"] == pytest.approx(base["iae_deg_s"], rel=1e-9)
    j = Joint(JointParams(payload_mass_kg=1.0, arm_length_m=0.10, gravity_on=True))
    lb = S.run(cfg, joint=j, t_end=1.0)[0]
    ll = S.run(S.perturbed_cfg(cfg, {"eta": 0.4}), joint=j, t_end=1.0)[0]
    assert abs(ll["sse_deg"] - lb["sse_deg"]) > 0.05
