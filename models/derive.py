"""Derive a complete, physically consistent plant model (with uncertainty) from whatever a motor profile contains.

An ideal brushed DC motor in SI has Ke = Kt = K (V.s/rad = N.m/A). From the profile's datasheet figures this module
produces ``R, L, K (= Kt = Ke), Jm, Bm, tau_c, eta`` each with a value, an interval [lo, hi], a provenance tag and a
derivation trail:

  R    winding resistance if given, else V / stall current, else a class prior
  K    no-load balance V = R*I0 + K*w0; cross-checked against any stated Kt, Ke/Kv and against the stall torque
  Bm   K*I0/w0: the no-load current attributed to viscous friction (an upper bound: part is Coulomb)
  eta  stated, else fitted from the output stall torque (K, I_stall, N) if given, else a class prior
  Jm   stated, else a rotor-cylinder approximation from the motor mass (low confidence), else a wide prior
  L    stated, else 0 (neglected) with an interval up to a few mH

Disagreeing sources (for example K from the no-load balance versus K from the stall torque, or a stall current that is only
labelled "max") are reported as ``conflicts`` with candidate resolutions; the engine never silently forces them to agree.
The three least certain parameters (interval width weighted by influence on the closed loop, from the sensitivity study)
are named so the user knows what to measure first.

PRELIMINARY: everything here is calculated from a datasheet, not validated against hardware.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from models.motor_profile import Profile

KGCM = 0.0980665
INFLUENCE = {"Jm": 1.0, "R": 0.8, "K": 0.8, "eta": 0.5, "Bm": 0.35, "L": 0.1, "tau_c": 0.1}   # from results/sensitivity (bare + loaded)
TIER_REL = {"datasheet": 0.05, "calculated": 0.10, "assumed": 0.30}


@dataclass
class Interval:
    value: float
    lo: float
    hi: float
    provenance: str           # datasheet | calculated | assumed
    confidence: str           # high | medium | low
    method: str

    @property
    def log_width(self) -> float:
        return math.log(self.hi / self.lo) if self.lo > 0 and self.hi > self.lo else (0.0 if self.hi == self.lo else 5.0)


@dataclass
class DerivedModel:
    motor_id: str
    params: Dict[str, Interval]
    conflicts: List[dict] = field(default_factory=list)
    trail: List[str] = field(default_factory=list)
    gear_ratio: float = 1.0
    out_counts_per_rev: int = 0
    V: float = 0.0
    notes: List[str] = field(default_factory=list)

    def least_certain(self, n: int = 3) -> List[str]:
        score = {k: v.log_width * INFLUENCE.get(k, 0.1) for k, v in self.params.items()}
        return [k for k, _ in sorted(score.items(), key=lambda kv: -kv[1])[:n]]

    def summary(self) -> str:
        lines = [f"Derived model for {self.motor_id} (PRELIMINARY, calculated from the datasheet):"]
        for k, v in self.params.items():
            lines.append(f"  {k:6s} {v.value:.5g}  [{v.lo:.4g} .. {v.hi:.4g}]  {v.provenance}/{v.confidence}  ({v.method})")
        for c in self.conflicts:
            lines.append(f"  CONFLICT: {c['what']} -- {c['detail']}")
        lines.append("  least certain parameters: " + ", ".join(self.least_certain()))
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"motor_id": self.motor_id, "gear_ratio": self.gear_ratio, "out_counts_per_rev": self.out_counts_per_rev, "V": self.V,
                "params": {k: vars(v) for k, v in self.params.items()}, "conflicts": self.conflicts, "trail": self.trail,
                "least_certain": self.least_certain(), "notes": self.notes}


def _iv(value, tier, method, conf="medium", rel=None, lo=None, hi=None):
    rel = TIER_REL[tier] if rel is None else rel
    return Interval(value, value * (1 - rel) if lo is None else lo, value * (1 + rel) if hi is None else hi, tier, conf, method)


def derive_model(profile: Profile, answers: Optional[Dict[str, str]] = None) -> DerivedModel:
    """Derive the model. ``answers`` resolves ambiguities, e.g. ``{"stall_current": "stall"}`` or ``{"stall_torque": "practical"}``."""
    answers = answers or {}
    P = profile
    log: List[str] = []
    conflicts: List[dict] = []
    notes: List[str] = []

    V = P.si("electrical.nominal_voltage")
    N = P.si("gearbox.ratio")
    w0 = P.si("mechanical.no_load_speed")
    if P.shaft("mechanical.no_load_speed") == "output":
        w0 *= N
        log.append(f"no-load speed was stated at the OUTPUT shaft: multiplied by N = {N:g} to get the motor-shaft speed {w0:.6g} rad/s")
    I0 = P.si("electrical.no_load_current")
    Is_f = P.field("electrical.stall_current")
    Is = P.si("electrical.stall_current")
    Is_meaning = answers.get("stall_current") or (Is_f or {}).get("meaning", "unknown")
    Rw = P.si("electrical.winding_resistance")
    eta_f = P.field("gearbox.efficiency")
    eta_given = P.si("gearbox.efficiency")
    tau_s_f = P.field("mechanical.stall_torque")
    tau_s = P.si("mechanical.stall_torque")
    tau_s_meaning = answers.get("stall_torque") or (tau_s_f or {}).get("meaning", "unknown")
    params: Dict[str, Interval] = {}

    # ---------------- R
    if Rw is not None:
        params["R"] = _iv(Rw, "datasheet", "stated winding resistance", "high")
        log.append(f"R = {Rw:.4g} ohm (stated)")
        if Is is not None and Is_meaning in ("stall", "unknown"):
            r_is = V / Is
            if abs(r_is / Rw - 1) > 0.25 and Is_meaning == "stall":
                conflicts.append({"what": "R versus V / stall current", "detail": f"stated R = {Rw:.3g} ohm but V / I_stall = {r_is:.3g} ohm",
                                  "resolutions": ["trust the stated R", "trust the stall current (R measured hot?)", "the 'stall' current is a limited rating"]})
    elif Is is not None:
        R = V / Is
        if Is_meaning == "stall":
            params["R"] = _iv(R, "calculated", "V / stall current", "medium", rel=0.10)
            log.append(f"R = V / I_stall = {V:g} / {Is:g} = {R:.4g} ohm")
        else:
            params["R"] = Interval(R, R / 4.0, R * 1.1, "assumed", "low", "V / current rating (not labelled stall: R is at most this)")
            log.append(f"R = V / {Is:g} A = {R:.4g} ohm ASSUMING the current is the locked-rotor current; it is not labelled 'stall' "
                       "(interval widened to R/4 .. 1.1 R)")
            conflicts.append({"what": "meaning of the current rating", "detail": f"{Is:g} A is labelled {Is_meaning!r}, not 'stall'",
                              "resolutions": ["treat it as the stall current (R = V / I)", "treat it as a maximum rating (R lower than V / I)", "measure R"]})
    elif I0 is not None:
        R = V / (8.0 * I0)
        params["R"] = Interval(R, V / (20.0 * I0), V / (3.0 * I0), "assumed", "low", "class prior: stall current about 8 x the no-load current")
        log.append(f"R from a class prior (no resistance or stall current given): {R:.4g} ohm")
    else:
        raise ValueError("cannot derive R: the profile has no winding resistance, stall current or no-load current")
    R = params["R"].value

    # ---------------- K = Kt = Ke
    sources: Dict[str, float] = {}
    if I0 is not None:
        sources["no-load balance V = R*I0 + K*w0"] = (V - R * I0) / w0
    else:
        sources["no-load speed V / w0 (I0 not given: 5 % of V assumed lost in R*I0)"] = 0.95 * V / w0
    Kt_s, Ke_s, Kv = P.si("constants.torque_constant"), P.si("constants.back_emf_constant"), P.si("constants.speed_constant")
    if Kt_s is not None:
        sources["stated torque constant Kt"] = Kt_s
    if Ke_s is not None:
        sources["stated back-EMF constant Ke"] = Ke_s
    if Kv is not None:
        sources["stated speed constant Kv (Ke = 1/Kv)"] = 1.0 / Kv
    if tau_s is not None and P.shaft("mechanical.stall_torque") == "motor" and Is is not None and Is_meaning == "stall":
        sources["stall torque / stall current"] = tau_s / Is
    vals = list(sources.values())
    explicit = [v for k, v in sources.items() if k.startswith("stated")]
    K = explicit[0] if explicit else sources[next(iter(sources))]
    lo, hi = min(vals) * 0.95, max(vals) * 1.05
    spread = max(vals) / min(vals)
    tier = "datasheet" if explicit else "calculated"
    params["K"] = Interval(K, min(K * 0.92, lo), max(K * 1.08, hi), tier, "medium" if spread < 1.15 else "low",
                           "; ".join(f"{k} = {v:.4g}" for k, v in sources.items()))
    for k, v in sources.items():
        log.append(f"K from {k}: {v:.5g} V.s/rad")
    if spread > 1.15:
        conflicts.append({"what": "K (= Kt = Ke) from different datasheet figures", "detail": ", ".join(f"{k}: {v:.4g}" for k, v in sources.items()),
                          "resolutions": ["trust the no-load balance (speed figures are usually precise)", "trust the stated constants", "measure Ke from a speed-versus-voltage line"]})
    if Kt_s is not None and (Ke_s is not None or Kv is not None):
        other = Ke_s if Ke_s is not None else 1.0 / Kv
        if abs(Kt_s / other - 1) > 0.1:
            conflicts.append({"what": "Kt differs from Ke", "detail": f"Kt = {Kt_s:.4g} but Ke = {other:.4g}; an ideal motor in SI has Ke = Kt",
                              "resolutions": ["treat the difference as unit/definition error", "model a loss term (brush/iron losses)"]})

    # ---------------- eta
    if eta_given is not None:
        params["eta"] = _iv(eta_given, "datasheet" if eta_f["provenance"] == "datasheet" else "assumed", "stated efficiency",
                            eta_f.get("confidence", "medium"), rel=0.10 if eta_f["provenance"] == "datasheet" else 0.25)
    if tau_s is not None and P.shaft("mechanical.stall_torque") == "output" and Is is not None:
        eta_fit = tau_s / (K * Is * N)
        log.append(f"efficiency fitted from the OUTPUT stall torque: {tau_s:.4g} / (K*I*N) = {eta_fit:.4g}")
        implausible = not (0.3 <= eta_fit <= 0.97)
        if eta_given is None:
            params["eta"] = Interval(min(max(eta_fit, 0.3), 0.95), max(0.3, eta_fit * 0.8), min(0.97, eta_fit * 1.2), "calculated", "low",
                                     "fitted from stall torque (assumes the stall figure is theoretical)")
        elif abs(eta_fit / eta_given - 1) > 0.25 or implausible:
            conflicts.append({"what": "output stall torque versus K, stall current and efficiency",
                              "detail": f"K*I_stall*N*eta = {K * Is * N * eta_given / KGCM:.4g} kg.cm but the datasheet says {tau_s / KGCM:.4g} kg.cm "
                                        f"(would need eta = {eta_fit:.3g})",
                              "resolutions": ["the stall torque is a practical (current-limited) rating", "the gearbox is much less efficient than assumed",
                                              "the current figure is not the locked-rotor current"]})
            if tau_s_meaning == "practical":
                notes.append("stall torque taken as a practical rating (user answer): efficiency left at its stated value")
    elif tau_s is not None and P.shaft("mechanical.stall_torque") == "motor" and Is is not None and Is_meaning == "stall":
        pass
    if "eta" not in params:
        params["eta"] = Interval(0.75, 0.5, 0.9, "assumed", "low", "class prior for a multi-stage spur/planetary gearbox")
        log.append("efficiency: class prior 0.75 (0.5 .. 0.9)")

    # ---------------- Bm and Coulomb friction
    Bm_s = P.si("mechanical.viscous_friction")
    tc_s = P.si("mechanical.coulomb_friction")
    if Bm_s is not None:
        params["Bm"] = _iv(Bm_s, "datasheet" if P.field("mechanical.viscous_friction")["provenance"] == "datasheet" else "assumed", "stated", rel=0.3)
    elif I0 is not None:
        Bm = K * I0 / w0
        params["Bm"] = Interval(Bm, 0.1 * Bm, Bm, "calculated", "low", "K*I0/w0: all of the no-load current as viscous friction (upper bound)")
        log.append(f"Bm = K*I0/w0 = {Bm:.4g} N.m.s/rad (upper bound)")
    else:
        params["Bm"] = Interval(1e-6, 1e-7, 1e-5, "assumed", "low", "class prior")
    tc_hi = 0.5 * K * I0 if I0 is not None else 1e-3
    params["tau_c"] = Interval(tc_s if tc_s is not None else 0.0, 0.0, max(tc_s or 0.0, tc_hi), "assumed", "low",
                               "stated" if tc_s is not None else "assumed zero; up to half of the no-load torque could be Coulomb")

    # ---------------- Jm
    Jm_s = P.si("mechanical.rotor_inertia")
    mass = P.si("mechanical.mass")
    if Jm_s is not None:
        tier = "datasheet" if P.field("mechanical.rotor_inertia")["provenance"] == "datasheet" else "assumed"
        params["Jm"] = _iv(Jm_s, tier, "stated rotor inertia", "medium" if tier == "datasheet" else "low", rel=0.1 if tier == "datasheet" else 2.0 / 3.0)
        if tier == "assumed":
            params["Jm"].lo, params["Jm"].hi = Jm_s / 3.0, Jm_s * 3.0
    elif mass is not None:
        D = (mass / 6000.0 / 1.178) ** (1.0 / 3.0)                      # motor body as a cylinder, L = 1.5 D, mean density 6000 kg/m3
        Jm = 0.5 * (0.3 * mass) * (0.6 * D / 2.0) ** 2                  # rotor: 30 % of the mass at 60 % of the body radius
        params["Jm"] = Interval(Jm, Jm / 3.0, Jm * 3.0, "assumed", "low", "rotor-cylinder approximation from the motor mass")
        log.append(f"Jm = 0.5*(0.3 m)*(0.6 r)^2 = {Jm:.3g} kg.m^2 from mass {mass:g} kg (documented approximation, x/ divided by 3)")
    else:
        params["Jm"] = Interval(1e-6, 1e-7, 1e-4, "assumed", "low", "class prior (no inertia or mass given)")

    # ---------------- L
    L_s = P.si("electrical.inductance")
    if L_s is not None:
        params["L"] = _iv(L_s, "datasheet", "stated", rel=0.2)
    else:
        params["L"] = Interval(0.0, 0.0, 5e-3, "assumed", "low", "neglected (0); plausible up to a few mH")

    # ---------------- encoder
    cpr = P.si("feedback.counts_per_rev")
    out_cpr = 0
    if cpr is not None:
        f = P.field
        quad = f("feedback.quadrature_included")
        mounted = f("feedback.mounted_on")
        out_cpr = cpr * (1.0 if quad else 4.0) * (N if mounted == "motor" else 1.0)
        log.append(f"output counts/rev = {cpr:g} x {'1 (quadrature included)' if quad else '4 (quadrature decode)'} x "
                   f"{'N (encoder on the motor shaft)' if mounted == 'motor' else '1 (encoder on the output shaft)'} = {out_cpr:g}")

    # ---------------- gearbox-side feasibility notes
    if tau_s_meaning == "unknown" and tau_s is not None:
        notes.append("stall torque is not labelled theoretical or practical: ask the user or measure")

    m = DerivedModel(P.id, params, conflicts, log + P.derivation_log, N, int(round(out_cpr)), V, notes)
    return m


def to_config(model: DerivedModel, base_cfg: dict) -> dict:
    """A config dict (same layout as config/motor_parameters.yaml) that runs this motor in every existing script."""
    c = copy.deepcopy(base_cfg)
    p = model.params
    c["supply"]["V_rated"] = model.V
    c["gearbox"]["ratio"] = model.gear_ratio
    c["gearbox"]["efficiency"] = p["eta"].value
    if model.out_counts_per_rev:
        c["encoder"]["output_cpr"] = model.out_counts_per_rev
    c["base_motor"]["derived"]["derived"] = {"description": f"derived from motor profile {model.motor_id}", "R_ohm": p["R"].value,
                                              "Kt_Nm_per_A": p["K"].value, "Ke_V_s_per_rad": p["K"].value}
    est = c["base_motor"]["estimated"]
    est["L_H"], est["Jm_kgm2"], est["Bm_Nms_per_rad"] = p["L"].value, p["Jm"].value, p["Bm"].value
    c["simulation"]["active_electrical_scenario"] = "derived"
    c["derived_uncertainty"] = {k: {"lo": v.lo, "hi": v.hi} for k, v in p.items()}
    c["motor_id"] = model.motor_id
    return c
