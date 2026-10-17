"""G3B.7: the dtrl command-line interface (motor add / list / show / derive, tune, export)."""

import json
import re

import pytest
import yaml

from dtrl import cli
from models.motor_profile import load_profile

DATASHEET = """BR-24 gearmotor
Voltage 24 V
Terminal resistance 1.2 ohm
No-load speed 6000 rpm (motor)
No-load current 0.35 A
Stall torque 52 oz-in (motor)
Stall current 20 A (stall)
Gear ratio 50:1
Efficiency 80 %
Weight 0.9 kg
Encoder 500 ppr
"""


@pytest.fixture()
def lib(tmp_path, monkeypatch):
    monkeypatch.setenv("DTRL_MOTORS_DIR", str(tmp_path / "motors"))
    (tmp_path / "motors").mkdir()
    ds = tmp_path / "br24.txt"
    ds.write_text(DATASHEET)
    return tmp_path, ds


def test_list_and_show_use_the_configured_library(lib, capsys):
    assert cli.main(["motor", "list"]) == 0
    assert capsys.readouterr().out.strip() == ""                                   # empty temporary library
    assert cli.main(["motor", "show", "nope"]) == 1


def test_motor_add_with_scripted_decisions_then_derive_tune_export(lib, capsys):
    tmp, ds = lib
    from models import ingest
    cands = ingest.extract_candidates(DATASHEET)
    ids = {c.field: c.id for c in cands}
    decisions = {"decisions": {str(i): "accept" for i in ids.values()}, "answers": {"stall_torque": "theoretical", "encoder_mounted_on": "motor"}}
    dj = tmp / "decisions.json"
    dj.write_text(json.dumps(decisions))
    rc = cli.main(["motor", "add", "--input", str(ds), "--id", "br24", "--manufacturer", "Test", "--model", "BR-24", "--decisions", str(dj)])
    out = capsys.readouterr().out
    assert rc == 0 and "| id | field |" in out and "wrote" in out                   # the confirmation table was shown
    p = tmp / "motors" / "br24" / "profile.yaml"
    assert p.exists() and (tmp / "motors" / "br24" / "datasheets" / "br24.txt").exists()
    data = yaml.safe_load(p.read_text())
    assert data["electrical"]["nominal_voltage"]["provenance"] == "datasheet" and data["mechanical"]["stall_torque"]["shaft"] == "motor"
    assert load_profile("br24").data["gearbox"]["ratio"]["value"] == 50.0
    assert cli.main(["motor", "add", "--input", str(ds), "--id", "br24", "--decisions", str(dj)]) == 1          # no silent overwrite
    capsys.readouterr()

    assert cli.main(["motor", "list"]) == 0 and "br24" in capsys.readouterr().out
    assert cli.main(["motor", "derive", "--motor", "br24", "--out", str(tmp / "d.json")]) == 0
    dd = json.loads((tmp / "d.json").read_text())
    assert dd["gear_ratio"] == 50.0 and dd["out_counts_per_rev"] == 500 * 4 * 50 and dd["params"]["R"]["value"] == pytest.approx(1.2)
    capsys.readouterr()

    fast = ["--popsize", "6", "--maxiter", "6", "--restarts", "1"]
    assert cli.main(["tune", "--motor", "br24", "--load", "bare_shaft", "--out-dir", str(tmp / "rep")] + fast) == 0
    text = capsys.readouterr().out
    assert text.startswith("TIER 1") and "recommended gains" in text and not re.search(r"\b(perfect|optimal)\b", text, re.I)
    assert (tmp / "rep" / "recommendation.md").exists() and (tmp / "rep" / "recommendation.html").exists()

    out_py = tmp / "ctl.py"
    assert cli.main(["export", "--motor", "br24", "--load", "bare_shaft", "--format", "py", "--out", str(out_py)] + fast) == 0
    code = out_py.read_text()
    assert "TIER 1" in code and "RE-TUNE AFTER VALIDATION" in code and "class Controller" in code


def test_interactive_wizard_path(lib):
    tmp, ds = lib
    from types import SimpleNamespace

    answers = []
    from models import ingest
    for c in ingest.extract_candidates(DATASHEET):
        answers.append("a")                                                         # accept every candidate
    answers += ["stall", "theoretical"]                                              # ambiguity answers, if asked
    it = iter(answers + ["a"] * 10)
    ns = SimpleNamespace(input=str(ds), id="br24i", manufacturer="T", model="B", figures_at="motor", decisions=None, force=False)
    shown = []
    rc = cli.cmd_motor_add(ns, input_fn=lambda _p: next(it), print_fn=shown.append)
    assert rc == 0 and any("| id | field |" in s for s in shown)
    assert (tmp / "motors" / "br24i" / "profile.yaml").exists()


def test_rejecting_everything_creates_no_profile(lib, capsys):
    tmp, ds = lib
    dj = tmp / "none.json"
    dj.write_text(json.dumps({"decisions": {}, "answers": {}}))                     # nothing accepted
    assert cli.main(["motor", "add", "--input", str(ds), "--id", "empty", "--decisions", str(dj)]) == 1
    assert "required field is missing" in capsys.readouterr().out
    assert not (tmp / "motors" / "empty").exists()


def test_unextractable_input_and_bad_arguments(lib, tmp_path, capsys):
    junk = tmp_path / "junk.txt"
    junk.write_text("nothing useful here\n")
    assert cli.main(["motor", "add", "--input", str(junk), "--id", "junk", "--decisions", str(tmp_path / "x.json")]) == 2
    with pytest.raises(SystemExit):
        cli.main(["motor", "derive", "--motor", "x", "--answer", "novalue"])
    with pytest.raises(SystemExit):
        cli.main([])


def test_python_dash_m_entry_point_runs():
    import subprocess
    import sys

    r = subprocess.run([sys.executable, "-m", "dtrl", "motor", "list"], capture_output=True, text=True)
    assert r.returncode == 0 and "rmcs_3070" in r.stdout
