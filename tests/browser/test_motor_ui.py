"""G3B.7: motor dropdown, tier badge, derived-parameter table, Recommend PID and RL-button availability in the browser page.

Also checks (without a browser) that the generated config carries the motor library and that stored recommendations are not stale.
"""

import hashlib
import json
import pathlib
import re

import pytest

pytest.importorskip("playwright.sync_api")
from tests.browser.test_browser_twin import page, server  # noqa: E402,F401  (shared Playwright fixtures)

ROOT = pathlib.Path(__file__).resolve().parents[2]


def gen_config():
    text = (ROOT / "autotune_360" / "config.generated.js").read_text(encoding="utf-8")
    return json.loads(text[text.index("const DTRL_CONFIG = ") + len("const DTRL_CONFIG = "):text.index(";\nif (typeof")])


def test_generated_config_contains_the_motor_library():
    g = gen_config()
    assert {"rmcs_3070", "synthetic_coreless_12v", "synthetic_brushed_48v"} <= set(g["motors"])
    assert g["defaultMotor"] == "rmcs_3070"
    assert g["motors"]["rmcs_3070"]["hasPolicy"] and not g["motors"]["synthetic_brushed_48v"]["hasPolicy"]
    m = g["motors"]["synthetic_brushed_48v"]
    assert m["supply"]["V_rated"] == 48 and m["gearbox"]["ratio"] == 30 and m["encoder"]["cpr"] == 240000
    assert m["params"]["Jm"]["confidence"] == "low" and m["params"]["R"]["lo"] < m["params"]["R"]["value"] < m["params"]["R"]["hi"]
    assert "TIER 1" in g["tierLabels"]["1"] and g["tierLabels"]["2"] != g["tierLabels"]["1"]


def test_stored_recommendations_match_the_current_profiles():
    g = gen_config()
    recs = g["recommendations"]
    if not recs:
        pytest.skip("no recommendations.json yet: run tools/precompute_recommendations.py")
    for mid, r in recs.items():
        prof = (ROOT / "motors" / mid / "profile.yaml").read_bytes().replace(b"\r\n", b"\n")
        assert r["profile_hash"] == hashlib.sha256(prof).hexdigest()[:16], f"{mid}: profile changed since its recommendation was computed"
        assert r["tier"] == 1 and "TIER 1" in r["label"] and r["gains"]["Kp"] > 0
        assert not re.search(r"\b(perfect|optimal)\b", json.dumps(r), re.I)
    assert set(recs) == set(g["motors"])


def test_new_profile_appears_in_the_generated_library(tmp_path, monkeypatch):
    import shutil
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import generate_js_config as gen

    from models.motors import load_base_config

    lib = tmp_path / "motors"
    shutil.copytree(ROOT / "motors", lib)
    shutil.copytree(lib / "synthetic_coreless_12v", lib / "my_new_motor")
    p = lib / "my_new_motor" / "profile.yaml"
    p.write_text(p.read_text().replace("id: synthetic_coreless_12v", "id: my_new_motor"))
    monkeypatch.setenv("DTRL_MOTORS_DIR", str(lib))
    assert "my_new_motor" in gen.motor_library(load_base_config())


def test_motor_switch_changes_the_plant_badge_and_rl_button(page):
    assert page.evaluate("CURRENT_MOTOR") == "rmcs_3070"
    base_R = page.evaluate("CFG.motor.R")
    badge = page.evaluate("document.getElementById('tierBadge').textContent")
    assert "TIER 1" in badge and "not validated against hardware" in badge and "RMCS-3070" in badge
    assert page.evaluate("document.getElementById('autoBtn').disabled") is False
    page.select_option("#motorSel", "synthetic_brushed_48v")
    page.wait_for_timeout(200)
    assert page.evaluate("CURRENT_MOTOR") == "synthetic_brushed_48v"
    assert page.evaluate("CFG.V_rated") == 48 and page.evaluate("CFG.gearboxRatio") == 30 and page.evaluate("CFG.motor.R") != base_R
    badge2 = page.evaluate("document.getElementById('tierBadge').textContent")
    assert "BR-48-30" in badge2 and "TIER 1" in badge2 and "not validated against hardware" in badge2
    assert page.evaluate("document.getElementById('autoBtn').disabled") is True
    assert "No RL policy has been trained" in page.evaluate("document.getElementById('autoBtn').title")
    page.select_option("#motorSel", "rmcs_3070")
    page.wait_for_timeout(200)
    assert page.evaluate("document.getElementById('autoBtn').disabled") is False
    assert page.errors == []


def test_parameter_table_colours_confidence(page):
    page.select_option("#motorSel", "synthetic_coreless_12v")
    rows = page.evaluate("document.querySelectorAll('#paramTable tr').length")
    assert rows >= 8
    classes = page.evaluate("Array.from(document.querySelectorAll('#paramTable td[class^=conf-]')).map(e => e.className)")
    assert "conf-low" in classes and ("conf-high" in classes or "conf-medium" in classes)
    assert "Least certain" in page.evaluate("document.getElementById('conflictBox').textContent")


def test_recommend_pid_applies_gains_and_shows_the_tier_and_bands(page):
    page.select_option("#motorSel", "synthetic_brushed_48v")
    page.click("#recBtn")
    page.wait_for_timeout(300)
    info = page.evaluate("document.getElementById('recInfo').textContent")
    kp = page.evaluate("+document.getElementById('kp').value")
    assert kp > 0 and "TIER 1" in info and "not validated against hardware" in info
    rec = gen_config()["recommendations"].get("synthetic_brushed_48v")
    if rec:
        assert kp == pytest.approx(rec["gains"]["Kp"], abs=0.05) and "5th / median / 95th" in info
        assert page.evaluate("+document.getElementById('kp').max") >= kp                 # slider range widened to hold the recommendation
    # the response with the recommended gains settles on the 48 V motor
    assert page.evaluate("document.getElementById('mSettle').textContent") not in ("n/a", "—")
    assert page.errors == []


def test_analytic_fallback_when_no_stored_recommendation(page):
    page.evaluate("DTRL_CONFIG.recommendations = {}")
    page.select_option("#motorSel", "synthetic_coreless_12v")
    page.click("#recBtn")
    info = page.evaluate("document.getElementById('recInfo').textContent")
    assert "analytic pole placement" in info and "TIER 1" in info and "python -m dtrl tune" in info
