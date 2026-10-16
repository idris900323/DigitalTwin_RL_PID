"""The original ("base") code is the reference: the refactored code must reproduce it.

The `html/` folder holds the base copies of `servo_pid_visualizer_360 (1).html`, `train_autotune_360.py` and
`autotune_policy_360.json`, byte-identical to the files first pushed in commit ffd4835. Where the refactored
implementations (shared physics.js, YAML-driven trainer) and the base code could disagree, the base code wins:
these tests run the BASE physics and BASE trainer functions as an oracle and require the new code to match them
on every scenario the base supports (bare shaft, payload point mass, gravity, speed cap, 0-360 deg targets,
encoder noise in the trainer). Features that did not exist in the base (driver current limit, arm mass, friction,
method_a/b switching, feasibility sampling) are covered by tests/test_cross_implementation.py instead.

The oracle is read from GIT HISTORY (`git show ffd4835:<path>`), never from the working tree, so it works on a clean
clone and cannot be altered by editing files. `html/` (git-ignored) is only a local convenience copy that one guard
test checks against history. If history is unavailable the tests SKIP locally but FAIL when the `CI` environment
variable is set (CI must check out with fetch-depth: 0).
"""

import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys

import numpy as np
import pytest

import autotune_360.train_autotune_360 as T

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE_COMMIT = "ffd4835"
BASE_FILES = {
    "html": ("html/servo_pid_visualizer_360 (1).html", "autotune_360/servo_pid_visualizer_360.html"),
    "trainer": ("html/train_autotune_360.py", "autotune_360/train_autotune_360.py"),
}
SCENARIOS = json.loads((pathlib.Path(__file__).parent / "scenarios.json").read_text())["scenarios"]
# scenarios the base physics can run: no current limit, no noise (JS), base parameter set method_c only
BASE_JS_SCENARIOS = [s for s in SCENARIOS if not {"current_limit_A", "params", "noise_counts"} & set(s)]


def _unavailable(msg: str):
    """Missing base history: fail on CI (misconfigured checkout), skip locally."""
    if os.environ.get("CI"):
        pytest.fail(msg + " -- CI must check out with fetch-depth: 0")
    pytest.skip(msg)


def git_show(path: str) -> bytes:
    res = subprocess.run(["git", "show", f"{BASE_COMMIT}:{path}"], cwd=ROOT, capture_output=True)
    if res.returncode != 0:
        _unavailable(f"base commit {BASE_COMMIT} is not available in git history")
    return res.stdout


def base_text(kind: str) -> str:
    return git_show(BASE_FILES[kind][1]).decode("utf-8")


@pytest.fixture(scope="module")
def base_trainer(tmp_path_factory):
    path = tmp_path_factory.mktemp("base") / "base_trainer.py"
    path.write_text(base_text("trainer"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("base_trainer", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["base_trainer"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_base_files_in_html_folder_are_the_originals():
    """Guard: if html/ exists it must still be the untouched base (so it can serve as the oracle)."""
    for kind, (local, in_git) in BASE_FILES.items():
        p = ROOT / local
        if not p.exists():
            pytest.skip("html/ folder not present (it is git-ignored and optional)")
        norm = lambda b: b.replace(b"\r\n", b"\n")
        assert norm(p.read_bytes()) == norm(git_show(in_git)), f"{local} differs from the base commit"


# ------------------------------------------------------------------ trainer: base vs refactored
def test_base_trainer_context_sampling_and_features_unchanged(base_trainer):
    a = base_trainer.sample_context(500, np.random.default_rng(11))
    b = T._raw_context(500, np.random.default_rng(11))
    for x, y in zip(a, b):
        assert np.array_equal(x, y)
    assert np.array_equal(base_trainer.features(*a), T.features(*b))
    z = np.random.default_rng(3).normal(size=(50, 3))
    assert np.array_equal(base_trainer.gains_from_z(z), T.gains_from_z(z))


def test_base_trainer_plant_constants_equal_yaml(base_trainer):
    for k, v in T.CFG.items():
        if k in base_trainer.CFG:
            assert base_trainer.CFG[k] == pytest.approx(v, rel=0, abs=0), k


def test_base_simulate_batch_matches_refactored(base_trainer):
    rng = np.random.default_rng(5)
    m, L, g, v, R = base_trainer.sample_context(200, rng)
    G = np.exp(rng.uniform(np.log(base_trainer.LO), np.log(base_trainer.HI), (200, 3)))
    for noise in (0.0, 1.0):
        th0, V0 = base_trainer.simulate_batch(G[:, 0], G[:, 1], G[:, 2], m, L, g, v, R, noise=noise,
                                              nrng=np.random.default_rng(9))
        th1, V1 = T.simulate_batch(G[:, 0], G[:, 1], G[:, 2], m, L, g, v, R, noise=noise, nrng=np.random.default_rng(9))
        assert np.array_equal(th0, th1) and np.array_equal(V0, V1)
    c0 = base_trainer.step_cost(th0, V0, v, R)
    assert np.array_equal(c0, T.step_cost(th1, V1, v, R))


def test_base_policy_json_still_loads_and_gives_same_features_contract(base_trainer):
    """The base policy has the same architecture/inputs, so it still runs through the refactored forward pass."""
    d = json.loads(git_show("autotune_360/autotune_policy_360.json").decode("utf-8"))
    pol = T.Policy(np.random.default_rng(0))
    for k in ("W1", "b1", "W2", "b2", "W3", "b3"):
        pol.p[k] = np.array(d[k])
    m, L, g, v, R = T._raw_context(100, np.random.default_rng(2))
    G = T.policy_gains(pol, m, L, g, v, R)
    assert G.shape == (100, 3) and np.all(G >= T.LO * 0.999) and np.all(G <= T.HI * 1.001)
    assert d["lo"] == T.LO.tolist() and d["hi"] == T.HI.tolist()


# ------------------------------------------------------------------ browser physics: base JS vs shared physics.js
def _base_js_physics() -> str:
    html = base_text("html")
    a = html.index("// ---------- physics: ported 1:1 from the Python project ----------")
    b = html.index("// ---------- Three.js scene")
    return html[a:b]


def test_base_js_physics_matches_shared_physics_js(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    driver = tmp_path / "base_vs_new.js"
    scen = [s for s in BASE_JS_SCENARIOS]
    driver.write_text(
        "const document = { getElementById: () => null };\n"
        + _base_js_physics()
        + "\nconst gen = require(" + json.dumps(str(ROOT / "autotune_360" / "config.generated.js")) + ");\n"
        + "const phys = require(" + json.dumps(str(ROOT / "autotune_360" / "physics.js")) + ");\n"
        + "const scen = " + json.dumps(scen) + ";\nconst out = {};\n"
        + """for (const sc of scen) {
  const pl = { mass: sc.mass || 0, len: sc.length === undefined ? 0.028 : sc.length, gravity: !!sc.gravity,
               vPct: sc.v_pct === undefined ? 100 : sc.v_pct };
  CFG.thetaRefDeg = sc.target_deg;                          // base code: global CFG
  const base = runTwin(sc.kp, sc.ki, sc.kd, pl);            // base code: runTwin(Kp, Ki, Kd, pl)
  const cfg = phys.makeCFG(gen); cfg.thetaRefDeg = sc.target_deg;
  const now = phys.runTwin(cfg, sc.kp, sc.ki, sc.kd, pl);
  const maxd = (a, b) => a.reduce((m, v, i) => Math.max(m, Math.abs(v - b[i])), 0);
  out[sc.id] = { dtheta: maxd(base.theta, now.theta), dV: maxd(base.V, now.V), derr: maxd(base.err, now.err),
                 n: [base.theta.length, now.theta.length] };
}
require('fs').writeFileSync(process.argv[2], JSON.stringify(out));
""", encoding="utf-8")
    out = tmp_path / "out.json"
    res = subprocess.run([node, str(driver), str(out)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    result = json.loads(out.read_text())
    assert len(result) == len(BASE_JS_SCENARIOS) >= 10
    for sid, r in result.items():
        assert r["n"][0] == r["n"][1], sid
        assert r["dtheta"] < 1e-9 and r["dV"] < 1e-9 and r["derr"] < 1e-9, (sid, r)
