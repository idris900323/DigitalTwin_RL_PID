"""G1.4: drive autotune_360/servo_pid_visualizer_360.html in Chromium via Playwright.

Requires `pip install playwright` and an installed Chromium (`playwright install chromium`).
The page is served over local HTTP because `file:` URLs are blocked in this setup.
Skips cleanly if Playwright is unavailable.
"""

import functools
import http.server
import pathlib
import threading

import pytest

pw = pytest.importorskip("playwright.sync_api")

ROOT = pathlib.Path(__file__).resolve().parents[2] / "autotune_360"
SHOTS = pathlib.Path(__file__).resolve().parents[2] / "docs" / "screenshots"


@pytest.fixture(scope="module")
def server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    handler.log_message = lambda *a, **k: None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/servo_pid_visualizer_360.html"
    httpd.shutdown()


@pytest.fixture()
def page(server):
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = browser.new_page(viewport={"width": 1500, "height": 1000})
        errors = []
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(server)
        pg.wait_for_function("cadLoaded === true", timeout=20000)
        pg.errors = errors
        yield pg
        browser.close()


def set_slider(pg, sid, value):
    pg.evaluate(
        "([id, v]) => { const e = document.getElementById(id); e.value = v; "
        "e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new Event('change', {bubbles: true})); }",
        [sid, value],
    )


def test_loads_without_console_errors(page):
    assert page.errors == []


def test_arm_length_default_not_snapped(page):
    assert page.evaluate("document.getElementById('plLen').getAttribute('value')") == "3"
    assert page.evaluate("document.getElementById('plLen').value") == "3"  # browser did not snap it
    assert page.evaluate("document.getElementById('plLenOut').textContent") == "3.0 cm"
    assert page.evaluate("(+document.getElementById('plLen').value).toFixed(1) + ' cm'") == "3.0 cm"


def test_badge_not_misleading(page):
    text = page.evaluate("document.getElementById('modeLabel').textContent")
    assert "0 rotating" not in text
    assert "CAD loaded" in text or text in ("running", "ready")
    assert "rotating CAD parts" in page.evaluate("document.getElementById('modeLabel').title")


def test_arm_stays_in_frame_at_15cm(page):
    set_slider(page, "plLen", 15)
    inside = page.evaluate(
        """() => {
          const out = [];
          for (const deg of [0, 45, 90, 135, 180, 225, 270, 315]) {
            shaftGroup.rotation.z = deg * Math.PI / 180;
            scene.updateMatrixWorld(true);
            const v = new THREE.Vector3(); indBall.getWorldPosition(v); v.project(camera);
            out.push([deg, v.x, v.y, v.z]);
          }
          shaftGroup.rotation.z = 0;
          return out;
        }"""
    )
    for deg, x, y, z in inside:
        assert -1 <= x <= 1 and -1 <= y <= 1 and z <= 1, f"arm tip off-screen at {deg} deg: ({x:.2f}, {y:.2f})"


def test_camera_refit_keeps_orbit_direction(page):
    d0 = page.evaluate("(() => { const d = camera.position.clone().sub(controls.target).normalize(); return [d.x, d.y, d.z]; })()")
    set_slider(page, "plLen", 12)
    d1 = page.evaluate("(() => { const d = camera.position.clone().sub(controls.target).normalize(); return [d.x, d.y, d.z]; })()")
    assert d1 == pytest.approx(d0, abs=1e-6)
    dist = page.evaluate("camera.position.distanceTo(controls.target)")
    set_slider(page, "plLen", 3)
    assert page.evaluate("camera.position.distanceTo(controls.target)") < dist


def test_screenshot_12cm(page):
    SHOTS.mkdir(parents=True, exist_ok=True)
    set_slider(page, "plLen", 12)
    set_slider(page, "plMass", 1.5)
    page.wait_for_timeout(800)
    page.screenshot(path=str(SHOTS / "09_browser_12cm_after.png"))


# ---------------------------------------------------------------- G1.5 feasibility

def set_gravity(pg, on):
    pg.evaluate("(on) => { const c = document.getElementById('plG'); c.checked = on; c.dispatchEvent(new Event('change', {bubbles: true})); }", on)


def test_infeasible_payload_shows_warning_with_margin(page):
    set_slider(page, "plMass", 2)
    set_slider(page, "plLen", 15)
    set_gravity(page, True)
    set_slider(page, "thetaRef", 90)
    banner = page.locator("#feasBanner")
    assert banner.is_visible()
    text = banner.inner_text()
    assert "INFEASIBLE" in text and "0.72" in text
    assert page.evaluate("document.getElementById('autoBtn').disabled") is True
    assert "disabled" in page.evaluate("document.getElementById('autoBtn').title")
    page.wait_for_timeout(300)
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / "10_browser_infeasible_banner.png"))


def test_feasible_payload_hides_warning(page):
    set_gravity(page, False)
    set_slider(page, "plMass", 2)
    assert not page.locator("#feasBanner").is_visible()
    assert page.evaluate("document.getElementById('autoBtn').disabled") is False


def test_feasibility_js_matches_python(page):
    import yaml
    from models.feasibility import feasibility
    cfg = yaml.safe_load(open(ROOT.parent / "config" / "motor_parameters.yaml"))
    cases = [(2.0, 0.15, 90, True, 100), (1.5, 0.12, 180, True, 100), (1.0, 0.10, 90, True, 50),
             (0.5, 0.08, 270, True, 100), (2.0, 0.15, 30, True, 100), (1.8, 0.12, 90, True, 100),
             (2.0, 0.15, 90, False, 100), (0.0, 0.10, 90, True, 100), (1.0, 0.05, 360, True, 25)]
    for m, L, tgt, g, v in cases:
        js = page.evaluate("([m, L, t, g, v]) => feasibilityJS(m, L, t, g, v)", [m, L, tgt, g, v])
        py = feasibility(cfg, m, L, tgt, gravity=g, v_pct=v)
        assert js["status"] == py["status"], (m, L, tgt, g, v)
        for key in ("tau_avail", "tau_hold_target", "tau_hold_peak"):
            assert js[key] == pytest.approx(py[key], rel=1e-9, abs=1e-12), key
        for key in ("margin_target", "margin_path"):
            if py[key] == float("inf"):
                assert js[key] is None or js[key] == float("inf")  # JSON turns Infinity into null
            else:
                assert js[key] == pytest.approx(py[key], rel=1e-9)


# ---------------------------------------------------------------- G1.6 feature / policy parity
import json  # noqa: E402

FIXTURE = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "feature_vectors.json"


def test_js_features_and_gains_match_python(page):
    fx = json.loads(FIXTURE.read_text())
    assert fx["feature_version"] == 1
    for c in fx["cases"]:
        pl = {"mass": c["mass"], "len": c["len"], "gravity": c["gravity"], "vPct": c["vPct"]}
        feats = page.evaluate("([pl, t]) => rlFeatures(pl, t)", [pl, c["target"]])
        assert feats == pytest.approx(c["features"], abs=1e-9, rel=1e-9)
        gains = page.evaluate("([pl, t]) => { CFG.thetaRefDeg = t; return rlGains(pl); }", [pl, c["target"]])
        assert gains == pytest.approx(c["gains"], rel=1e-9)


def test_embedded_policy_equals_committed_json(page):
    committed = json.loads((ROOT / "autotune_policy_360.json").read_text())
    embedded = page.evaluate("RL_POLICY")
    assert embedded == committed
