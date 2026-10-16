"""G3.1: simulate_pid.py reproduces the baseline table, honours its flags and regenerates byte-identical outputs."""

import csv
import math

import pytest

from simulation import simulate_pid

OUTPUTS = ["pid_test_sequence.csv", "pid_test_sequence.md", "pid_test_sequence_raw.csv", "pid_sequence_angle.png",
           "pid_sequence_error.png", "pid_sequence_voltage.png", "pid_sequence_current.png"]

# rise_s, overshoot_pct, settle_s (nan = never), sse_deg -- tests/baseline_numbers.md (Task 0.2)
BASELINE = {
    "1 low P": (1.765, 0.0, math.nan, -7.99),
    "2a higher P": (0.171, 6.65, 0.467, -0.003),
    "2b highest P": (0.157, 11.2, 0.459, 0.012),
    "3 P+D (Tuned)": (0.190, 1.73, 0.292, -0.011),
    "4 P+I": (0.169, 9.72, 0.531, 0.145),
    "5 full PID": (0.188, 3.04, 0.514, 0.690),
    "legacy default": (0.223, 42.2, 1.826, 1.351),
}


def read_table(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["case"]: r for r in csv.DictReader(f)}


@pytest.fixture(scope="module")
def default_run(tmp_path_factory):
    d = tmp_path_factory.mktemp("seq")
    assert simulate_pid.main(["--out-dir", str(d)]) == 0
    return d


def test_default_run_reproduces_task0_table(default_run):
    rows = read_table(default_run / "pid_test_sequence.csv")
    assert set(rows) == set(BASELINE)
    for name, (rise, os_, settle, sse) in BASELINE.items():
        r = rows[name]
        assert float(r["rise_s"]) == pytest.approx(rise, abs=0.005)
        assert float(r["overshoot_pct"]) == pytest.approx(os_, abs=0.1)
        if math.isnan(settle):
            assert r["settle_s"] == ""
        else:
            assert float(r["settle_s"]) == pytest.approx(settle, abs=0.005)
        assert float(r["sse_deg"]) == pytest.approx(sse, abs=0.01)


def test_all_outputs_written_with_schema(default_run):
    for f in OUTPUTS + ["pid_sequence_manifest.json"]:
        assert (default_run / f).exists() and (default_run / f).stat().st_size > 0
    header = (default_run / "pid_test_sequence_raw.csv").read_text().splitlines()[0].split(",")
    from simulation.rawlog import RAW_COLUMNS
    assert tuple(header) == RAW_COLUMNS
    md = (default_run / "pid_test_sequence.md").read_text()
    assert "preliminary" in md.lower() and "What the sequence shows" in md and "validated" not in md.lower().replace("not validated", "")


def test_method_a_reproduces_documented_overshoot_and_never_settles(tmp_path):
    simulate_pid.main(["--out-dir", str(tmp_path), "--params", "method_a"])
    r = read_table(tmp_path / "pid_test_sequence.csv")["legacy default"]
    assert float(r["overshoot_pct"]) == pytest.approx(66.8, abs=0.3)
    assert r["settle_s"] == ""                                   # never settles


def test_method_b_is_rejected_not_silently_simulated():
    with pytest.raises(SystemExit):
        simulate_pid.main(["--params", "method_b"])


def test_outputs_are_byte_identical_on_rerun(default_run, tmp_path):
    simulate_pid.main(["--out-dir", str(tmp_path)])
    for f in OUTPUTS:
        assert (default_run / f).read_bytes() == (tmp_path / f).read_bytes(), f


def test_flags_arm_gravity_target_noise(tmp_path):
    simulate_pid.main(["--out-dir", str(tmp_path), "--arm-mass", "0.5", "--arm-length", "0.10", "--gravity",
                       "--target-deg", "180", "--t-end", "3", "--dt", "0.001", "--noise-counts", "1", "--seed", "4"])
    rows = read_table(tmp_path / "pid_test_sequence.csv")
    assert len(rows) == 7
    raw = (tmp_path / "pid_test_sequence_raw.csv").read_text().splitlines()
    assert len(raw) == 1 + 7 * 3000
    assert "180" in raw[1] and ",0.5,0.1,1," in raw[1]                   # target, payload, arm length, gravity on
    manifest = (tmp_path / "pid_sequence_manifest.json").read_text()
    assert "C:\\\\" not in manifest and "Users" not in manifest          # no local absolute paths in artefacts


def test_plot_styles_are_fixed_and_unique_per_method():
    from simulation import plotstyle
    styles = [tuple(plotstyle.style(n).values()) for n in plotstyle.METHODS]
    assert len(set(styles)) == len(styles)
    with pytest.raises(KeyError):
        plotstyle.style("not a registered method")
