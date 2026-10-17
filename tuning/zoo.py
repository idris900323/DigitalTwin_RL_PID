"""Synthetic motor zoo (G3B.8): known true motors -> plausible published datasheets -> import -> derive -> recommend -> judge on the TRUE plant.

For each random but physically consistent brushed-DC gearmotor the zoo writes the datasheet a manufacturer might publish (3
significant digits, mixed units, realistic omissions, a few deliberate mistakes), runs the whole pipeline on that text only,
and then evaluates the recommended gains on the true plant. Reported (see ``summarise``):

  * fraction of motors whose Tier 1 gains are stable on the true plant;
  * fraction meeting the overshoot and settling spec on the true plant;
  * the "price of uncertainty": median ratio of the recommended gains' cost to the cost of gains optimised with perfect
    knowledge of the true plant;
  * calibration: how often the true-plant metrics fall inside the predicted 5th-95th percentile band (target about 90 %).

The zoo is generated with ASSUMPTIONS, stated here because the calibration result depends on them: rotor inertia is drawn
log-normally (sigma 0.6) around the rotor-cylinder approximation from the motor mass (so about 94 % of true inertias lie inside the
derived x/3 interval), efficiency is uniform in 0.45-0.9, the no-load current is 2-8 % of the stall current, and viscous friction
is 30-100 % of the value implied by the no-load current. Coulomb friction and inductance are zero in the true plants.
PRELIMINARY: simulated; says nothing about real motors.
"""

from __future__ import annotations

import copy
import math
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from models import ingest
from models.derive import derive_model, to_config
from models.motor_profile import ProfileError
from tuning import analytic, optimize
from tuning.linear import LinearPlant
from tuning.loads import Load
from tuning.recommend import recommend

KGCM, OZIN, GCM = 0.0980665, 0.00706155, 9.80665e-5


@dataclass
class TrueMotor:
    id: str
    V: float
    R: float
    K: float
    Bm: float
    Jm: float
    eta: float
    N: float
    I0: float
    Is: float
    w0: float                 # motor-shaft no-load speed [rad/s]
    mass: float
    cpr_motor: int


def zoo_ranges() -> dict:
    """The zoo's sampling ranges (YAML ``zoo:`` section; nothing is hard-coded here)."""
    from models.motors import load_base_config

    return load_base_config()["zoo"]


def make_motor(seed: int, z: Optional[dict] = None) -> TrueMotor:
    z = z or zoo_ranges()
    rng = np.random.default_rng(seed)
    V = float(rng.choice(z["voltages_V"]))
    Is = float(np.exp(rng.uniform(math.log(z["stall_current_A"][0]), math.log(z["stall_current_A"][1]))))
    R = V / Is
    rpm = float(np.exp(rng.uniform(math.log(z["no_load_rpm"][0]), math.log(z["no_load_rpm"][1]))))
    w0 = rpm * 2 * math.pi / 60
    I0 = Is * rng.uniform(*z["no_load_current_frac"])
    K = (V - R * I0) / w0
    Bm = rng.uniform(*z["viscous_frac"]) * K * I0 / w0
    mass = float(z["mass_coeff"] * (V * Is) ** z["mass_exp"] * math.exp(rng.normal(0, z["mass_logsigma"])))
    D = (mass / z["density_kg_m3"] / z["rotor_form"]) ** (1.0 / 3.0)
    Jm_est = 0.5 * (z["rotor_mass_frac"] * mass) * (z["rotor_dia_frac"] * D / 2.0) ** 2
    Jm = Jm_est * math.exp(rng.normal(0, z["Jm_logsigma"]))
    return TrueMotor(f"zoo_{seed:03d}", V, R, K, Bm, Jm, float(rng.uniform(*z["efficiency"])), float(rng.choice(z["gear_ratios"])),
                     I0, Is, w0, mass, int(rng.choice(z["motor_cpr"])))


def make_datasheet(m: TrueMotor, seed: int, mistake: Optional[str] = None) -> str:
    """The text a manufacturer might publish for ``m``: rounded, mixed units, some omissions. ``mistake`` injects one error."""
    rng = np.random.default_rng(10_000 + seed)
    r3 = lambda x: float(f"{x:.3g}")
    lines = [f"{m.id} geared DC motor", f"Voltage {m.V:g} V", f"Gear ratio {m.N:g}:1", "Base motor"]
    rpm = r3(m.w0 * 60 / (2 * math.pi))
    lines.append(f"No-load speed {rpm:g} rpm")
    i0 = r3(m.I0)
    lines.append(f"No-load current {int(i0 * 1000)} mA" if rng.random() < 0.5 else f"No-load current {i0:g} A")
    if rng.random() > 0.15:
        lines.append(f"Terminal resistance {r3(m.R):g} ohm")
    Is = m.Is * (1.3 if mistake == "max_current_as_stall" else 1.0)
    if rng.random() > 0.2 or mistake == "max_current_as_stall":
        lines.append(f"Stall current {r3(Is):g} A")
    if rng.random() > 0.3 or mistake == "torque_unit_typo":
        tau = m.K * m.Is
        unit = rng.choice(["mN.m", "oz.in", "g.cm"])
        val = {"mN.m": tau * 1e3, "oz.in": tau / OZIN, "g.cm": tau / GCM}[unit]
        if mistake == "torque_unit_typo":
            unit = "kg.cm" if unit == "g.cm" else unit
            val = tau / GCM if unit == "kg.cm" else val * 1000.0
        lines.append(f"Stall torque {r3(val):g} {unit}")
    if rng.random() > 0.4:
        lines.append(f"Efficiency {int(m.eta * 100)} %")
    if rng.random() > 0.15:
        lines.append(f"Weight {int(m.mass * 1000)} g")
    lines.append(f"Encoder {m.cpr_motor} ppr")
    if mistake == "contradiction":
        lines.append(f"Torque constant {r3(m.K * 2.5 * 1000):g} mN.m/A")
    return "\n".join(lines)


def cfg_from_truth(m: TrueMotor, base: dict) -> dict:
    c = copy.deepcopy(base)
    c["supply"]["V_rated"] = m.V
    c["gearbox"]["ratio"] = m.N
    c["gearbox"]["efficiency"] = m.eta
    c["encoder"]["output_cpr"] = int(m.cpr_motor * 4 * m.N)
    c["base_motor"]["derived"]["derived"] = {"R_ohm": m.R, "Kt_Nm_per_A": m.K, "Ke_V_s_per_rad": m.K}
    est = c["base_motor"]["estimated"]
    est["L_H"], est["Jm_kgm2"], est["Bm_Nms_per_rad"] = 0.0, m.Jm, m.Bm
    c["simulation"]["active_electrical_scenario"] = "derived"
    return c


def pipeline(text: str, motor_id: str, answers: Optional[dict] = None):
    """Datasheet text -> accepted candidates -> profile -> derived model. Everything is accepted (a scripted 'user')."""
    cands = ingest.extract_candidates(text, source=motor_id)
    rev = ingest.Review().accept(*[c.id for c in cands])
    rev.answers.update(answers or {})
    prof = ingest.build_profile(motor_id, cands, rev)
    return prof, derive_model(prof, answers)


def zoo_load() -> Load:
    return Load("zoo_bare_shaft", 0.0, 0.0, 0.0, targets_deg=[90.0], accuracy_deg=0.5, max_overshoot_pct=5.0, max_settling_s=1.0, max_noise_V_rms=0.6)


def run_one(seed: int, *, base: dict, fast: dict, mistake: Optional[str] = None) -> Dict[str, object]:
    """Full pipeline for one motor; returns a result row (including failure reasons instead of raising)."""
    m = make_motor(seed)
    text = make_datasheet(m, seed, mistake)
    row: Dict[str, object] = {"seed": seed, "motor": m.id, "mistake": mistake or "", "V": m.V, "N": m.N}
    try:
        prof, model = pipeline(text, m.id, {"stall_current": "stall", "stall_torque": "theoretical"})
    except (ProfileError, ValueError) as exc:
        row.update(status="import failed", reason=str(exc)[:120])
        return row
    cfg_est = to_config(model, base)
    load = zoo_load()
    rec = recommend(m.id, load.id, model=model, cfg=cfg_est, load=load, profile=prof, **fast)
    true_cfg = cfg_from_truth(m, base)
    ctxs = optimize.contexts(load)
    plants = optimize.plant_arrays(true_cfg, None, 1)
    ev = optimize.evaluate(true_cfg, load, np.array([rec.gains]), ctxs, plants)
    mm = {k: float(v[0, 0]) for k, v in ev["metrics"].items()}
    lin_true = LinearPlant.from_cfg(true_cfg, target_deg=90.0)
    stable = bool(lin_true.margins(*rec.gains)["stable"])
    meets = mm["overshoot"] <= load.max_overshoot_pct and mm["settle"] <= load.max_settling_s and mm["sse"] <= load.accuracy_deg
    # oracle: optimised with perfect knowledge of the true plant
    d = analytic.design(lin_true, settle_s=0.5 * load.max_settling_s)
    kd_floor = 0.1 * max(d["gains"][0], 1e-6) / d["wn"]
    orc = optimize.optimize(true_cfg, load, d["gains"], ctxs, plants, [lin_true], seed=1, popsize=fast["popsize"], maxiter=fast["maxiter"], restarts=fast["restarts"],
                            noise_limit_v=load.max_noise_V_rms, kd_floor=kd_floor)
    ev_o = optimize.evaluate(true_cfg, load, np.array([orc["gains"]]), ctxs, plants)
    in_band = {}
    for key, tkey in (("overshoot [%]", "overshoot"), ("settling time [s]", "settle"), ("peak current [A]", "peak_i")):
        p = rec.predictions[key]
        val = min(mm[tkey], 4.0 * load.max_settling_s) if tkey == "settle" else mm[tkey]
        tol = 0.02 * max(abs(p["p50"]), 1e-3) + (0.5 if tkey == "overshoot" else 0.0)
        in_band[key] = bool(p["p5"] - tol <= val <= p["p95"] + tol)
    row.update(status="ok", stable=stable, meets_spec=bool(meets), cost_rec=float(ev["cost"][0]), cost_oracle=float(ev_o["cost"][0]),
               price=float(ev["cost"][0] / max(ev_o["cost"][0], 1e-9)), in_band=in_band, gains=[float(g) for g in rec.gains],
               conflicts=[c["what"] for c in model.conflicts], overshoot=mm["overshoot"], settle=mm["settle"],
               true_Jm_in_interval=bool(model.params["Jm"].lo <= m.Jm <= model.params["Jm"].hi),
               true_R_in_interval=bool(model.params["R"].lo <= m.R <= model.params["R"].hi),
               true_K_in_interval=bool(model.params["K"].lo <= m.K <= model.params["K"].hi))
    return row


def summarise(rows: List[dict]) -> Dict[str, object]:
    ok = [r for r in rows if r["status"] == "ok"]
    n = len(ok)
    cover = {}
    for key in ("overshoot [%]", "settling time [s]", "peak current [A]"):
        cover[key] = sum(r["in_band"][key] for r in ok) / max(n, 1)
    return {"motors": len(rows), "imported": n, "import_failed": len(rows) - n,
            "stable_fraction": sum(r["stable"] for r in ok) / max(n, 1),
            "meets_spec_fraction": sum(r["meets_spec"] for r in ok) / max(n, 1),
            "price_of_uncertainty_median": statistics.median(r["price"] for r in ok) if ok else float("nan"),
            "price_of_uncertainty_p90": float(np.percentile([r["price"] for r in ok], 90)) if ok else float("nan"),
            "band_coverage": cover, "band_coverage_mean": float(np.mean(list(cover.values()))) if ok else float("nan"),
            "interval_coverage": {k: sum(r[f"true_{k}_in_interval"] for r in ok) / max(n, 1) for k in ("R", "K", "Jm")}}
