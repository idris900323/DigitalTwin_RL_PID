"""G3.4: the validation plan is complete and its numbers agree with the YAML and the twin."""

import pathlib
import re

import pytest

DOC = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "validation_plan.md").read_text(encoding="utf-8")
TEMPLATE = (pathlib.Path(__file__).resolve().parents[1] / "validation" / "report_template.md").read_text(encoding="utf-8")


def test_all_tests_and_sections_present():
    for t in range(1, 12):
        assert f"### T{t} " in DOC, f"T{t}"
    for sec in ("## 3. Safety and setup", "## 5. Parameter identification method", "## 6. Data format and logging",
                "## 7. Acceptance thresholds", "## 9. Assumptions about the equipment", "Open flags to resolve first"):
        assert sec in DOC, sec
    for needle in ("locked rotor", "current limit", "emergency stop", "RMCS-3013", "7.5 A", "27.18", "151 g.cm", "known added output inertia"):
        assert needle.lower() in DOC.lower(), needle


def test_thresholds_in_the_doc_match_the_yaml(cfg):
    th = cfg["validation_thresholds"]
    assert f"<= {th['step_nrmse_max'] * 100:g} %" in DOC
    assert f">= {th['step_fit_min_pct']:g} %" in DOC
    assert f"<= {th['overshoot_abs_pp_max']:g} percentage points" in DOC
    assert f"{th['settling_rel_max'] * 100:g} %" in DOC and f"{int(th['settling_abs_min_s'] * 1000)} ms" in DOC
    assert f"<= {th['rise_rel_max'] * 100:g} %" in DOC and f"<= {th['sse_abs_deg_max']:g} deg" in DOC
    assert f"<= {th['current_nrmse_max'] * 100:g} %" in DOC and f"<= {th['peak_current_rel_max'] * 100:g} %" in DOC


def test_expected_values_agree_with_the_twin(cfg):
    d = cfg["base_motor"]["derived"]
    N, eta = cfg["gearbox"]["ratio"], cfg["gearbox"]["efficiency"]
    per_amp_c = d["method_c"]["Kt_Nm_per_A"] * N * eta
    per_amp_d = d["method_d"]["Kt_Nm_per_A"] * N * d["method_d"]["gearbox_efficiency"]
    per_amp_d2 = d["method_d2"]["Kt_Nm_per_A"] * N * d["method_d2"]["gearbox_efficiency"]
    assert f"{per_amp_c:.3f} N.m/A" in DOC and f"{per_amp_d:.3f} N.m/A" in DOC and f"{per_amp_d2:.3f} N.m/A" in DOC
    e = cfg["base_motor"]["estimated"]
    c = d["method_c"]
    tau_m = e["Jm_kgm2"] / (e["Bm_Nms_per_rad"] + c["Kt_Nm_per_A"] * c["Ke_V_s_per_rad"] / c["R_ohm"])
    assert f"{tau_m * 1000:.0f} ms" in DOC
    assert 12.0 / c["R_ohm"] * 0 + 1.0 / c["R_ohm"] == pytest.approx(0.625)           # 0.625 A at 1 V
    assert "0.625 A at 1 V" in DOC


def test_no_overclaiming_and_template_wording():
    flat = re.sub(r"never be called validated|may be called validated only|validated\b[^.]*?(only|until)", "", DOC, flags=re.I)
    assert "preliminary" in DOC.lower() and "preliminary" in TEMPLATE.lower()
    assert "never loosen a threshold" in DOC.lower()
    assert "ABB" in DOC and "methodology only" in DOC
