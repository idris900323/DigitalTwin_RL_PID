"""Load and task definition (G3B.4): what the motor has to drive and what "good" means for the tuning.

A PID is only right for a specific load and task. ``loads/<id>.yaml`` gives the load (arm, payload range, gravity,
friction) and the task (step targets, accuracy, overshoot and settling limits, current/voltage limits, allowed noise).
``check_drivable`` rejects loads the motor cannot drive (torque-infeasible) up front, with numbers.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import List, Optional

import yaml

from models.feasibility import feasibility

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOADS_DIR = ROOT / "loads"


class LoadError(ValueError):
    """The load/task file is invalid, or the load cannot be driven by the motor."""


@dataclass
class Load:
    id: str
    arm_length_m: float
    payload_min_kg: float
    payload_max_kg: float
    arm_mass_kg: float = 0.0
    gravity: bool = False
    viscous: float = 0.0
    coulomb: float = 0.0
    targets_deg: List[float] = field(default_factory=lambda: [90.0])
    accuracy_deg: float = 0.5
    max_overshoot_pct: float = 5.0
    max_settling_s: float = 1.0
    max_current_A: Optional[float] = None
    max_voltage_V: Optional[float] = None
    max_noise_V_rms: float = 0.6
    trajectory: str = "step"

    @property
    def payload_nominal_kg(self) -> float:
        return 0.5 * (self.payload_min_kg + self.payload_max_kg)

    def payloads(self, n: int = 3) -> List[float]:
        if n <= 1 or self.payload_max_kg == self.payload_min_kg:
            return [self.payload_max_kg]
        return [self.payload_min_kg + (self.payload_max_kg - self.payload_min_kg) * k / (n - 1) for k in range(n)]


def load_load(load_id: str, loads_dir: pathlib.Path = LOADS_DIR) -> Load:
    """Read ``loads/<load_id>.yaml`` (or a path)."""
    path = pathlib.Path(load_id) if str(load_id).endswith(".yaml") else loads_dir / f"{load_id}.yaml"
    if not path.exists():
        raise LoadError(f"no load file {path}")
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        ld, tk = d["load"], d["task"]
        pm = ld["payload_mass_kg"]
        pmin, pmax = (pm["min"], pm["max"]) if isinstance(pm, dict) else (pm, pm)
        load = Load(d["id"], float(ld["arm_length_m"]), float(pmin), float(pmax), float(ld.get("arm_mass_kg", 0.0)), bool(ld.get("gravity", False)),
                    float(ld.get("joint_viscous_friction", 0.0)), float(ld.get("joint_coulomb_friction", 0.0)),
                    [float(x) for x in tk.get("target_deg", [90.0])], float(tk.get("accuracy_deg", 0.5)), float(tk.get("max_overshoot_pct", 5.0)),
                    float(tk.get("max_settling_s", 1.0)), tk.get("max_current_A"), tk.get("max_voltage_V"),
                    float(tk.get("max_effort_noise_V_rms", 0.6)), tk.get("trajectory", "step"))
    except KeyError as exc:
        raise LoadError(f"{path.name}: missing field {exc}") from exc
    if load.payload_min_kg > load.payload_max_kg:
        raise LoadError(f"{path.name}: payload min exceeds max")
    if load.trajectory != "step":
        raise LoadError(f"{path.name}: trajectory {load.trajectory!r} is not supported yet (only 'step'); ramp/trapezoid/sinusoid are follow-ups")
    return load


def check_drivable(cfg: dict, load: Load, *, v_pct: float = 100.0) -> List[dict]:
    """Feasibility of every (payload extreme, target) pair. Raises ``LoadError`` with numbers if any is infeasible."""
    rows, bad = [], []
    for m in (load.payload_min_kg, load.payload_max_kg):
        for tgt in load.targets_deg:
            f = feasibility(cfg, m, load.arm_length_m, tgt, gravity=load.gravity, v_pct=v_pct, arm_mass_kg=load.arm_mass_kg)
            rows.append(dict(payload_kg=m, target_deg=tgt, **{k: f[k] for k in ("tau_hold_peak", "tau_avail", "margin_path", "status")}))
            if f["status"] == "infeasible":
                bad.append(f"payload {m:g} kg to {tgt:g} deg needs {f['tau_hold_peak']:.3g} N.m but the motor gives {f['tau_avail']:.3g} N.m "
                           f"(margin {f['margin_path']:.2f})")
    if bad:
        raise LoadError("load cannot be driven (torque-infeasible, margin below 1; upper bound that ignores back-EMF): " + "; ".join(bad))
    return rows
