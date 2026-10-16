"""G3B.2: datasheet ingestion (text, CSV, PDF), mandatory confirmation, ambiguity handling and the curve digitiser."""

import math

import numpy as np
import pytest

from models import ingest
from models.curves import AxisCalibration, Digitizer, trace_curve
from models.derive import derive_model
from models.motor_profile import ProfileError

RMCS_TEXT = """Johnson RMCS-3070 Geared DC Motor
Operating voltage: 12 V
Gear ratio 180:1
Gearmotor output
Stall torque: 27.18 kg.cm
Rated torque: 12.5 kg.cm
Weight 180 g
Encoder 9360 counts/rev (output)
Base motor
No load speed: 18000 rpm
No load current: 0.8 A
Load current up to 7.5 A (Max)
Rated torque 151 g.cm
"""

TRUTH_RMCS = {"electrical.nominal_voltage": 12.0, "gearbox.ratio": 180.0, "mechanical.stall_torque": 27.18 * 0.0980665,
              "mechanical.rated_torque": 12.5 * 0.0980665, "mechanical.mass": 0.18, "mechanical.no_load_speed": 18000 * 2 * math.pi / 60,
              "electrical.no_load_current": 0.8, "electrical.stall_current": 7.5, "mechanical.motor_rated_torque": 151 * 9.80665e-5}


def by_field(cands, field):
    return [c for c in cands if c.field == field]


def test_rmcs_text_values_are_extracted_with_the_right_shafts_and_flags():
    cands = ingest.extract_candidates(RMCS_TEXT)
    s = ingest.extraction_score(cands, TRUTH_RMCS)
    assert s["fraction"] >= 0.9 and not s["wrong"], s
    print("extraction fraction", s["fraction"], "missing", s["missing"])
    assert by_field(cands, "mechanical.stall_torque")[0].shaft == "output"
    assert by_field(cands, "mechanical.no_load_speed")[0].shaft == "motor"
    sc = by_field(cands, "electrical.stall_current")[0]
    assert sc.value == 7.5 and any("maximum" in f for f in sc.flags)
    flags = " ".join(f for c in cands for f in c.flags)
    assert "reflected value" in flags                                            # 151 g.cm == 27.18 kg.cm / 180 is spotted
    q = {a["key"] for a in ingest.ambiguities(cands)}
    assert {"stall_current", "stall_torque"} <= q


def test_nothing_is_written_without_acceptance():
    cands = ingest.extract_candidates(RMCS_TEXT)
    with pytest.raises(ProfileError, match="required field is missing"):
        ingest.build_profile("x", cands, ingest.Review())                         # no decisions = everything rejected
    review = ingest.Review().accept(*[c.id for c in cands if c.field in ("electrical.nominal_voltage", "mechanical.no_load_speed", "gearbox.ratio")])
    prof = ingest.build_profile("x", cands, review)
    assert set(prof.data["electrical"]) == {"nominal_voltage"} and "stall_torque" not in prof.data["mechanical"]
    assert prof.data["electrical"]["nominal_voltage"]["provenance"] == "datasheet"


def test_edited_values_are_recorded_as_user_provenance_and_logged():
    cands = ingest.extract_candidates(RMCS_TEXT)
    ids = {c.field: c.id for c in cands}
    review = ingest.Review().accept(ids["electrical.nominal_voltage"], ids["gearbox.ratio"]).edit(ids["mechanical.no_load_speed"], value=17500, unit="rpm", shaft="motor")
    prof = ingest.build_profile("x", cands, review)
    f = prof.data["mechanical"]["no_load_speed"]
    assert f["value"] == 17500 and f["provenance"] == "user" and "edited" in f["source"]
    assert any("user edited 18000 rpm -> 17500 rpm" in line for line in prof.derivation_log)


def test_accepting_a_torque_without_a_shaft_is_refused():
    cands = ingest.extract_candidates("No load speed: 18000 rpm\nVoltage 12 V\nGear ratio 100:1\n")
    ns = by_field(cands, "mechanical.no_load_speed")[0]
    assert ns.shaft is None and any("motor or the output" in f for f in ns.flags)
    review = ingest.Review().accept(*[c.id for c in cands])
    with pytest.raises(ProfileError, match="which shaft"):
        ingest.build_profile("x", cands, review)
    review.answers[f"shaft:{ns.id}"] = "motor"
    assert ingest.build_profile("x", cands, review).data["mechanical"]["no_load_speed"]["shaft"] == "motor"


def test_ambiguity_answers_flow_into_the_derivation():
    cands = ingest.extract_candidates(RMCS_TEXT)
    review = ingest.Review().accept(*[c.id for c in cands])
    review.answers.update({"stall_current": "stall", "stall_torque": "practical"})
    prof = ingest.build_profile("x", cands, review, identity={"manufacturer": "Johnson", "model": "RMCS-3070"})
    assert prof.data["electrical"]["stall_current"]["meaning"] == "stall"
    assert prof.data["mechanical"]["stall_torque"]["meaning"] == "practical"
    m = derive_model(prof, {"stall_current": "stall"})
    assert m.params["R"].provenance == "calculated" and m.params["R"].value == pytest.approx(1.6)
    assert m.params["K"].value == pytest.approx(5.687e-3, rel=1e-3)


def test_different_values_for_one_field_are_flagged():
    cands = ingest.extract_candidates("Voltage 12 V\nSupply voltage 24 V\nNo load speed 1000 rpm (motor)\nGear ratio 10:1\n")
    vs = by_field(cands, "electrical.nominal_voltage")
    assert len(vs) == 2 and all(any("different values" in f for f in v.flags) for v in vs)


def test_unit_styles_and_thousands_separators():
    text = "No-load speed 13,100 r/min (motor)\nStall torque 4.5 oz-in (motor)\nNo-load current 120 mA\nTerminal resistance 3.2 ohm\nVoltage 12 V\nGear ratio 100:1\nEfficiency 72 %\nWeight 85 g\n"
    cands = ingest.extract_candidates(text)
    truth = {"mechanical.no_load_speed": 13100 * 2 * math.pi / 60, "mechanical.stall_torque": 4.5 * 0.00706155, "electrical.no_load_current": 0.12,
             "electrical.winding_resistance": 3.2, "electrical.nominal_voltage": 12.0, "gearbox.ratio": 100.0, "mechanical.mass": 0.085}
    s = ingest.extraction_score(cands, truth)
    assert s["fraction"] == 1.0 and not s["wrong"], s
    assert by_field(cands, "gearbox.efficiency")[0].unit == "%"


def test_deliberately_messy_table_nothing_silently_dropped_or_accepted():
    messy = """Specification table   (typical @25C)
Parameter | Value | Unit
Nominal Voltage |  12.0 |  V
No-Load  Speed|18000|rpm   (motor side)
No load current | 0,8 | A
Stall torque | n/a | kg.cm
Gear ratio | 180 :1
Weight    :  approx. 180g
Back-EMF constant || V/krpm
"""
    cands = ingest.extract_candidates(messy)
    table = ingest.confirmation_table(cands)
    found = {c.field for c in cands}
    assert "electrical.nominal_voltage" in found and "mechanical.no_load_speed" in found and "gearbox.ratio" in found and "mechanical.mass" in found
    assert "mechanical.stall_torque" not in found and "constants.back_emf_constant" not in found            # no numbers: not invented
    nl = by_field(cands, "electrical.no_load_current")[0]
    assert nl.value == 0.8 and any("decimal comma" in f for f in nl.flags)                                   # '0,8' is read as 0.8 AND flagged for the user
    for c in cands:
        assert f"| {c.id} |" in table                                                                       # every extracted item is visible for review
    review = ingest.Review()
    assert review.decisions == {}                                                                            # nothing accepted by default


def test_csv_and_text_files(tmp_path):
    p = tmp_path / "ds.csv"
    p.write_text("Parameter,Value,Unit\nNo load speed,18000,rpm\nNo load current,0.8,A\nVoltage,12,V\n")
    cands = ingest.extract_candidates(ingest.read_input(p), source=p.name)
    assert {c.field for c in cands} >= {"mechanical.no_load_speed", "electrical.no_load_current", "electrical.nominal_voltage"}
    t = tmp_path / "ds.txt"
    t.write_text(RMCS_TEXT)
    assert len(ingest.extract_candidates(ingest.read_input(t))) >= 9
    with pytest.raises(RuntimeError, match="unsupported"):
        ingest.read_input(tmp_path / "x.docx")


def test_text_pdf_roundtrip(tmp_path):
    fpdf = pytest.importorskip("fpdf")
    pytest.importorskip("pypdf")
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    page1 = ["CL-12-100 gearmotor", "Voltage 12 V", "Terminal resistance 3.2 ohm", "No-load speed 13,100 r/min (motor)", "No-load current 120 mA"]
    for line in page1:
        pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
    pdf.add_page()
    for line in ["Stall torque 4.5 oz-in (motor)", "Gear ratio 100:1", "Efficiency 72 %", "Weight 85 g", "Encoder 64 ppr"]:
        pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
    path = tmp_path / "ds.pdf"
    pdf.output(str(path))
    cands = ingest.extract_candidates(ingest.read_input(path), source="ds.pdf")
    truth = {"electrical.nominal_voltage": 12.0, "electrical.winding_resistance": 3.2, "mechanical.no_load_speed": 13100 * 2 * math.pi / 60,
             "electrical.no_load_current": 0.12, "mechanical.stall_torque": 4.5 * 0.00706155, "gearbox.ratio": 100.0, "mechanical.mass": 0.085}
    s = ingest.extraction_score(cands, truth)
    assert s["fraction"] >= 0.85 and not s["wrong"], s
    assert {c.page for c in cands} == {1, 2}                                       # page numbers are recorded


def test_scanned_input_degrades_gracefully_without_ocr(tmp_path, monkeypatch):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name in ("pytesseract",):
            raise ImportError(name)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    img = tmp_path / "scan.png"
    img.write_bytes(b"\x89PNG\r\n")
    with pytest.raises(RuntimeError, match="OCR needs"):
        ingest.read_input(img)


def test_interactive_wizard_with_scripted_answers():
    cands = ingest.extract_candidates("Voltage 12 V\nNo load speed 1000 rpm (motor)\nGear ratio 10:1\nStall torque 2 kg.cm (output)\n")
    answers = iter(["a", "a", "a", "e", "2.5", "kg.cm", "output", "theoretical"])
    shown = []
    rev = ingest.review_interactively(cands, input_fn=lambda _p: next(answers), print_fn=shown.append)
    assert "| id | field |" in shown[0] and len(rev.decisions) == 4
    assert rev.decisions[3] == {"edit": {"value": 2.5, "unit": "kg.cm", "shaft": "output"}} and rev.answers["stall_torque"] == "theoretical"


# ----------------------------------------------------------------------------------------------- curve digitiser
def test_axis_calibration_linear_and_log():
    ax = AxisCalibration(100, 0.0, 500, 8.0)
    assert ax.to_value(300) == pytest.approx(4.0) and ax.to_value(100) == 0.0
    lg = AxisCalibration(100, 1.0, 500, 1000.0, log=True)
    assert lg.to_value(300) == pytest.approx(math.sqrt(1000.0), rel=1e-9)
    inv = AxisCalibration(400, 0.0, 100, 1400.0)                                  # y axis grows upward in an image (pixel decreases)
    assert inv.to_value(250) == pytest.approx(700.0)
    with pytest.raises(ValueError):
        AxisCalibration(1, 0, 1, 5)
    with pytest.raises(ValueError):
        AxisCalibration(1, 0, 2, 5, log=True)


def test_digitising_a_synthetic_plotted_curve_recovers_the_truth():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    torque = np.linspace(0, 1400, 300)
    speed = 18000 * (1 - torque / 1500.0)                                          # a line like a motor speed-torque curve
    fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
    ax.plot(torque, speed, color=(1, 0, 0), linewidth=2)
    ax.set_xlim(0, 1500); ax.set_ylim(0, 20000)
    fig.canvas.draw()
    img = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
    h = img.shape[0]
    to_px = lambda x, y: ax.transData.transform((x, y)) * np.array([1, 1])
    (x0, y0), (x1, y1) = to_px(0, 0), to_px(1500, 20000)
    xcal = AxisCalibration(x0, 0.0, x1, 1500.0)
    ycal = AxisCalibration(h - y0, 0.0, h - y1, 20000.0)                         # image rows run top-down
    dig = Digitizer(xcal, ycal, "g.cm", "rpm")
    pts = dig.convert(trace_curve(img, (255, 0, 0), tol=80, step=5))
    xs, ys = np.array(pts).T
    assert len(pts) > 40
    assert np.max(np.abs(ys - 18000 * (1 - xs / 1500.0))) < 250                    # within about 1.2 % of full scale
    plt.close(fig)


def test_digitising_with_a_log_axis():
    ax = AxisCalibration(0, 1.0, 400, 10000.0, log=True)
    xs = ax.to_value([0, 100, 200, 300, 400])
    assert xs.tolist() == pytest.approx([1.0, 10.0, 100.0, 1000.0, 10000.0], rel=1e-9)
