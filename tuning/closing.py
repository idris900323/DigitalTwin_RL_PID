"""Closing the loop with real data (G3B.6): Tier 1 -> Tier 2 (identified) -> Tier 3 (refined on hardware).

* ``profile_with_identification`` turns an identification result (``validation.identify``) into a CANDIDATE profile: identified values
  get provenance ``measured`` with intervals from the fit; the original profile is never modified.
* ``tier_after_identification`` refuses Tier 2 unless the identified model passed the validation thresholds on held-out data.
* ``relay_analysis`` extracts the ultimate gain and period from a logged relay-feedback test; ``RelayController`` is the matching
  (hysteretic) relay for simulation. ``refine_with_relay`` adjusts the inertia estimate until the model reproduces the measured
  relay oscillation, then re-tunes at Tier 3.

Safety limits for the real relay test are in ``docs/onhardware_tuning.md``. Everything stays PRELIMINARY until validated.
"""

from __future__ import annotations

import copy
import math
import pathlib
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import yaml
from scipy.optimize import minimize_scalar

from models.motor_profile import Profile
from tuning.recommend import Recommendation, recommend
from tuning.tiers import Tier, tier_for

MEASURED_SOURCE = "validation/identify.py (bench data)"


def _field(value, unit, rel, source=MEASURED_SOURCE):
    return {"value": float(value), "unit": unit, "provenance": "measured", "source": source, "confidence": "high", "uncertainty_rel": float(rel)}


def profile_with_identification(profile: Profile, ident, *, source: str = MEASURED_SOURCE, min_rel: float = 0.02) -> Profile:
    """Copy of ``profile`` with every IDENTIFIABLE parameter replaced by its measured value and interval. Others stay as they were."""
    data = copy.deepcopy(profile.data)
    log = list(profile.derivation_log)
    mapping = {"R": ("electrical.winding_resistance", "ohm"), "Ke": ("constants.back_emf_constant", "V.s/rad"),
               "Kt": ("constants.torque_constant", "N.m/A"), "Jm": ("mechanical.rotor_inertia", "kg.m2"),
               "Bm": ("mechanical.viscous_friction", "N.m.s/rad")}
    for name, (path, unit) in mapping.items():
        e = ident.estimates.get(name)
        if e is None or not e.identifiable:
            continue
        rel = max((e.ci95[1] - e.ci95[0]) / (2.0 * e.value), min_rel)
        group, leaf = path.split(".")
        data.setdefault(group, {})[leaf] = _field(e.value, unit, rel, source)
        log.append(f"{path}: replaced by measured {e.value:.5g} {unit} (+-{rel * 100:.1f} %)")
    data["identification"] = {"status": ident.status, "not_identifiable": [n for n, e in ident.estimates.items() if not e.identifiable]}
    return Profile(profile.id, data, None, log)


def save_profile(profile: Profile, path) -> pathlib.Path:
    """Write a profile to a SEPARATE file (never over the original)."""
    p = pathlib.Path(path)
    p.write_text("# CANDIDATE profile written by tuning/closing.py: values with provenance 'measured' come from bench data\n"
                 + yaml.safe_dump(profile.data, sort_keys=False), encoding="utf-8")
    return p


def tier_after_identification(ident, comparison_passed: Optional[bool], *, has_bench_data: bool = True) -> Tier:
    """Tier 2 only if the identification is complete enough to determine the model AND the held-out comparison passed."""
    complete = ident.status == "ok"
    return tier_for(has_bench_data=has_bench_data, identification_passed=bool(complete and comparison_passed), hardware_refined=False)


# ----------------------------------------------------------------------------------------------- relay feedback
class RelayController:
    """Relay with hysteresis, usable as ``twin.pid`` in simulation: output +/-d, switching when the error crosses +/-h."""

    def __init__(self, d_volts: float, hysteresis: float = 0.0):
        self.d, self.h = d_volts, hysteresis
        self.reset()

    def reset(self):
        self.state = 1.0

    def step(self, error: float) -> float:
        if error > self.h:
            self.state = 1.0
        elif error < -self.h:
            self.state = -1.0
        return self.d * self.state


@dataclass
class RelayResult:
    Ku: float
    Tu: float
    amplitude: float
    cycles: int
    zn_gains: Tuple[float, float, float]
    tyreus_luyben_gains: Tuple[float, float, float]


def relay_analysis(t, y, d_volts: float, *, min_cycles: int = 4, skip_cycles: int = 2) -> RelayResult:
    """Ultimate gain and period from a relay-feedback test. ``y`` is the output angle in RADIANS, ``d_volts`` the relay amplitude.

    Ku = 4 d / (pi a) (describing function), Tu = mean period of the oscillation of y about its mean after ``skip_cycles``."""
    t, y = np.asarray(t, float), np.asarray(y, float)
    yc = y - np.mean(y[len(y) // 2:])
    up = np.where((yc[:-1] < 0) & (yc[1:] >= 0))[0]
    if len(up) < min_cycles + skip_cycles + 1:
        raise ValueError(f"only {max(len(up) - 1, 0)} oscillation cycles found; need at least {min_cycles + skip_cycles}: lengthen the test or raise the relay amplitude")
    times = t[up[skip_cycles:]]
    Tu = float(np.mean(np.diff(times)))
    pp = [np.ptp(yc[up[i]:up[i + 1]]) for i in range(skip_cycles, len(up) - 1)]        # peak-to-peak of each full cycle
    amp = float(0.5 * np.mean(pp))
    Ku = 4.0 * d_volts / (math.pi * amp)
    zn = (0.6 * Ku, 1.2 * Ku / Tu, 0.075 * Ku * Tu)
    tl = (0.31 * Ku, 0.31 * Ku / (2.2 * Tu), 0.31 * Ku * Tu / 6.3)
    return RelayResult(Ku, Tu, amp, len(up) - 1, zn, tl)


def simulate_relay(cfg: dict, d_volts: float, hysteresis_rad: float, *, t_end: float = 3.0, payload_kg: float = 0.0, load=None, seed: int = 0):
    """Run a relay test on the twin (the same experiment you would run on the rig). Returns (t, theta_rad)."""
    from models.factory import build_twin_from_config
    from models.joint import Joint, JointParams

    j = Joint(JointParams(payload_mass_kg=payload_kg, arm_length_m=load.arm_length_m if load else 0.0, gravity_on=False))
    tw = build_twin_from_config(cfg, 1.0, 0.0, 0.0, joint=j, seed=seed)
    tw.pid = RelayController(d_volts, hysteresis_rad)
    log = tw.run(0.0, int(round(t_end / tw.dt)))
    return np.asarray(log["t"]), np.asarray(log["theta_out"])


def refine_with_relay(rec: Recommendation, relay: RelayResult, *, d_volts: float, hysteresis_rad: float, **recommend_kwargs) -> Recommendation:
    """Tier 3: scale the rotor-inertia estimate until the model reproduces the measured relay oscillation, then re-tune."""
    base_Jm = rec.model.params["Jm"].value

    def mismatch(logs):
        cfg = copy.deepcopy(rec.cfg)
        cfg["base_motor"]["estimated"]["Jm_kgm2"] = base_Jm * math.exp(logs)
        t, th = simulate_relay(cfg, d_volts, hysteresis_rad, t_end=3.0, load=rec.load, payload_kg=rec.load.payload_max_kg)
        try:
            r = relay_analysis(t, th, d_volts)
        except ValueError:
            return 10.0
        return (math.log(r.Tu / relay.Tu)) ** 2 + (math.log(r.Ku / relay.Ku)) ** 2

    res = minimize_scalar(mismatch, bounds=(math.log(0.2), math.log(5.0)), method="bounded", options={"xatol": 1e-3})
    new_Jm = base_Jm * math.exp(res.x)
    # the relay-matched inertia replaces the model's Jm (+-5 %); the rest of the model and config stay as they were
    cfg = copy.deepcopy(rec.cfg)
    cfg["base_motor"]["estimated"]["Jm_kgm2"] = new_Jm
    return recommend(rec.motor_id, rec.load_id, tier=Tier.REFINED, model=_with_jm(rec.model, new_Jm), cfg=cfg, load=rec.load, **recommend_kwargs)


def _with_jm(model, Jm: float):
    from models.derive import Interval

    m = copy.deepcopy(model)
    m.params["Jm"] = Interval(Jm, Jm * 0.95, Jm * 1.05, "measured", "high", "relay-feedback refinement")
    m.conflicts = list(m.conflicts)
    m.trail = list(m.trail) + [f"Jm replaced by the relay-matched value {Jm:.4g} kg.m^2 (+-5 %)"]
    return m
