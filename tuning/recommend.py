"""PID recommendation for a motor profile and a load, with tier label, uncertainty, margins and a sanity check (G3B.5).

Methods compared on the SAME held-out set of plausible plants (drawn inside the derived intervals) and the load's
payload/target contexts: analytic pole placement, IMC/lambda, Ziegler-Nichols (reference), nominal-model optimisation and
robust optimisation. The winner is the lowest robust cost on the held-out set among methods that satisfy the stability margins;
the runner-up and a cost breakdown explain why.

The recommendation is ALWAYS labelled with its tier (``tuning.tiers``) and never printed as bare gains. Everything is
PRELIMINARY: computed on a datasheet-derived (Tier 1) or identified model, not validated on hardware.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from models.derive import DerivedModel, derive_model
from models.motor_profile import load_profile
from models.motors import get_cfg
from tuning import analytic, optimize
from tuning.linear import LinearPlant, noise_voltage_rms
from tuning.loads import Load, check_drivable, load_load
from tuning.tiers import Tier

Gains = Tuple[float, float, float]


@dataclass
class Method:
    name: str
    gains: Gains
    cost: float = float("nan")          # robust cost on the held-out set
    mean_cost: float = float("nan")
    p_ok: float = float("nan")          # fraction of held-out simulations meeting every constraint
    pm_deg: float = float("nan")
    gm_db: float = float("nan")
    delay_margin_s: float = float("nan")
    stable: bool = True
    info: str = ""

    def __post_init__(self):
        self.gains = tuple(float(x) for x in self.gains)       # plain floats (numpy scalars would break code export)


@dataclass
class Recommendation:
    tier: Tier
    motor_id: str
    load_id: str
    gains: Gains
    winner: str
    runner_up: Optional[str]
    methods: List[Method]
    model: DerivedModel
    margins: Dict[str, float]
    predictions: Dict[str, Dict[str, float]]
    constraint_probability: Dict[str, float]
    warnings: List[str]
    cost_breakdown: Dict[str, float]
    next_measurement: str
    drivable: List[dict]
    settings: Dict[str, object]
    profile_hash: str = ""
    cfg: dict = field(default_factory=dict, repr=False)
    load: Optional[Load] = field(default=None, repr=False)
    references: List[Method] = field(default_factory=list)      # reference gains evaluated on the same set (not eligible to win)

    def format(self) -> str:
        """Human-readable summary. Gains are never shown without the tier label and the uncertainty."""
        kp, ki, kd = self.gains
        def width(k):
            p = self.model.params[k]
            return f"{k} in [{p.lo:.3g}, {p.hi:.3g}]"
        wid = ", ".join(width(k) for k in self.model.least_certain())
        lines = [f"{self.tier.label}", f"motor {self.motor_id}, load {self.load_id}",
                 f"recommended gains: Kp {kp:.4g}, Ki {ki:.4g}, Kd {kd:.4g}  (method: {self.winner}; PRELIMINARY)",
                 f"plant uncertainty behind this: least certain parameters {wid}",
                 "predicted performance (5th / median / 95th percentile over plausible plants):"]
        for name, p in self.predictions.items():
            lines.append(f"  {name}: {p['p5']:.3g} / {p['p50']:.3g} / {p['p95']:.3g}")
        lines.append("probability of meeting each constraint: " + ", ".join(f"{k} {v * 100:.0f} %" for k, v in self.constraint_probability.items()))
        lines.append(f"stability margins (linear model, worst of nominal and corner plants): gain {self.margins['gain_margin_db']:.1f} dB, "
                     f"phase {self.margins['phase_margin_deg']:.1f} deg, delay {self.margins['delay_margin_s'] * 1e3:.1f} ms")
        for w in self.warnings:
            lines.append("WARNING: " + w)
        lines.append("most valuable next measurement: " + self.next_measurement)
        return "\n".join(lines)


def profile_hash(motor_id: str, profile=None) -> str:
    if profile is not None and profile.path is None:                  # an in-memory profile (zoo, identified candidate): hash its content
        import yaml
        return hashlib.sha256(yaml.safe_dump(profile.data, sort_keys=True).encode()).hexdigest()[:16]
    from models.motor_profile import library_dir
    return hashlib.sha256((library_dir() / motor_id / "profile.yaml").read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


NEXT_MEASUREMENT = {
    "Jm": "rotor inertia: free-run speed decay with and without a known added inertia (docs/validation_plan.md T6)",
    "R": "winding resistance and torque per ampere: low-voltage locked-rotor test with a torque arm (T2)",
    "K": "back-EMF constant: no-load speed versus voltage at several voltages (T3)",
    "eta": "gearbox efficiency: loaded versus no-load current at a known output torque (T8)",
    "Bm": "viscous friction: steady speed versus current at low speed, both directions (T7)",
    "L": "armature inductance: LCR meter or locked-rotor current rise (T5)",
    "tau_c": "Coulomb friction: friction map at low speed (T7)",
}


def intervals_as_factors(model: DerivedModel) -> Dict[str, Tuple[float, float]]:
    """Multiplicative (lo, hi) factors of the plant parameters relative to the derived nominal."""
    out = {}
    for k in ("R", "K", "Jm", "Bm", "eta"):
        p = model.params[k]
        if p.value > 0:
            out[k] = (p.lo / p.value, p.hi / p.value)
    return out


def corner_plants(cfg: dict, load: Load, factors, payload_kg, target_deg) -> List[LinearPlant]:
    """Nominal plus the extreme corners of R, K, Jm (the parameters that matter most) for margin checks."""
    nom = optimize.plant_arrays(cfg, None, 1)
    base = {k: float(v[0]) for k, v in nom.items()}
    plants = [LinearPlant.from_cfg(cfg, payload_kg=payload_kg, arm_length_m=load.arm_length_m, arm_mass_kg=load.arm_mass_kg, gravity=load.gravity,
                                   target_deg=target_deg, viscous=load.viscous)]
    keys = [k for k in ("R", "K", "Jm") if k in factors]
    for bits in range(2 ** len(keys)):
        o = dict(base)
        for j, k in enumerate(keys):
            f = factors[k][(bits >> j) & 1]
            if k == "K":
                o["Kt"], o["Ke"] = base["Kt"] * f, base["Ke"] * f
            else:
                o[k] = base[k] * f
        plants.append(LinearPlant.from_cfg(cfg, payload_kg=payload_kg, arm_length_m=load.arm_length_m, arm_mass_kg=load.arm_mass_kg, gravity=load.gravity,
                                           target_deg=target_deg, viscous=load.viscous, overrides=o))
    return plants


def sanity_check(cfg: dict, load: Load, gains: Gains, lin: LinearPlant, optimiser_info: Optional[dict], margins: dict,
                 settle_s: float, bounds_hit: Optional[List[bool]] = None) -> List[str]:
    """Flag nonsense: derivative noise amplification, integral windup/oscillation, gains at the search bounds, weak margins."""
    kp, ki, kd = gains
    warn = []
    nv = noise_voltage_rms(kp, kd, lin)
    if nv > load.max_noise_V_rms:
        warn.append(f"derivative gain amplifies encoder quantisation noise to {nv:.2f} V RMS (limit {load.max_noise_V_rms:g} V): "
                    "increase the derivative filter time constant or lower Kd")
    elif nv > 0.5 * load.max_noise_V_rms:
        warn.append(f"encoder quantisation noise through the controller is {nv:.2f} V RMS, above half the allowed {load.max_noise_V_rms:g} V")
    if ki > 0 and kp / ki < 0.5 * load.max_settling_s:
        warn.append(f"integral time Kp/Ki = {kp / ki:.2f} s is shorter than half the settling target: the integrator will wind up and oscillate under saturation")
    if bounds_hit and any(bounds_hit):
        warn.append("an optimised gain sits at the edge of its search range: the bounds were too tight, widen them and re-run")
    if margins["phase_margin_deg"] < 45 or margins["gain_margin_db"] < 6:
        warn.append(f"margins are below the usual 45 deg / 6 dB (phase {margins['phase_margin_deg']:.0f} deg, gain {margins['gain_margin_db']:.1f} dB)")
    if not math.isfinite(settle_s):
        warn.append("the nominal response does not settle within the simulated window")
    return warn


REFERENCE_GAINS = {"rmcs_3070": {"Tuned preset (reference)": (15.0, 0.0, 0.3)}}


def recommend(motor_id: str, load_id: str, *, tier: Tier = Tier.ESTIMATE, seed: int = 0, n_train_plants: int = 12, n_test_plants: int = 48,
              popsize: int = 10, maxiter: int = 20, restarts: int = 2, min_pm: float = 45.0, min_gm: float = 6.0, answers: Optional[dict] = None,
              model: Optional[DerivedModel] = None, cfg: Optional[dict] = None, load: Optional[Load] = None, profile=None) -> Recommendation:
    """Run every tuning method, compare them on a held-out plant set, and return the best with its evidence."""
    prof = profile or load_profile(motor_id)
    model = model or derive_model(prof, answers)
    cfg = cfg or get_cfg(motor_id, answers)
    load = load or load_load(load_id)
    drivable = check_drivable(cfg, load)
    factors = intervals_as_factors(model)
    payload = load.payload_max_kg                                         # worst case for stability; contexts cover the range
    target = max(load.targets_deg)
    nominal_lin = LinearPlant.from_cfg(cfg, payload_kg=payload, arm_length_m=load.arm_length_m, arm_mass_kg=load.arm_mass_kg, gravity=load.gravity,
                                       target_deg=target, viscous=load.viscous)
    lin_all = corner_plants(cfg, load, factors, payload, target)
    ctxs = optimize.contexts(load)
    train = optimize.plant_arrays(cfg, optimize.sample_factors(factors, n_train_plants, seed), n_train_plants)
    test = optimize.plant_arrays(cfg, optimize.sample_factors(factors, n_test_plants, seed + 777), n_test_plants)
    nominal = optimize.plant_arrays(cfg, None, 1)

    # ---- candidates
    methods: List[Method] = []
    d = analytic.design(nominal_lin, settle_s=0.5 * load.max_settling_s, min_pm_deg=min_pm, min_gm_db=min_gm, ki_ratio=0.1 if load.gravity else 0.0)
    methods.append(Method("analytic (pole placement)", d["gains"], info=d["note"]))
    imc = analytic.imc_lambda(nominal_lin, 0.25 * load.max_settling_s, 0.1 if load.gravity else 0.0)
    methods.append(Method("analytic (IMC/lambda)", imc))
    try:
        methods.append(Method("Ziegler-Nichols (reference)", analytic.ziegler_nichols(nominal_lin)))
    except Exception:                                       # noqa: BLE001 - no ultimate gain found
        pass
    ref = d["gains"]
    kd_floor = 0.1 * max(ref[0], 1e-6) / d["wn"]          # when the plant is already damped enough the analytic Kd is 0: give the search a scale
    opt_nom = optimize.optimize(cfg, load, ref, ctxs, nominal, [nominal_lin], seed=seed, popsize=popsize, maxiter=maxiter, restarts=restarts,
                                min_pm=min_pm, min_gm=min_gm, noise_limit_v=load.max_noise_V_rms, kd_floor=kd_floor)
    methods.append(Method("optimised (nominal model)", opt_nom["gains"]))
    opt_rob = optimize.optimize(cfg, load, ref, ctxs, train, lin_all, seed=seed + 1, popsize=popsize, maxiter=maxiter, restarts=restarts,
                                min_pm=min_pm, min_gm=min_gm, noise_limit_v=load.max_noise_V_rms, kd_floor=kd_floor)
    methods.append(Method("optimised (robust)", opt_rob["gains"]))

    # ---- compare all on the same held-out plants
    for m in methods:
        ev = optimize.evaluate(cfg, load, np.array([m.gains]), ctxs, test)
        mg = min((lp.margins(*m.gains) for lp in lin_all), key=lambda x: x["phase_margin_deg"])
        m.cost, m.mean_cost, m.p_ok = float(ev["cost"][0]), float(ev["mean_cost"][0]), float(ev["p_ok"][0])
        m.pm_deg, m.gm_db, m.delay_margin_s, m.stable = mg["phase_margin_deg"], mg["gain_margin_db"], mg["delay_margin_s"], bool(mg["stable"])
    references = []
    for name, g in REFERENCE_GAINS.get(motor_id, {}).items():
        r = Method(name, g)
        ev = optimize.evaluate(cfg, load, np.array([g]), ctxs, test)
        mg = min((lp.margins(*g) for lp in lin_all), key=lambda x: x["phase_margin_deg"])
        r.cost, r.mean_cost, r.p_ok = float(ev["cost"][0]), float(ev["mean_cost"][0]), float(ev["p_ok"][0])
        r.pm_deg, r.gm_db, r.delay_margin_s, r.stable = mg["phase_margin_deg"], mg["gain_margin_db"], mg["delay_margin_s"], bool(mg["stable"])
        references.append(r)
    eligible = [m for m in methods if m.name != "Ziegler-Nichols (reference)"]
    strict = [m for m in eligible if m.stable and m.pm_deg >= min_pm and m.gm_db >= min_gm]
    relaxed = [m for m in eligible if m.stable and m.pm_deg >= 0.5 * min_pm and m.gm_db >= 0.5 * min_gm]
    pool = strict or relaxed or [m for m in methods if m.stable] or methods
    margin_note = None if strict else "no method met the requested stability margins; the least bad stable one is returned"
    pool = sorted(pool, key=lambda m: (-(m.p_ok > 0.9), m.cost))
    win, runner = pool[0], (pool[1] if len(pool) > 1 else None)

    # ---- evidence for the winner
    ev = optimize.evaluate(cfg, load, np.array([win.gains]), ctxs, test)
    mm = ev["metrics"]
    q = lambda a: dict(p5=float(np.percentile(a, 5)), p50=float(np.percentile(a, 50)), p95=float(np.percentile(a, 95)))
    finite_settle = np.where(np.isfinite(mm["settle"]), mm["settle"], 4.0 * load.max_settling_s)
    predictions = {"overshoot [%]": q(mm["overshoot"]), "settling time [s]": q(finite_settle), "steady-state error [deg]": q(mm["sse"]),
                   "peak current [A]": q(mm["peak_i"]), "control effort [mean V^2 / Vmax^2]": q(mm["effort"]), "IAE / |ref| [s]": q(mm["iae"])}
    constraint = {"overshoot": float(np.mean(mm["overshoot"] <= load.max_overshoot_pct)),
                  "settling": float(np.mean(mm["settle"] <= load.max_settling_s)),
                  "accuracy": float(np.mean(mm["sse"] <= load.accuracy_deg))}
    if load.max_current_A is not None:
        constraint["current"] = float(np.mean(mm["peak_i"] <= load.max_current_A))
    margins = min((lp.margins(*win.gains) for lp in lin_all), key=lambda x: x["phase_margin_deg"])
    nominal_ev = optimize.evaluate(cfg, load, np.array([win.gains]), ctxs, nominal)
    breakdown = {"robust cost": win.cost, "mean cost": win.mean_cost, "worst held-out cost": float(ev["worst_cost"][0]),
                 "fraction of held-out cases meeting all constraints": win.p_ok, "nominal-plant cost": float(nominal_ev["cost"][0])}
    if runner:
        breakdown[f"runner-up ({runner.name}) robust cost"] = runner.cost
    nominal_settle = float(np.median(finite_settle))
    warnings = sanity_check(cfg, load, win.gains, nominal_lin, opt_rob, margins, nominal_settle,
                            opt_rob["at_bound"] if win.name == "optimised (robust)" else (opt_nom["at_bound"] if win.name == "optimised (nominal model)" else None))
    if margin_note:
        warnings.append(margin_note)
    for c in model.conflicts:
        warnings.append("datasheet conflict unresolved: " + c["what"])
    rated = prof.si("electrical.stall_current")
    if rated is not None and predictions["peak current [A]"]["p95"] > 1.2 * rated:
        warnings.append(f"predicted peak current reaches {predictions['peak current [A]']['p95']:.1f} A in some plausible plants, above the {rated:g} A rating: "
                        "set a driver current limit (config driver.current_limit_A) and re-run")
    next_key = model.least_certain()[0]
    settings = dict(seed=seed, n_train_plants=n_train_plants, n_test_plants=n_test_plants, popsize=popsize, maxiter=maxiter, restarts=restarts,
                    min_pm_deg=min_pm, min_gm_db=min_gm, cost_weights=optimize.COST_WEIGHTS, risk=f"mean + {optimize.RISK_WEIGHT} x mean of worst {optimize.RISK_FRACTION:.0%}")
    return Recommendation(tier, motor_id, load.id, win.gains, win.name, runner.name if runner else None, methods, model, margins, predictions, constraint,
                          warnings, breakdown, NEXT_MEASUREMENT.get(next_key, next_key), drivable, settings, profile_hash(motor_id, profile), cfg, load, references)


def verify_in_twin(rec: Recommendation, payload_kg: Optional[float] = None, target_deg: Optional[float] = None) -> Dict[str, float]:
    """Run the recommended gains in the full Python twin (command delay, joint friction, quantisation) and return the step metrics."""
    from models.factory import build_twin_from_config
    from models.joint import Joint, JointParams
    from simulation.metrics import all_metrics

    load = rec.load
    m = load.payload_max_kg if payload_kg is None else payload_kg
    tgt = max(load.targets_deg) if target_deg is None else target_deg
    joint = Joint(JointParams(payload_mass_kg=m, arm_length_m=load.arm_length_m, arm_mass_kg=load.arm_mass_kg, gravity_on=load.gravity,
                              B_joint=load.viscous, tau_coulomb=load.coulomb))
    tw = build_twin_from_config(rec.cfg, *rec.gains, joint=joint)
    log = tw.run(math.radians(tgt), int(round(rec.cfg["simulation"]["run_duration_s"] / tw.dt)))
    return all_metrics(log["t"], np.degrees(log["theta_out"]), tgt, log["V_applied"], log["i_motor"], error_deg=np.degrees(log["error"]))
