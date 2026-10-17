"""Motor profiles: a typed, validated description of any brushed DC (gear)motor, with provenance on every number.

A profile lives in ``motors/<motor_id>/profile.yaml`` (original datasheet files in ``motors/<motor_id>/datasheets/``).
Every field is a mapping ``{value, unit, provenance, source, confidence}``:

* ``provenance``: ``datasheet`` | ``calculated`` | ``measured`` | ``assumed`` | ``user``
* ``source``: file and page, or "typed by user"
* ``confidence``: ``high`` | ``medium`` | ``low``

Torque and speed fields additionally carry ``shaft: motor`` or ``shaft: output`` (a classic source of error, so it is an
explicit REQUIRED field), and the gearbox block states whether the motor figures are ``at: motor`` or ``at: output``.

``validate_profile`` rejects unknown units, out-of-range values and missing shaft sides with a message that names the
field and the allowed units. ``to_si`` converts a field to SI and ``Profile.derivation_log`` records every conversion.

PRELIMINARY: a profile only records what a datasheet says; the model derived from it (``models/derive.py``) is
unvalidated until bench data exists.
"""

from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOTORS_DIR = ROOT / "motors"


def library_dir() -> pathlib.Path:
    """The motor library folder: ``motors/`` in the repository, or the folder named by the DTRL_MOTORS_DIR environment variable."""
    import os

    return pathlib.Path(os.environ.get("DTRL_MOTORS_DIR", MOTORS_DIR))

PROVENANCE = ("datasheet", "calculated", "measured", "assumed", "user")
CONFIDENCE = ("high", "medium", "low")
SHAFTS = ("motor", "output")
RPM = 2.0 * math.pi / 60.0

# unit -> factor to SI, per dimension
UNITS: Dict[str, Dict[str, float]] = {
    "voltage": {"V": 1.0, "mV": 1e-3},
    "current": {"A": 1.0, "mA": 1e-3},
    "resistance": {"ohm": 1.0, "mohm": 1e-3},
    "inductance": {"H": 1.0, "mH": 1e-3, "uH": 1e-6},
    "speed": {"rpm": RPM, "rad/s": 1.0},
    "torque": {"N.m": 1.0, "mN.m": 1e-3, "kg.cm": 0.0980665, "g.cm": 9.80665e-5, "oz.in": 0.00706155, "lb.in": 0.112985},
    "inertia": {"kg.m2": 1.0, "g.cm2": 1e-7, "kg.cm2": 1e-4},
    "mass": {"kg": 1.0, "g": 1e-3},
    "kt": {"N.m/A": 1.0, "mN.m/A": 1e-3, "oz.in/A": 0.00706155, "g.cm/A": 9.80665e-5, "kg.cm/A": 0.0980665},
    "ke": {"V.s/rad": 1.0, "mV.s/rad": 1e-3, "V/krpm": 60.0 / (2 * math.pi) / 1000.0, "mV/rpm": 60.0 / (2 * math.pi) / 1000.0},
    "kv": {"rpm/V": RPM, "rad/s/V": 1.0},      # speed constant; Ke = 1/Kv
    "friction": {"N.m.s/rad": 1.0, "mN.m.s/rad": 1e-3},
    "torque_coulomb": {"N.m": 1.0, "mN.m": 1e-3, "g.cm": 9.80665e-5},
    "ratio": {"": 1.0, "1": 1.0},
    "fraction": {"": 1.0, "1": 1.0, "%": 0.01},
    "angle": {"deg": 1.0, "arcmin": 1.0 / 60.0},
    "stiffness": {"N.m/rad": 1.0, "N.m/deg": 180.0 / math.pi},
    "frequency": {"Hz": 1.0, "kHz": 1e3},
    "counts": {"counts": 1.0, "counts/rev": 1.0, "ppr": 1.0, "cpr": 1.0},
}

# field path -> (dimension, needs_shaft, (min_SI, max_SI))
FIELDS: Dict[str, tuple] = {
    "electrical.nominal_voltage": ("voltage", False, (0.5, 1000.0)),
    "electrical.voltage_min": ("voltage", False, (0.0, 1000.0)),
    "electrical.voltage_max": ("voltage", False, (0.5, 1000.0)),
    "electrical.winding_resistance": ("resistance", False, (1e-3, 1e3)),
    "electrical.inductance": ("inductance", False, (0.0, 1.0)),
    "electrical.no_load_current": ("current", False, (1e-4, 100.0)),
    "electrical.stall_current": ("current", False, (1e-3, 1000.0)),
    "electrical.current_limit": ("current", False, (1e-3, 1000.0)),
    "mechanical.no_load_speed": ("speed", True, (1e-3, 2000.0 * 1000 * RPM)),
    "mechanical.stall_torque": ("torque", True, (1e-6, 1e3)),
    "mechanical.rated_torque": ("torque", True, (1e-6, 1e3)),
    "mechanical.motor_rated_torque": ("torque", True, (1e-6, 1e4)),
    "mechanical.rated_speed": ("speed", True, (1e-3, 2000.0 * 1000 * RPM)),
    "mechanical.rotor_inertia": ("inertia", False, (1e-12, 10.0)),
    "mechanical.viscous_friction": ("friction", False, (0.0, 1.0)),
    "mechanical.coulomb_friction": ("torque_coulomb", False, (0.0, 100.0)),
    "mechanical.mass": ("mass", False, (1e-3, 1e3)),
    "constants.torque_constant": ("kt", False, (1e-5, 10.0)),
    "constants.back_emf_constant": ("ke", False, (1e-5, 10.0)),
    "constants.speed_constant": ("kv", False, (1e-2, 1e6)),
    "gearbox.ratio": ("ratio", False, (1.0, 1e5)),
    "gearbox.efficiency": ("fraction", False, (0.05, 1.0)),
    "gearbox.backlash": ("angle", False, (0.0, 30.0)),
    "gearbox.torsional_stiffness": ("stiffness", False, (1e-3, 1e8)),
    "gearbox.max_output_torque": ("torque", False, (1e-6, 1e5)),
    "feedback.counts_per_rev": ("counts", False, (1.0, 1e7)),
    "drive.supply_voltage": ("voltage", False, (0.5, 1000.0)),
    "drive.pwm_frequency": ("frequency", False, (1.0, 1e6)),
    "drive.driver_current_limit": ("current", False, (1e-3, 1000.0)),
    "drive.driver_voltage_drop": ("voltage", False, (0.0, 50.0)),
    "drive.control_rate": ("frequency", False, (1.0, 1e6)),
}
REQUIRED = ("electrical.nominal_voltage", "mechanical.no_load_speed", "gearbox.ratio")
ENUMS = {
    "electrical.stall_current.meaning": ("stall", "max_continuous", "unknown"),
    "mechanical.stall_torque.meaning": ("theoretical", "practical", "unknown"),
    "gearbox.stated_figures_at": ("motor", "output"),
    "feedback.mounted_on": ("motor", "output"),
}


class ProfileError(ValueError):
    """A profile field is missing, has an unknown unit, an implausible value, or lacks provenance."""


def _get(d: dict, path: str):
    cur: Any = d
    for k in path.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def to_si(path: str, field_: dict) -> float:
    """Value of a validated field in SI units."""
    dim = FIELDS[path][0]
    return float(field_["value"]) * UNITS[dim][field_.get("unit", "")]


@dataclass
class Profile:
    id: str
    data: dict
    path: Optional[pathlib.Path] = None
    derivation_log: List[str] = field(default_factory=list)

    @property
    def synthetic(self) -> bool:
        return bool(self.data.get("synthetic", False))

    def field(self, path: str) -> Optional[dict]:
        return _get(self.data, path)

    def si(self, path: str) -> Optional[float]:
        f = self.field(path)
        if f is None or f.get("value") is None:
            return None
        v = to_si(path, f)
        if f.get("unit", "") not in ("", "1"):
            self.derivation_log.append(f"{path}: {f['value']} {f['unit']} -> {v:.6g} SI")
        return v

    def shaft(self, path: str) -> Optional[str]:
        f = self.field(path)
        return None if f is None else f.get("shaft")

    @property
    def name(self) -> str:
        i = self.data.get("identity", {})
        return f"{i.get('manufacturer', '')} {i.get('model', self.id)}".strip()


def validate_profile(data: dict) -> None:
    """Raise ``ProfileError`` naming the field if anything is wrong."""
    if "id" not in data:
        raise ProfileError("profile: missing 'id'")
    for path in REQUIRED:
        if _get(data, path) is None:
            raise ProfileError(f"{path}: required field is missing")
    for path, (dim, needs_shaft, (lo, hi)) in FIELDS.items():
        f = _get(data, path)
        if f is None:
            continue
        if not isinstance(f, dict) or "value" not in f:
            raise ProfileError(f"{path}: must be a mapping with value, unit, provenance, source, confidence")
        unit = f.get("unit", "")
        allowed = UNITS[dim]
        if unit not in allowed:
            raise ProfileError(f"{path}: unit {unit!r} is not allowed; allowed units: {', '.join(repr(u) for u in allowed)}")
        for key, options in (("provenance", PROVENANCE), ("confidence", CONFIDENCE)):
            if f.get(key) not in options:
                raise ProfileError(f"{path}: {key} must be one of {options}, got {f.get(key)!r}")
        if "source" not in f or not f["source"]:
            raise ProfileError(f"{path}: 'source' is required (file and page, or 'typed by user')")
        try:
            v = float(f["value"])
        except (TypeError, ValueError) as exc:
            raise ProfileError(f"{path}: value {f['value']!r} is not a number") from exc
        si = v * allowed[unit]
        if not (lo <= si <= hi):
            raise ProfileError(f"{path}: value {v:g} {unit} is outside the plausible range ({lo:g} .. {hi:g} in SI)")
        if needs_shaft and f.get("shaft") not in SHAFTS:
            raise ProfileError(f"{path}: 'shaft' must be 'motor' or 'output' (figures before and after the gearbox are easy to confuse)")
    for path, options in ENUMS.items():
        parent, _, leaf = path.rpartition(".")
        node = _get(data, parent) if parent else None
        val = node.get(leaf) if isinstance(node, dict) else _get(data, path)
        if val is not None and val not in options:
            raise ProfileError(f"{path}: must be one of {options}, got {val!r}")
    if _get(data, "gearbox.stated_figures_at") is None:
        raise ProfileError("gearbox.stated_figures_at: required ('motor' or 'output'): say which shaft the motor figures refer to")
    if _get(data, "feedback.counts_per_rev") is not None:
        for k in ("mounted_on", "quadrature_included"):
            if _get(data, f"feedback.{k}") is None:
                raise ProfileError(f"feedback.{k}: required when counts_per_rev is given")
    ts, ms = _get(data, "mechanical.stall_torque"), _get(data, "mechanical.mass")
    if ts and ms and ts.get("shaft") == "output":
        density = to_si("mechanical.stall_torque", ts) / to_si("mechanical.mass", ms)
        if density > 100.0:
            raise ProfileError(f"mechanical.stall_torque: {density:.0f} N.m per kg of motor mass is implausible; check the torque unit (g.cm versus kg.cm?)")
    vmin, vmax = to_si("electrical.voltage_min", _get(data, "electrical.voltage_min")) if _get(data, "electrical.voltage_min") else None, \
        to_si("electrical.voltage_max", _get(data, "electrical.voltage_max")) if _get(data, "electrical.voltage_max") else None
    if vmin is not None and vmax is not None and vmin > vmax:
        raise ProfileError("electrical.voltage_min is larger than voltage_max")


def load_profile(motor_id: str, motors_dir: Optional[pathlib.Path] = None) -> Profile:
    """Load and validate ``motors/<motor_id>/profile.yaml``."""
    motors_dir = pathlib.Path(motors_dir) if motors_dir is not None else library_dir()
    path = motors_dir / motor_id / "profile.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no motor profile {motor_id!r} (looked for {path}); available: {', '.join(list_motors(motors_dir))}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data.get("id") != motor_id:
        raise ProfileError(f"profile id {data.get('id')!r} does not match its folder {motor_id!r}")
    validate_profile(data)
    return Profile(motor_id, data, path)


def list_motors(motors_dir: Optional[pathlib.Path] = None) -> List[str]:
    """Ids of all motor folders that contain a profile."""
    base = pathlib.Path(motors_dir) if motors_dir is not None else library_dir()
    return sorted(p.parent.name for p in base.glob("*/profile.yaml"))
