"""G2.4: every implementation of the plant agrees on the canonical scenarios (tests/scenarios.json).

Implementations compared against the Python twin (models/ + controllers/):
  * trainer      -- the vectorised numpy simulator in autotune_360/train_autotune_360.py
  * browser JS   -- autotune_360/physics.js (the same file that is inlined in the HTML), run headlessly in Node
  * Qt demo      -- cad_pid_visualizer.compute_run, the demo's GUI-free compute path

Intentionally loose spots (documented, not hidden):
  * Encoder noise exists only in the Python twin and the trainer, so the JS physics skips the noise scenario.
    Python vs trainer still agree there because both draw the same seeded normal stream (seed 0, one draw per step).
  * The trainer supports a subset (payload point mass, gravity, speed cap, current limit, noise) -- no arm mass,
    friction or disturbances -- and the Qt compute path supports payload + gravity only; scenarios outside a
    subset are skipped for that implementation.
"""

import json
import math
import pathlib
import shutil
import subprocess

import numpy as np
import pytest

import autotune_360.train_autotune_360 as T
from models.factory import build_twin_from_config
from models.joint import Joint, JointParams
from simulation.metrics import overshoot_pct, rise_time, settling_time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENARIOS = json.loads((pathlib.Path(__file__).parent / "scenarios.json").read_text())["scenarios"]

# tolerances (final angle in deg, overshoot in percentage points, traces in deg / A)
TOL_FINAL, TOL_OVERSHOOT, TOL_TRACE, TOL_I = 0.01, 0.05, 1e-3, 1e-6


def _fields(sc):
    return dict(mass=sc.get("mass", 0.0), length=sc.get("length", 0.0 if "mass" not in sc else 0.0),
                gravity=bool(sc.get("gravity", False)), v_pct=sc.get("v_pct", 100.0),
                noise=sc.get("noise_counts", 0.0), ilim=sc.get("current_limit_A"), params=sc.get("params"))


def run_python(cfg, sc):
    f = _fields(sc)
    joint = Joint(JointParams(payload_mass_kg=f["mass"], arm_length_m=f["length"], gravity_on=f["gravity"]))
    tw = build_twin_from_config(cfg, sc["kp"], sc["ki"], sc["kd"], scenario=f["params"], joint=joint, v_pct=f["v_pct"],
                                noise_counts=f["noise"], seed=0, current_limit_A=f["ilim"])
    log = tw.run(math.radians(sc["target_deg"]), int(round(2.0 / tw.dt)))
    return dict(theta=np.degrees(log["theta_out"]), V=log["V_applied"], i=log["i_motor"])


def run_trainer(sc):
    f = _fields(sc)
    th, V, i = T.simulate_batch([sc["kp"]], [sc["ki"]], [sc["kd"]], [f["mass"]], [f["length"]], [float(f["gravity"])],
                                [f["v_pct"]], [sc["target_deg"]], cfg=T.load_cfg(f["params"]), noise=f["noise"],
                                nrng=np.random.default_rng(0), current_limit=f["ilim"], return_current=True)
    return dict(theta=np.degrees(th[:, 0]), V=V[:, 0], i=i[:, 0])


@pytest.fixture(scope="module")
def js_results(tmp_path_factory):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    out = tmp_path_factory.mktemp("js") / "out.json"
    res = subprocess.run([node, str(ROOT / "tools" / "run_scenarios.js"), str(pathlib.Path(__file__).parent / "scenarios.json"),
                          str(out)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return json.loads(out.read_text())


def _metrics(theta, target, t):
    return dict(final=float(theta[-1]), overshoot=float(overshoot_pct(theta, target)), peak=float(np.max(theta)))


def _compare(a, b, sc, label):
    t = np.arange(1, len(a["theta"]) + 1) * 1e-3
    ma, mb = _metrics(a["theta"], sc["target_deg"], t), _metrics(b["theta"], sc["target_deg"], t)
    assert mb["final"] == pytest.approx(ma["final"], abs=TOL_FINAL), f"{label} final angle"
    assert mb["overshoot"] == pytest.approx(ma["overshoot"], abs=TOL_OVERSHOOT), f"{label} overshoot"
    assert np.max(np.abs(np.asarray(b["theta"]) - a["theta"])) < TOL_TRACE, f"{label} angle trace"
    assert np.max(np.abs(np.abs(b["i"]).max() - np.abs(a["i"]).max())) < TOL_I * max(1, np.abs(a["i"]).max()), f"{label} peak current"
    sa = settling_time(t, a["theta"], sc["target_deg"])
    sb = settling_time(t, np.asarray(b["theta"]), sc["target_deg"])
    assert (math.isnan(sa) and math.isnan(sb)) or sb == pytest.approx(sa, abs=0.002), f"{label} settling"
    ra, rb = rise_time(t, a["theta"], sc["target_deg"]), rise_time(t, np.asarray(b["theta"]), sc["target_deg"])
    assert (math.isnan(ra) and math.isnan(rb)) or rb == pytest.approx(ra, abs=0.002), f"{label} rise time"


def test_scenario_list_is_large_enough():
    ids = [s["id"] for s in SCENARIOS]
    assert len(ids) >= 12 and len(set(ids)) == len(ids)


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_trainer_matches_python_twin(cfg, sc):
    _compare(run_python(cfg, sc), run_trainer(sc), sc, "trainer")


@pytest.mark.parametrize("sc", [s for s in SCENARIOS if not s.get("skip_js")], ids=lambda s: s["id"])
def test_browser_js_matches_python_twin(cfg, js_results, sc):
    js = js_results[sc["id"]]
    _compare(run_python(cfg, sc), dict(theta=np.asarray(js["theta"]), V=np.asarray(js["V"]), i=np.asarray(js["i"])), sc, "browser JS")


@pytest.mark.parametrize("sc", [s for s in SCENARIOS if not {"v_pct", "noise_counts", "current_limit_A", "params"} & set(s)],
                         ids=lambda s: s["id"])
def test_qt_compute_path_matches_python_twin(cfg, sc):
    qt = pytest.importorskip("simulation.cad_pid_visualizer", reason="Qt/pyvista stack not installed")
    log = qt.compute_run(cfg, sc["kp"], sc["ki"], sc["kd"], sc.get("mass", 0.0), sc.get("length", 0.0),
                         sc.get("gravity", False), sc["target_deg"], 2000)
    got = dict(theta=np.degrees(log["theta_out"]), V=log["V_applied"], i=log["i_motor"])
    _compare(run_python(cfg, sc), got, sc, "Qt compute path")


def test_noise_scenario_actually_differs_from_ideal(cfg):
    ideal = run_python(cfg, {**next(s for s in SCENARIOS if s["id"] == "noise_1count"), "noise_counts": 0.0})
    noisy = run_python(cfg, next(s for s in SCENARIOS if s["id"] == "noise_1count"))
    assert np.max(np.abs(ideal["theta"] - noisy["theta"])) > 1e-6        # the noise path is really exercised


def test_infeasible_scenario_really_stalls(cfg):
    sc = next(s for s in SCENARIOS if s["id"] == "infeasible_2kg_15cm_gravity_90")
    assert run_python(cfg, sc)["theta"][-1] < 60.0                       # cannot reach 90 deg: torque margin 0.72


def test_browser_physics_and_trainer_refuse_inductance(cfg):
    """Neither the browser physics nor the trainer sub-steps, so both must refuse L > 0 instead of going unstable."""
    import copy
    import tempfile

    import yaml

    bad = copy.deepcopy(cfg)
    bad["base_motor"]["estimated"]["L_H"] = 1e-3
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "bad.yaml"
        p.write_text(yaml.safe_dump(bad))
        with pytest.raises(ValueError, match="inductance"):
            T.load_cfg(yaml_path=p)
    node = shutil.which("node")
    if node:
        gen_text = (ROOT / "autotune_360" / "config.generated.js").read_text()
        script = ("const gen = require(%s); gen.scenarios[gen.activeScenario].L = 1e-3;"
                  "const phys = require(%s); try { phys.makeCFG(gen); process.exit(1); } catch (e) { console.log(e.message); }"
                  % (json.dumps(str(ROOT / "autotune_360" / "config.generated.js")), json.dumps(str(ROOT / "autotune_360" / "physics.js"))))
        res = subprocess.run([node, "-e", script], capture_output=True, text=True)
        assert res.returncode == 0 and "refuses L > 0" in res.stdout
