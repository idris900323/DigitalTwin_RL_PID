"""Generate ``autotune_360/config.generated.js`` from ``config/motor_parameters.yaml``.

The YAML is the single source of truth for every motor/plant/controller constant. The browser page and the
Node cross-implementation checks read the generated file instead of keeping their own copies.

Run from the repository root:

    python tools/generate_js_config.py            # rewrite the generated file and the copies inside the HTML
    python tools/generate_js_config.py --check    # exit 1 if either is out of date (used by tests/test_config_sync.py)

The HTML page is a single self-contained file, so the generated config and ``physics.js`` are also copied
between ``// <<BEGIN name>>`` / ``// <<END name>>`` markers inside it, and ``cad/JGB37-520_converted.glb`` is embedded
as base64 (``const GLB_B64``). The standalone files are the source; the copies inside the HTML are build products kept
in sync by this tool and checked by the tests. (One mesh for every demo: the 83k-triangle GLB, ~3 MB page.)
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "config" / "motor_parameters.yaml"
OUT_DIR = ROOT / "autotune_360"
HTML_PATH = OUT_DIR / "servo_pid_visualizer_360.html"
GENERATED = OUT_DIR / "config.generated.js"
PHYSICS = OUT_DIR / "physics.js"
GLB_PATH = ROOT / "cad" / "JGB37-520_converted.glb"

TAGS = ("DATASHEET", "CALCULATED", "ESTIMATED", "ASSUMED", "CAD", "EXPERIMENTAL", "UNKNOWN")
HEADER = "// GENERATED - do not edit; run `python tools/generate_js_config.py`"


def read_provenance(text: str) -> dict:
    """Map dotted YAML key paths to the provenance tag found in the line's trailing comment (best effort)."""
    out: dict = {}
    stack: list[tuple[int, str]] = []
    for line in text.splitlines():
        m = re.match(r"^(\s*)([A-Za-z0-9_]+):\s*(.*)$", line)
        if not m:
            continue
        indent, key, rest = len(m.group(1)), m.group(2), m.group(3)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, key))
        if "#" in rest:
            comment = rest.split("#", 1)[1]
            for tag in TAGS:
                if re.search(r"\b" + tag + r"\b", comment):
                    out[".".join(k for _, k in stack)] = tag
                    break
    return out


RECOMMENDATIONS = OUT_DIR / "recommendations.json"


def motor_library(base_cfg: dict) -> dict:
    """Every motor profile as the browser needs it: the plant used for simulation, derived parameters with intervals, conflicts."""
    sys.path.insert(0, str(ROOT))
    from models.derive import derive_model
    from models.motor_profile import list_motors, load_profile
    from models.motors import get_cfg

    lib = {}
    for mid in list_motors():
        prof = load_profile(mid)
        cfg = get_cfg(mid, base_cfg=copy.deepcopy(base_cfg))
        sc = cfg["simulation"]["active_electrical_scenario"]
        d, e = cfg["base_motor"]["derived"][sc], cfg["base_motor"]["estimated"]
        model = derive_model(prof)
        lib[mid] = {
            "name": prof.name, "synthetic": prof.synthetic, "scenario": sc,
            "supply": {"V_rated": cfg["supply"]["V_rated"]},
            "gearbox": {"ratio": cfg["gearbox"]["ratio"], "efficiency": d.get("gearbox_efficiency", cfg["gearbox"]["efficiency"])},
            "encoder": {"cpr": cfg["encoder"]["output_cpr"]},
            "motor": dict(R=d["R_ohm"], L=e["L_H"], Kt=d["Kt_Nm_per_A"], Ke=d["Ke_V_s_per_rad"], Jm=e["Jm_kgm2"],
                          Bm=d.get("Bm_Nms_per_rad", e["Bm_Nms_per_rad"])),
            "params": {k: {"value": v.value, "lo": v.lo, "hi": v.hi, "provenance": v.provenance, "confidence": v.confidence, "method": v.method}
                       for k, v in model.params.items()},
            "conflicts": [c["what"] for c in model.conflicts],
            "leastCertain": model.least_certain(),
            "hasPolicy": mid == "rmcs_3070",
        }
    return lib


def build_config(yaml_text: str) -> dict:
    cfg = yaml.safe_load(yaml_text)
    scen = cfg["base_motor"]["derived"]
    est = cfg["base_motor"]["estimated"]

    def motor(s):
        d = scen[s]
        if d.get("R_ohm") is None or d.get("Kt_Nm_per_A") is None:
            return None  # method_b cannot be simulated (no R, Kt); keep it out of the browser
        out = dict(R=d["R_ohm"], L=est["L_H"], Kt=d["Kt_Nm_per_A"], Ke=d["Ke_V_s_per_rad"],
                   Jm=est["Jm_kgm2"], Bm=d.get("Bm_Nms_per_rad", est["Bm_Nms_per_rad"]))
        if "gearbox_efficiency" in d:
            out["eff"] = d["gearbox_efficiency"]          # alternative sets carry their own efficiency
        return out

    j = cfg.get("joint", {})
    return {
        "activeScenario": cfg["simulation"]["active_electrical_scenario"],
        "scenarios": {s: m for s in scen if (m := motor(s)) is not None},
        "supply": {"V_rated": cfg["supply"]["V_rated"]},
        "gearbox": {"ratio": cfg["gearbox"]["ratio"], "efficiency": cfg["gearbox"]["efficiency"]},
        "encoder": {"cpr": cfg["encoder"]["output_cpr"], "noiseCountsRms": cfg["encoder"].get("noise_counts_rms", 0.0)},
        "simulation": {"dt": cfg["simulation"]["control_loop_dt_s"], "durationS": cfg["simulation"]["run_duration_s"],
                       "thetaRefDefaultDeg": cfg["simulation"]["theta_ref_default_deg"]},
        "controller": {"derivativeFilterTauS": cfg.get("controller", {}).get("derivative_filter_tau_s", 0.01)},
        "driver": {"currentLimitA": cfg.get("driver", {}).get("current_limit_A")},
        "joint": {"payloadMassKg": j.get("payload_mass_kg", 0.0), "armLengthM": j.get("arm_length_m", 0.0),
                  "armMassKg": j.get("arm_mass_kg", 0.0), "gravityOn": bool(j.get("gravity_on", False)),
                  "BJointNmsPerRad": j.get("B_joint_Nms_per_rad", 0.0), "tauCoulombNm": j.get("tau_coulomb_Nm", 0.0),
                  "omegaEpsRadS": j.get("omega_eps_rad_s", 0.01)},
        "feasibility": {"marginalMargin": cfg.get("feasibility", {}).get("marginal_margin", 1.2)},
        "pidDefaults": {k: cfg["pid_defaults"][k] for k in ("Kp", "Ki", "Kd")},
        "pidPresets": cfg.get("pid_presets", {}),
        "provenance": read_provenance(yaml_text),
        "yamlSha256": hashlib.sha256(yaml_text.encode("utf-8")).hexdigest(),
        "defaultMotor": "rmcs_3070",
        "motors": motor_library(cfg),
        "recommendations": json.loads(RECOMMENDATIONS.read_text(encoding="utf-8")) if RECOMMENDATIONS.exists() else {},
        "tierLabels": {1: "TIER 1 - datasheet estimate: safe starting point, expect to re-tune",
                       2: "TIER 2 - identified from bench data", 3: "TIER 3 - refined on hardware"},
    }


def generated_text(yaml_text: str) -> str:
    body = json.dumps(build_config(yaml_text), indent=2, sort_keys=False)
    return (f"{HEADER}\n// source: config/motor_parameters.yaml\n"
            f"const DTRL_CONFIG = {body};\n"
            "if (typeof module !== 'undefined' && module.exports) module.exports = DTRL_CONFIG;\n")


def block(name: str, content: str) -> str:
    return f"// <<BEGIN {name}>>\n{content.rstrip()}\n// <<END {name}>>"


def splice(html: str, name: str, content: str) -> str:
    pat = re.compile(r"// <<BEGIN " + re.escape(name) + r">>.*?// <<END " + re.escape(name) + r">>", re.S)
    if not pat.search(html):
        raise SystemExit(f"marker block '{name}' not found in {HTML_PATH.name}")
    return pat.sub(lambda m: block(name, content), html, count=1)


def splice_glb(html: str) -> str:
    b64 = base64.b64encode(GLB_PATH.read_bytes()).decode("ascii")
    pat = re.compile(r'const GLB_B64 = "[A-Za-z0-9+/=]*";')
    if not pat.search(html):
        raise SystemExit(f"'const GLB_B64' not found in {HTML_PATH.name}")
    return pat.sub(lambda m: f'const GLB_B64 = "{b64}";', html, count=1)


def norm(s: str) -> str:
    return s.replace("\r\n", "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="do not write; exit 1 if anything is out of date")
    args = ap.parse_args(argv)

    yaml_text = norm(YAML_PATH.read_text(encoding="utf-8"))
    gen = generated_text(yaml_text)
    physics = norm(PHYSICS.read_text(encoding="utf-8"))
    with open(HTML_PATH, encoding="utf-8", newline="") as fh:
        html_old = fh.read()
    crlf = "\r\n" in html_old
    html = splice_glb(splice(splice(norm(html_old), "config.generated.js", gen), "physics.js", physics))
    if crlf:
        html = html.replace("\n", "\r\n")

    stale = []
    if not GENERATED.exists() or norm(GENERATED.read_text(encoding="utf-8")) != gen:
        stale.append(GENERATED.name)
    if html != html_old:
        stale.append(HTML_PATH.name)
    if args.check:
        if stale:
            print("out of date: " + ", ".join(stale) + " -- run `python tools/generate_js_config.py`", file=sys.stderr)
            return 1
        return 0
    GENERATED.write_text(gen, encoding="utf-8", newline="\n")
    if html != html_old:
        with open(HTML_PATH, "w", encoding="utf-8", newline="") as fh:
            fh.write(html)
    print("updated:", ", ".join(stale) if stale else "nothing (already in sync)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
