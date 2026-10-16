"""G3.3: alternative parameter sets are consistent with their derivation, inactive, and documented with true numbers."""

import csv
import math
import pathlib
import re

import pytest

from models.feasibility import feasibility
from simulation import compare_parameter_sets as C
from simulation import simulate_pid

DOC = pathlib.Path(__file__).resolve().parents[1] / "docs" / "parameter_derivation.md"
D_SETS = ("method_d", "method_d2", "method_d3")


@pytest.fixture(scope="module")
def derived(cfg):
    return C.derive_alternative(cfg)


def test_derivation_algebra(derived):
    assert derived["R"] == pytest.approx(1.6)
    assert derived["K"] == pytest.approx(5.687137e-3, rel=1e-6)
    assert derived["Bm"] == pytest.approx(2.413696e-6, rel=1e-6)
    assert derived["stall_torque_out_eta1_kgcm"] == pytest.approx(78.29, abs=0.01)
    assert derived["eta_for_stall"] == pytest.approx(0.347170, abs=1e-6)
    assert derived["eta_for_rated_at_half_stall"] == pytest.approx(0.319325, abs=1e-6)
    assert derived["current_for_stall_eta08"] == pytest.approx(3.2547, abs=1e-4)
    assert derived["current_of_151_gcm"] == pytest.approx(2.60, abs=0.01)


def test_yaml_alternative_sets_match_the_derivation(cfg, derived):
    d = cfg["base_motor"]["derived"]
    for name in D_SETS:
        s = d[name]
        assert s["Kt_Nm_per_A"] == s["Ke_V_s_per_rad"] == pytest.approx(derived["K"], rel=1e-6)   # SI identity holds
        assert s["R_ohm"] == pytest.approx(derived["R"]) and s["Bm_Nms_per_rad"] == pytest.approx(derived["Bm"], rel=1e-6)
        assert s["status"] == "inactive"
    assert d["method_d"]["gearbox_efficiency"] == pytest.approx(derived["eta_for_stall"], abs=1e-6)
    assert d["method_d2"]["gearbox_efficiency"] == 0.80
    assert d["method_d3"]["gearbox_efficiency"] == pytest.approx(derived["eta_for_rated_at_half_stall"], abs=1e-6)


def test_alternatives_are_never_the_default(cfg):
    assert cfg["simulation"]["active_electrical_scenario"] == "method_c"
    assert {"method_a", "method_b", "method_c"} <= set(cfg["base_motor"]["derived"])
    assert set(D_SETS) <= set(simulate_pid.simulatable_sets(cfg))        # selectable with --params
    assert "method_b" not in simulate_pid.simulatable_sets(cfg)          # still no R, Kt: cannot be simulated


def test_active_set_values_unchanged(cfg):
    c = cfg["base_motor"]["derived"]["method_c"]
    assert (c["R_ohm"], c["Kt_Nm_per_A"], c["Ke_V_s_per_rad"]) == (1.6, 1.974e-3, 6.366e-3)
    assert cfg["gearbox"]["efficiency"] == 0.80 and cfg["base_motor"]["estimated"]["Bm_Nms_per_rad"] == 1.0e-6


def test_d_family_reproduces_no_load_figures_and_one_torque_point(cfg):
    for name in D_SETS:
        c = C.consistency(cfg, name)
        assert c["no_load_rpm"] == pytest.approx(18000, rel=1e-4) and c["no_load_current_A"] == pytest.approx(0.8, rel=1e-4)
        assert c["stall_current_A"] == pytest.approx(7.5) and c["Ke_over_Kt"] == pytest.approx(1.0)
    assert C.consistency(cfg, "method_d")["stall_torque_out_kgcm"] == pytest.approx(27.18, abs=0.01)
    assert C.consistency(cfg, "method_d3")["rated_torque_out_kgcm"] == pytest.approx(12.5, abs=0.01)
    assert C.consistency(cfg, "method_d2")["stall_torque_out_kgcm"] == pytest.approx(62.63, abs=0.02)
    # the existing sets cannot do both: method_c misses the stall torque, method_a the no-load speed
    assert C.consistency(cfg, "method_c")["stall_torque_out_kgcm"] == pytest.approx(21.74, abs=0.01)
    assert C.consistency(cfg, "method_a")["no_load_rpm"] > 2 * 18000


def test_feasibility_uses_the_sets_own_efficiency(cfg):
    base = feasibility(cfg, 1.0, 0.10, 90.0)["tau_avail"]
    d = feasibility(cfg, 1.0, 0.10, 90.0, scenario="method_d")["tau_avail"]
    assert d / base == pytest.approx((5.687137e-3 * 0.347170) / (1.974e-3 * 0.80), rel=1e-4)


def test_trainer_and_factory_read_the_set_overrides(cfg):
    import autotune_360.train_autotune_360 as T
    from models.factory import build_twin_from_config
    t = T.load_cfg("method_d")
    assert t["eff"] == pytest.approx(0.347170) and t["Bm"] == pytest.approx(2.413696e-6) and t["Kt"] == pytest.approx(5.687137e-3)
    tw = build_twin_from_config(cfg, 15, 0, 0.3, scenario="method_d")
    assert tw.gearbox.p.efficiency == pytest.approx(0.347170) and tw.motor.p.Bm == pytest.approx(2.413696e-6)
    assert build_twin_from_config(cfg, 15, 0, 0.3).gearbox.p.efficiency == 0.80       # default unchanged


def test_compare_script_outputs_and_doc_numbers_agree(tmp_path):
    assert C.main(["--out-dir", str(tmp_path)]) == 0
    for f in ("datasheet_consistency.csv", "closed_loop_by_set.csv", "closed_loop_by_set.md", "closed_loop_loaded_by_set.csv",
              "fig_datasheet_consistency.png", "fig_closed_loop_by_set.png", "parameter_sets_manifest.json"):
        assert (tmp_path / f).stat().st_size > 0, f
    with open(tmp_path / "closed_loop_by_set.csv", newline="") as fh:
        rows = {(r["set"], r["case"]): r for r in csv.DictReader(fh)}
    doc = DOC.read_text()
    tuned = {s: rows[(s, "3 P+D (Tuned)")] for s in ("method_a", "method_c", "method_d")}
    # the table in section 5 of the document must quote what the code produced
    for s, (rise, os_, settle, iae) in {"method_a": (0.117, 23.70, 0.602, 13.79), "method_c": (0.190, 1.73, 0.292, 13.00),
                                        "method_d": (0.192, 0.00, 0.348, 10.51)}.items():
        r = tuned[s]
        assert float(r["rise_s"]) == pytest.approx(rise, abs=0.0006) and float(r["overshoot_pct"]) == pytest.approx(os_, abs=0.006)
        assert float(r["settle_s"]) == pytest.approx(settle, abs=0.0006) and float(r["iae_deg_s"]) == pytest.approx(iae, abs=0.006)
    for needle in ("0.347", "0.319", "5.687", "41,153", "15,968", "21.74", "78.29", "27.18", "2.414", "3.25 A", "preliminary"):
        assert needle in doc, needle
    assert "validated" not in re.sub(r"not validated|nothing is validated|is validated on hardware", "", doc.lower())


def test_doc_states_the_recommended_measurement():
    doc = DOC.read_text().lower()
    assert "locked-rotor" in doc and "torque per ampere" in doc and "no-load speed versus voltage" in doc
