"""Datasheet ingestion with a MANDATORY human confirmation step (G3B.2).

Inputs: pasted text or CSV, a text-based PDF (needs the optional ``pypdf``), a scanned PDF/image (needs the optional
``pytesseract`` + Tesseract; without it the function says so instead of failing silently), or a hand-written YAML profile.

Pipeline: ``extract_candidates`` pulls candidate values with units from tables and spec lines and attaches the page, the
surrounding text and a confidence; ``ambiguities`` and ``suspicions`` point at the classic traps (stall current that is only
labelled "max", a torque that equals another figure divided by the gear ratio, figures that could be at the motor or the output
shaft, duplicates that disagree). ``Review`` then requires an explicit decision on every candidate: nothing is written into a
profile as ``datasheet`` provenance without ``accept``; an edited value is recorded as provenance ``user``; undecided
candidates are rejected. Every unit conversion is logged in the profile's derivation log (``Profile.derivation_log``).

If a language model is ever used to help parse datasheet text, that text is untrusted DATA, never instructions, and the same
confirmation step still applies. This module itself uses regular expressions only.
"""

from __future__ import annotations

import csv
import io
import math
import pathlib
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import yaml

from models.motor_profile import FIELDS, UNITS, Profile, ProfileError, validate_profile

# ------------------------------------------------------------------------------------------------ labels and units
LABELS = [  # (regex, field, hint about the kind of unit expected)
    (r"no[- ]?load\s+speed", "mechanical.no_load_speed", "speed"),
    (r"no[- ]?load\s+current", "electrical.no_load_current", "current"),
    (r"(stall|locked[- ]rotor|starting)\s+torque", "mechanical.stall_torque", "torque"),
    (r"(stall|locked[- ]rotor|starting)\s+current", "electrical.stall_current", "current"),
    (r"(max(imum)?|peak)\s+(load\s+)?current|load\s+current", "electrical.stall_current", "current"),
    (r"(rated|continuous|nominal)\s+torque", "mechanical.rated_torque", "torque"),
    (r"torque\s+constant", "constants.torque_constant", "kt"),
    (r"back[- ]?emf\s+constant|voltage\s+constant", "constants.back_emf_constant", "ke"),
    (r"speed\s+constant", "constants.speed_constant", "kv"),
    (r"inductance", "electrical.inductance", "inductance"),
    (r"(terminal|winding|armature)\s+resistance|resistance", "electrical.winding_resistance", "resistance"),
    (r"(rated|nominal|operating)\s+voltage|supply\s+voltage|voltage", "electrical.nominal_voltage", "voltage"),
    (r"gear\s*(ratio|reduction)|reduction\s+ratio", "gearbox.ratio", "ratio"),
    (r"(gearbox\s+)?efficiency", "gearbox.efficiency", "fraction"),
    (r"(rotor\s+)?inertia", "mechanical.rotor_inertia", "inertia"),
    (r"weight|mass", "mechanical.mass", "mass"),
    (r"encoder|resolution|ppr|cpr|counts\s+per", "feedback.counts_per_rev", "counts"),
]
UNIT_ALIASES = {
    "rpm": "rpm", "r/min": "rpm", "rad/s": "rad/s", "a": "A", "ma": "mA", "v": "V", "mv": "mV", "ohm": "ohm", "ohms": "ohm", "Ω": "ohm",
    "mΩ": "mohm", "mohm": "mohm", "h": "H", "mh": "mH", "uh": "uH", "µh": "uH", "g": "g", "kg": "kg", "%": "%",
    "n.m": "N.m", "n·m": "N.m", "nm": "N.m", "n-m": "N.m", "mn.m": "mN.m", "mn·m": "mN.m", "mnm": "mN.m",
    "kg.cm": "kg.cm", "kg·cm": "kg.cm", "kgcm": "kg.cm", "kg-cm": "kg.cm", "kgf.cm": "kg.cm", "kgf·cm": "kg.cm",
    "g.cm": "g.cm", "g·cm": "g.cm", "gcm": "g.cm", "g-cm": "g.cm", "oz.in": "oz.in", "oz·in": "oz.in", "ozin": "oz.in", "oz-in": "oz.in",
    "lb.in": "lb.in", "ppr": "ppr", "cpr": "cpr", "counts/rev": "counts/rev", "rpm/v": "rpm/V", "v/krpm": "V/krpm", "mv/rpm": "mV/rpm",
    "mn.m/a": "mN.m/A", "n.m/a": "N.m/A", "oz.in/a": "oz.in/A", "g.cm/a": "g.cm/A", "kg.cm2": "kg.cm2", "g.cm2": "g.cm2", "kg.m2": "kg.m2",
    "v.s/rad": "V.s/rad", "rad/s/v": "rad/s/V",
}
UNIT_RE = (r"(rpm/V|V/krpm|mV/rpm|rad/s/V|mN[\.·\-]?m/A|N[\.·\-]?m/A|oz[\.·\-]?in/A|g[\.·\-]?cm/A|kgf?[\.·\-]?cm2|g[\.·\-]?cm2|kg[\.·]?m2|"
           r"kgf?[\.·\-]?cm|g[\.·\-]?cm|oz[\.·\-]?in|lb[\.·\-]?in|mN[\.·\-]?m|N[\.·\-]?m|r/min|rpm|rad/s|counts/rev|ppr|cpr|"
           r"mΩ|Ω|ohms?|mohm|uH|µH|mH|mA|mV|kg|g|%|A|V|H)")
NUM_RE = r"[-+]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?"
VALUE_RE = re.compile(rf"(?P<value>{NUM_RE})[\s|:]*(?P<unit>{UNIT_RE})?", re.I)
RATIO_RE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*:\s*1\b")
KIND_UNITS = {k: set(v) for k, v in UNITS.items()}


def parse_number(s: str):
    """(value, note). A lone comma followed by 1-2 digits is read as a decimal comma ('0,8' = 0.8) and noted; 13,100 is a thousand."""
    s = s.strip()
    if "." not in s and s.count(",") == 1 and 1 <= len(s.split(",")[1]) <= 2:
        return float(s.replace(",", ".")), "decimal comma read as a decimal point: check"
    return float(s.replace(",", "")), None


def canonical_unit(u: Optional[str]) -> Optional[str]:
    if u is None:
        return None
    key = u.strip().lower().replace(" ", "")
    return UNIT_ALIASES.get(key) or UNIT_ALIASES.get(key.replace("·", ".").replace("-", "."))


@dataclass
class Candidate:
    id: int
    field: str
    value: float
    unit: str
    shaft: Optional[str]
    page: int
    snippet: str
    confidence: str                  # high | medium | low
    flags: List[str] = field(default_factory=list)
    meaning: Optional[str] = None    # for stall current / stall torque

    def label(self) -> str:
        return f"{self.field} = {self.value:g} {self.unit}" + (f" ({self.shaft} shaft)" if self.shaft else "")


@dataclass
class Review:
    """The user's decisions. Anything not explicitly accepted is rejected."""

    decisions: Dict[int, object] = field(default_factory=dict)       # id -> "accept" | "reject" | {"edit": {value, unit, shaft?}}
    answers: Dict[str, str] = field(default_factory=dict)            # ambiguity answers

    def accept(self, *ids: int) -> "Review":
        for i in ids:
            self.decisions[i] = "accept"
        return self

    def reject(self, *ids: int) -> "Review":
        for i in ids:
            self.decisions[i] = "reject"
        return self

    def edit(self, cid: int, **changes) -> "Review":
        self.decisions[cid] = {"edit": changes}
        return self


# ------------------------------------------------------------------------------------------------ extraction
def _split_pages(text: str) -> List[str]:
    return text.split("\f") if "\f" in text else [text]


def _kind_for(unit: str) -> Optional[str]:
    for kind, units in KIND_UNITS.items():
        if unit in units and unit not in ("", "1"):
            return kind
    return None


def _expected_kinds(hint: str) -> set:
    return {"speed": {"speed"}, "current": {"current"}, "torque": {"torque"}, "voltage": {"voltage"}, "resistance": {"resistance"},
            "inductance": {"inductance"}, "kt": {"kt"}, "ke": {"ke"}, "kv": {"kv"}, "ratio": {"ratio"}, "fraction": {"fraction"},
            "inertia": {"inertia"}, "mass": {"mass"}, "counts": {"counts"}}[hint]


def extract_candidates(text: str, *, source: str = "pasted text") -> List[Candidate]:
    """Candidate profile values found in ``text`` (pages separated by form feeds). Nothing is accepted yet."""
    out: List[Candidate] = []
    section_shaft: Optional[str] = None
    for pno, page in enumerate(_split_pages(text), 1):
        for raw in page.splitlines():
            line = raw.strip()
            if not line:
                continue
            low = line.lower()
            if re.match(r"^[#=\-\s]*(gear\s*motor|gearbox|output|gear\s+shaft)\b[^0-9]*$", low) or low.rstrip(":") in ("gearmotor", "gearbox output", "output shaft", "at output"):
                section_shaft = "output"
            elif re.match(r"^[#=\-\s]*(base\s+motor|motor|dc\s+motor|motor\s+only)\b[^0-9]*$", low) or low.rstrip(":") in ("motor specifications", "base motor"):
                section_shaft = "motor"
            for rx, fld, hint in LABELS:
                m = re.search(rx, low)
                if not m:
                    continue
                tail = line[m.end():]
                cand = _parse_tail(tail, fld, hint)
                if cand is None:
                    continue
                value, unit, note = cand
                if FIELDS.get(fld, ("",))[0] == "ratio" and unit in ("", "1"):
                    pass
                shaft = None
                if FIELDS.get(fld, (None, False))[1]:
                    if re.search(r"\b(at\s+)?(gear\s*box\s+)?output|gear\s+shaft|\bgeared\b", low):
                        shaft = "output"
                    elif re.search(r"base\s+motor|motor\s+shaft|before\s+gear|\bmotor\b", low):
                        shaft = "motor"
                    else:
                        shaft = section_shaft
                if fld == "mechanical.rated_torque" and shaft == "motor":
                    fld = "mechanical.motor_rated_torque"
                conf = "high" if (unit not in ("", None) and shaft is not None) or not FIELDS.get(fld, (None, False))[1] else "medium"
                if shaft is None and FIELDS.get(fld, (None, False))[1]:
                    conf = "low"
                meaning = None
                if fld == "electrical.stall_current":
                    meaning = "stall" if re.search(r"stall|locked|starting", low) else "max_continuous"
                if fld == "mechanical.stall_torque":
                    meaning = "unknown"
                flags = [note] if note else []
                if fld == "electrical.stall_current" and meaning != "stall":
                    flags.append("labelled as a maximum/load current, not stall current")
                out.append(Candidate(len(out), fld, value, unit, shaft, pno, f"{source} p{pno}: {line[:160]}", conf, flags, meaning))
                break                                      # one field per line
    out = _dedupe(out)
    _add_suspicions(out)
    return out


def _parse_tail(tail: str, fld: str, hint: str):
    if hint == "ratio":
        r = RATIO_RE.search(tail) or re.search(rf"({NUM_RE})", tail)
        return (float(r.group(1).replace(",", "")), "", None) if r else None
    for m in VALUE_RE.finditer(tail):
        try:
            v, note = parse_number(m.group("value"))
        except ValueError:
            continue
        u = canonical_unit(m.group("unit"))
        if u is None:
            if hint == "fraction":
                return (v, "%" if v > 1.0 else "", note)
            continue
        if _kind_for(u) in _expected_kinds(hint) or (hint == "counts" and u in ("ppr", "cpr", "counts/rev")):
            return v, u, note
        if hint == "torque" and u == "N.m":
            return v, u, note
    return None


def _dedupe(c: List[Candidate]) -> List[Candidate]:
    seen, out = {}, []
    for x in c:
        key = (x.field, x.shaft, round(x.value, 9), x.unit)
        if key in seen:
            continue
        seen[key] = True
        x.id = len(out)
        out.append(x)
    return out


def _to_si(x: Candidate) -> Optional[float]:
    dim = FIELDS.get(x.field, (None,))[0]
    if dim is None or x.unit not in UNITS.get(dim, {}):
        return None
    return x.value * UNITS[dim][x.unit]


def _add_suspicions(cands: List[Candidate]) -> None:
    """Flag traps: a torque equal to another divided by the gear ratio, conflicting duplicates, unknown shaft side."""
    ratio = next((x.value for x in cands if x.field == "gearbox.ratio"), None)
    torques = [x for x in cands if FIELDS.get(x.field, (None,))[0] == "torque"]
    for a in torques:
        for b in torques:
            if a is b or ratio is None:
                continue
            sa, sb = _to_si(a), _to_si(b)
            if sa and sb and abs(sa / ratio - sb) / sb < 0.01 and sa > sb:
                a.flags.append(f"equals {b.label()} x {ratio:g} (gear ratio): possibly a reflected value, not an independent measurement")
                b.flags.append(f"equals {a.label()} / {ratio:g}: possibly a reflected value of the other torque")
    by_field: Dict[str, List[Candidate]] = {}
    for x in cands:
        by_field.setdefault(x.field, []).append(x)
    for fld, group in by_field.items():
        if len(group) > 1:
            vals = {round(_to_si(g) or 0.0, 9) for g in group}
            if len(vals) > 1:
                for g in group:
                    g.flags.append(f"{len(group)} different values found for {fld}: choose one or reject the rest")
    for x in cands:
        if FIELDS.get(x.field, (None, False))[1] and x.shaft is None:
            x.flags.append("cannot tell whether this figure is at the motor or the output shaft: you must say")
        if x.unit in ("g.cm", "kg.cm") and x.field in ("mechanical.stall_torque", "mechanical.rated_torque"):
            x.flags.append(f"check the unit: {x.unit} (a g.cm / kg.cm mix-up is a factor of 1000)")


def ambiguities(cands: List[Candidate]) -> List[dict]:
    """Questions the user must answer; do not guess."""
    q = []
    for x in cands:
        if x.field == "electrical.stall_current" and x.meaning != "stall":
            q.append({"key": "stall_current", "question": f"Is {x.value:g} {x.unit} the locked-rotor (stall) current, or a maximum rating?",
                      "options": ["stall", "max_continuous"], "candidate": x.id})
        if x.field == "mechanical.stall_torque":
            q.append({"key": "stall_torque", "question": f"Is {x.value:g} {x.unit} a theoretical (zero-speed) or a practical (current-limited) stall torque?",
                      "options": ["theoretical", "practical"], "candidate": x.id})
        if x.field == "feedback.counts_per_rev":
            q.append({"key": "encoder_mounted_on", "question": f"Is the {x.value:g} {x.unit} encoder on the motor shaft or on the gearbox output shaft?",
                      "options": ["motor", "output"], "candidate": x.id})
        if FIELDS.get(x.field, (None, False))[1] and x.shaft is None:
            q.append({"key": f"shaft:{x.id}", "question": f"Is {x.label()} at the motor shaft or the gearbox output shaft?", "options": ["motor", "output"], "candidate": x.id})
    return q


# ------------------------------------------------------------------------------------------------ file input
def read_input(path) -> str:
    """Text of a datasheet file: .txt/.md/.csv directly, .pdf via pypdf (optional), images via pytesseract (optional)."""
    p = pathlib.Path(path)
    ext = p.suffix.lower()
    if ext in (".txt", ".md", ".text"):
        return p.read_text(encoding="utf-8", errors="replace")
    if ext == ".csv":
        rows = list(csv.reader(io.StringIO(p.read_text(encoding="utf-8", errors="replace"))))
        return "\n".join(" ".join(c.strip() for c in r if c.strip()) for r in rows)
    if ext == ".pdf":
        try:
            import pypdf
        except ImportError as exc:
            raise RuntimeError("reading PDFs needs the optional package 'pypdf' (pip install pypdf), or paste the text instead") from exc
        reader = pypdf.PdfReader(str(p))
        pages = [(pg.extract_text() or "") for pg in reader.pages]
        if not any(t.strip() for t in pages):
            return _ocr(p)
        return "\f".join(pages)
    if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"):
        return _ocr(p)
    raise RuntimeError(f"unsupported input type {ext!r}; use .txt, .csv, .pdf, an image, or a hand-written profile .yaml")


def _ocr(path: pathlib.Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("this looks like a scanned/image datasheet: OCR needs the optional packages 'pytesseract' and 'Pillow' plus a Tesseract "
                           "install. Without OCR, type the values into a form/YAML or paste text") from exc
    return pytesseract.image_to_string(Image.open(path))


# ------------------------------------------------------------------------------------------------ confirmation and profile
def build_profile(motor_id: str, candidates: List[Candidate], review: Review, *, identity: Optional[dict] = None, gearbox_figures_at: str = "motor",
                  source: str = "datasheet") -> Profile:
    """Assemble and validate a profile from the ACCEPTED (or edited) candidates only."""
    data: dict = {"id": motor_id, "synthetic": False, "identity": identity or {"manufacturer": "", "model": motor_id},
                  "electrical": {}, "mechanical": {}, "constants": {}, "gearbox": {"stated_figures_at": gearbox_figures_at}, "feedback": {}, "drive": {}}
    log: List[str] = []
    for c in candidates:
        d = review.decisions.get(c.id, "reject")
        if d == "reject":
            continue
        value, unit, shaft, prov = c.value, c.unit, c.shaft, "datasheet"
        if isinstance(d, dict) and "edit" in d:
            e = d["edit"]
            value, unit, shaft, prov = e.get("value", value), e.get("unit", unit), e.get("shaft", shaft), "user"
            log.append(f"{c.field}: user edited {c.value:g} {c.unit} -> {value:g} {unit}")
        elif d != "accept":
            raise ValueError(f"candidate {c.id}: decision must be 'accept', 'reject' or an edit, got {d!r}")
        group, name = c.field.split(".")
        f = {"value": value, "unit": unit, "provenance": prov, "source": c.snippet if prov == "datasheet" else "typed by user (edited)",
             "confidence": "high" if (c.confidence == "high" and prov == "datasheet") else "medium"}
        if FIELDS[c.field][1]:
            shaft = shaft or review.answers.get(f"shaft:{c.id}")
            if shaft is None:
                raise ProfileError(f"{c.field}: you accepted a value without saying which shaft it refers to (answer the shaft question)")
            f["shaft"] = shaft
        if c.field == "electrical.stall_current":
            f["meaning"] = review.answers.get("stall_current") or c.meaning or "unknown"
        if c.field == "mechanical.stall_torque":
            f["meaning"] = review.answers.get("stall_torque") or "unknown"
        if unit not in ("", "1"):
            log.append(f"{c.field}: {value:g} {unit} accepted ({prov}); converted to SI on use")
        data[group][name] = f
    if data["feedback"].get("counts_per_rev"):
        data["feedback"].setdefault("mounted_on", review.answers.get("encoder_mounted_on", "motor"))
        unit = data["feedback"]["counts_per_rev"]["unit"]
        # PPR is pulses per channel per revolution: quadrature decoding (x4) is NOT included unless stated; CPR / counts already are
        default_quad = "false" if unit == "ppr" else "true"
        data["feedback"].setdefault("quadrature_included", review.answers.get("quadrature_included", default_quad) == "true")
    data["ambiguity_answers"] = dict(review.answers)
    validate_profile(data)
    return Profile(motor_id, data, None, log)


def confirmation_table(candidates: List[Candidate]) -> str:
    """Markdown table shown to the user: every extracted value with its source, confidence and flags."""
    rows = ["| id | field | value | shaft | confidence | page | flags | source snippet |", "|---|---|---|---|---|---|---|---|"]
    for c in candidates:
        rows.append(f"| {c.id} | {c.field} | {c.value:g} {c.unit} | {c.shaft or '?'} | {c.confidence} | {c.page} | {'; '.join(c.flags) or '-'} | {c.snippet[:90].replace('|', '/')} |")
    return "\n".join(rows)


def review_interactively(candidates: List[Candidate], input_fn: Callable[[str], str] = input, print_fn: Callable[[str], None] = print) -> Review:
    """Terminal wizard: show the table, ask accept/reject/edit per candidate, then the ambiguity questions."""
    review = Review()
    print_fn(confirmation_table(candidates))
    for c in candidates:
        ans = input_fn(f"[{c.id}] {c.label()}  flags: {'; '.join(c.flags) or 'none'}  -> (a)ccept / (r)eject / (e)dit [r]: ").strip().lower()
        if ans in ("a", "accept", "y", "yes"):
            review.accept(c.id)
        elif ans in ("e", "edit"):
            v = float(input_fn("  new value: "))
            u = input_fn(f"  unit [{c.unit}]: ").strip() or c.unit
            s = input_fn(f"  shaft (motor/output) [{c.shaft or ''}]: ").strip() or c.shaft
            review.edit(c.id, value=v, unit=u, shaft=s)
        else:
            review.reject(c.id)
    for q in ambiguities(candidates):
        if review.decisions.get(q["candidate"], "reject") == "reject":
            continue
        a = input_fn(f"{q['question']} {q['options']}: ").strip().lower()
        if a in q["options"]:
            review.answers[q["key"]] = a
    return review


def load_profile_yaml_candidates(path) -> Profile:
    """A hand-written YAML profile goes straight through validation (the user typed it, so it is its own confirmation)."""
    data = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    validate_profile(data)
    return Profile(data["id"], data, pathlib.Path(path))


def extraction_score(candidates: List[Candidate], truth: Dict[str, float]) -> Dict[str, object]:
    """Fraction of ``truth`` (field -> SI value) found with the right value; lists the missing and wrong ones (for tests/reports)."""
    found: Dict[str, float] = {}
    for c in candidates:
        si = _to_si(c)
        if si is not None and c.field not in found:
            found[c.field] = si
    right = [k for k, v in truth.items() if k in found and math.isclose(found[k], v, rel_tol=2e-3)]
    return {"fraction": len(right) / len(truth), "missing": [k for k in truth if k not in found],
            "wrong": [k for k in truth if k in found and k not in right]}
