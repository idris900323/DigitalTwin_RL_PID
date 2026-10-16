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
