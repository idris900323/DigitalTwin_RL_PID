"""G2.1: the YAML is the single source of truth; generated JS config must match it; no copies of motor constants.

* `tools/generate_js_config.py --check` fails if config.generated.js, or the copies of it and of physics.js
  inlined in the HTML page, are out of date (so a hand-edit of the YAML cannot silently desynchronise the browser).
* An AST/regex scan fails if a motor, plant or controller constant is hard-coded outside the YAML, the generated
  file, and the tests (which compare against datasheet values on purpose).
"""

import ast
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import generate_js_config as gen  # noqa: E402

YAML_TEXT = (ROOT / "config" / "motor_parameters.yaml").read_text(encoding="utf-8").replace("\r\n", "\n")


def test_generated_files_are_in_sync():
    assert gen.main(["--check"]) == 0


def test_hand_editing_the_yaml_is_detected():
    edited = YAML_TEXT.replace("Kt_Nm_per_A: 1.974e-3", "Kt_Nm_per_A: 2.1e-3", 1)
    assert edited != YAML_TEXT
    committed = (ROOT / "autotune_360" / "config.generated.js").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert gen.generated_text(edited) != committed           # the check would fail
    assert gen.generated_text(YAML_TEXT) == committed         # and the unedited YAML reproduces the committed file


def test_generated_header_and_content():
    text = (ROOT / "autotune_360" / "config.generated.js").read_text(encoding="utf-8")
    assert text.startswith("// GENERATED - do not edit; run `python tools/generate_js_config.py`")
    body = json.loads(text[text.index("const DTRL_CONFIG = ") + len("const DTRL_CONFIG = "):text.index(";\nif (typeof")])
    assert body["activeScenario"] == "method_c" and body["scenarios"]["method_c"]["Ke"] == 6.366e-3
    assert "method_b" not in body["scenarios"]                # no R/Kt, cannot be simulated
    assert body["encoder"]["cpr"] == 9360 and body["supply"]["V_rated"] == 12.0
    assert len(body["yamlSha256"]) == 64


def test_provenance_tags_are_carried_over():
    prov = gen.read_provenance(YAML_TEXT)
    assert prov["supply.V_rated"] == "DATASHEET"
    assert prov["gearbox.efficiency"] == "ESTIMATED"
    assert prov["encoder.noise_counts_rms"] == "ASSUMED"
    assert prov["base_motor.estimated.Jm_kgm2"] == "ESTIMATED"


# ------------------------------------------------------------------ no hard-coded plant constants
# `html/` holds the frozen base copies of the original code (the reference oracle, see tests/test_base_code_oracle.py):
# they intentionally contain the original hard-coded constants and must not be modified, so they are not scanned.
PY_SOURCES = [p for p in ROOT.rglob("*.py")
              if not {".git", "tests", "__pycache__", "html"} & set(p.relative_to(ROOT).parts)
              and p.name != "generate_js_config.py"]
FORBIDDEN_NUMBERS = {9360, 18000, 18000.0, 1.974e-3, 6.366e-3, 5.0e-7}     # 9360 CPR, 18000 RPM, Kt, Ke, Jm
FORBIDDEN_NAMES = {"R", "Kt", "Ke", "Jm", "Bm", "eta", "eff", "V_rated", "ratio", "cpr", "output_cpr"}


def _numeric(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)


@pytest.mark.parametrize("path", PY_SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_hardcoded_constants_in_python(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if _numeric(node) and node.value in FORBIDDEN_NUMBERS:
            bad.append(f"line {node.lineno}: literal {node.value}")
        if isinstance(node, ast.keyword) and node.arg in FORBIDDEN_NAMES and _numeric(node.value):
            bad.append(f"line {node.value.lineno}: {node.arg}={node.value.value}")
        if isinstance(node, ast.Assign) and _numeric(node.value):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in FORBIDDEN_NAMES:
                    bad.append(f"line {node.lineno}: {t.id} = {node.value.value}")
        if isinstance(node, ast.AnnAssign) and node.value is not None and _numeric(node.value) \
                and isinstance(node.target, ast.Name) and node.target.id in FORBIDDEN_NAMES:
            bad.append(f"line {node.lineno}: {node.target.id} = {node.value.value}")
    assert not bad, f"hard-coded plant constants in {path.name}: {bad}"


def _js_app_text(path: pathlib.Path) -> str:
    s = path.read_text(encoding="utf-8")
    s = re.sub(r"// <<BEGIN config\.generated\.js>>.*?// <<END physics\.js>>", "", s, flags=re.S)
    s = re.sub(r'const GLB_B64 = "[^"]*"', "", s)
    s = re.sub(r"const RL_POLICY = \{.*?\};", "", s, flags=re.S)
    i = s.find("// ---------- configuration and physics")
    return s[i:] if i >= 0 else s


JS_CONST = re.compile(r"\b(R|Kt|Ke|Jm|Bm|eta|eff|V_rated|ratio|cpr)\s*[:=]\s*[0-9]")
JS_NUMBERS = re.compile(r"(?<![\w.])(1\.974e-3|6\.366e-3|9360|18000|5e-7)(?![\w.])")


@pytest.mark.parametrize("name", ["physics.js", "servo_pid_visualizer_360.html"])
def test_no_hardcoded_constants_in_js(name):
    path = ROOT / "autotune_360" / name
    text = _js_app_text(path)
    text = re.sub(r"//[^\n]*", "", text)        # ignore comments
    assert not JS_CONST.findall(text), JS_CONST.findall(text)
    assert not JS_NUMBERS.findall(text), JS_NUMBERS.findall(text)
