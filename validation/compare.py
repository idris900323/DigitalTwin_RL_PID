"""Compare a measured run with the twin and decide, quantity by quantity, whether the acceptance thresholds are met.

Thresholds live in ``config/motor_parameters.yaml`` (`validation_thresholds`, PROPOSED values with their reasoning in
``docs/validation_plan.md``). Nothing is called "validated" by this module: it reports PASS/FAIL per metric for the
tested condition, and the twin only earns the word for the conditions and quantities that pass.

Metrics (all on the output angle unless stated):
  RMSE, NRMSE (RMSE / peak-to-peak of the measured signal), FIT % = 100*(1 - ||y - yhat|| / ||y - mean(y)||), R^2,
  Theil's U (RMSE / (RMS(y) + RMS(yhat))), maximum error; step-response scalars (overshoot, settling, rise time,
  steady-state error) and peak armature current; residual diagnostics (Ljung-Box whiteness, residual-input cross-correlation).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from scipy import stats

from simulation.metrics import overshoot_pct, rise_time, settling_time, steady_state_error
from validation.load_bench_csv import Run


# ------------------------------------------------------------------------------------------------ signal metrics
def signal_metrics(y: np.ndarray, yhat: np.ndarray) -> Dict[str, float]:
    """Agreement between a measured signal ``y`` and a simulated one ``yhat`` (same length)."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    e = y - yhat
    rmse = float(np.sqrt(np.mean(e ** 2)))
    span = float(np.ptp(y))
    denom = float(np.linalg.norm(y - np.mean(y)))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return {
        "rmse": rmse,
        "nrmse": rmse / span if span > 0 else float("nan"),
        "fit_pct": 100.0 * (1.0 - float(np.linalg.norm(e)) / denom) if denom > 0 else float("nan"),
        "r2": 1.0 - float(np.sum(e ** 2)) / ss_tot if ss_tot > 0 else float("nan"),
        "theil_u": rmse / (float(np.sqrt(np.mean(y ** 2))) + float(np.sqrt(np.mean(yhat ** 2)))) if (np.any(y) or np.any(yhat)) else float("nan"),
        "max_error": float(np.max(np.abs(e))),
    }


def ljung_box(resid: np.ndarray, lags: int = 20) -> Dict[str, float]:
    """Ljung-Box whiteness test of the residuals: Q statistic and p-value (small p = residuals are not white)."""
    r = np.asarray(resid, float) - np.mean(resid)
    n = len(r)
    denom = float(np.sum(r ** 2))
    if denom == 0 or n <= lags + 1:
        return {"Q": float("nan"), "p": float("nan"), "lags": lags}
    ac = np.array([np.sum(r[k:] * r[:-k]) / denom for k in range(1, lags + 1)])
    q = n * (n + 2) * float(np.sum(ac ** 2 / (n - np.arange(1, lags + 1))))
    return {"Q": q, "p": float(1.0 - stats.chi2.cdf(q, lags)), "lags": lags}


def input_cross_correlation(resid: np.ndarray, u: np.ndarray, max_lag: int = 20) -> float:
    """Largest |normalised cross-correlation| between the residual and the input over +-max_lag samples."""
    r = np.asarray(resid, float) - np.mean(resid)
    x = np.asarray(u, float) - np.mean(u)
    if np.std(r) == 0 or np.std(x) == 0:
        return 0.0
    best = 0.0
    n = len(r)
    for k in range(-max_lag, max_lag + 1):
        a, b = (r[k:], x[: n - k]) if k >= 0 else (r[: n + k], x[-k:])
        best = max(best, abs(float(np.corrcoef(a, b)[0, 1])))
    return best


def step_scalars(t, theta_deg, target_deg) -> Dict[str, float]:
    return {"overshoot_pct": overshoot_pct(theta_deg, target_deg), "settle_s": settling_time(t, theta_deg, target_deg),
            "rise_s": rise_time(t, theta_deg, target_deg), "sse_deg": steady_state_error(theta_deg, target_deg)}


# ------------------------------------------------------------------------------------------------ comparison
@dataclass
class Check:
    name: str
    value: float
    limit: str
    passed: Optional[bool]          # None = informational only
    note: str = ""

    def __post_init__(self):
        if self.passed is not None:
            self.passed = bool(self.passed)           # numpy bools would break `is False` style checks

@dataclass
class Comparison:
    run_id: str
    checks: List[Check] = field(default_factory=list)
    signals: Dict[str, Dict[str, float]] = field(default_factory=dict)
    scalars: Dict[str, Dict[str, float]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.passed is not None)

    def table(self) -> str:
        """Markdown pass/fail table."""
        rows = ["| check | value | threshold | result |", "|---|---|---|---|"]
        for c in self.checks:
            res = "info" if c.passed is None else ("PASS" if c.passed else "FAIL")
            v = "n/a" if (isinstance(c.value, float) and math.isnan(c.value)) else f"{c.value:.4g}"
            rows.append(f"| {c.name} | {v} | {c.limit} | {res} |")
        rows.append("")
        rows.append(f"**Overall for run `{self.run_id}`: {'all thresholds met' if self.passed else 'thresholds NOT met'}** "
                    "(for this tested condition only).")
        return "\n".join(rows)


def _num(x) -> float:
    return float("nan") if x is None else float(x)


def compare_run(run: Run, sim: Dict[str, np.ndarray], thresholds: dict, *, target_deg: Optional[float] = None) -> Comparison:
    """Compare ``run`` with simulated signals ``sim`` (keys ``theta_deg`` and optionally ``i``), both on ``run.t``.

    For closed-loop step runs pass the target (or set ``run.target_deg``): overshoot, settling, rise time and steady-state
    error are compared as well. ``thresholds`` is the YAML ``validation_thresholds`` mapping."""
    th = thresholds
    cmp = Comparison(run.run_id)
    sm = signal_metrics(run.theta_deg, sim["theta_deg"])
    cmp.signals["theta_deg"] = sm
    cmp.checks += [
        Check("angle NRMSE", sm["nrmse"], f"<= {th['step_nrmse_max']}", sm["nrmse"] <= th["step_nrmse_max"]),
        Check("angle FIT %", sm["fit_pct"], f">= {th['step_fit_min_pct']}", sm["fit_pct"] >= th["step_fit_min_pct"]),
        Check("angle max error [deg]", sm["max_error"], "informational", None),
        Check("angle R^2 / Theil U", sm["r2"], f"Theil U = {sm['theil_u']:.3g}", None),
    ]
    if run.i is not None and "i" in sim:
        ci = signal_metrics(run.i, sim["i"])
        cmp.signals["i_A"] = ci
        pk_m, pk_s = float(np.max(np.abs(run.i))), float(np.max(np.abs(sim["i"])))
        rel = abs(pk_s - pk_m) / pk_m if pk_m > 0 else float("nan")
        cmp.checks += [
            Check("current NRMSE", ci["nrmse"], f"<= {th['current_nrmse_max']}", ci["nrmse"] <= th["current_nrmse_max"]),
            Check("peak current rel. error", rel, f"<= {th['peak_current_rel_max']}", rel <= th["peak_current_rel_max"],
                  f"measured {pk_m:.3g} A, simulated {pk_s:.3g} A"),
        ]
    tgt = target_deg if target_deg is not None else run.target_deg
    if tgt:
        m, s = step_scalars(run.t, run.theta_deg, tgt), step_scalars(run.t, sim["theta_deg"], tgt)
        cmp.scalars = {"measured": m, "simulated": s}
        d_os = abs(s["overshoot_pct"] - m["overshoot_pct"])
        cmp.checks.append(Check("overshoot difference [pp]", d_os, f"<= {th['overshoot_abs_pp_max']}", d_os <= th["overshoot_abs_pp_max"]))
        if math.isnan(m["settle_s"]) or math.isnan(s["settle_s"]):
            cmp.checks.append(Check("settling time", float("nan"), "both settle", math.isnan(m["settle_s"]) and math.isnan(s["settle_s"]),
                                    "one run never settles within the window" if math.isnan(m["settle_s"]) != math.isnan(s["settle_s"]) else "neither settles"))
        else:
            d = abs(s["settle_s"] - m["settle_s"])
            lim = max(th["settling_rel_max"] * m["settle_s"], th["settling_abs_min_s"])
            cmp.checks.append(Check("settling time difference [s]", d, f"<= {lim:.3g} (max of {th['settling_rel_max']:.0%} and {th['settling_abs_min_s']} s)", d <= lim))
        if not (math.isnan(m["rise_s"]) or math.isnan(s["rise_s"])):
            d = abs(s["rise_s"] - m["rise_s"]) / m["rise_s"]
            cmp.checks.append(Check("rise time rel. difference", d, f"<= {th['rise_rel_max']}", d <= th["rise_rel_max"]))
        d_sse = abs(s["sse_deg"] - m["sse_deg"])
        cmp.checks.append(Check("steady-state error difference [deg]", d_sse, f"<= {th['sse_abs_deg_max']}", d_sse <= th["sse_abs_deg_max"]))
    resid = run.theta_deg - sim["theta_deg"]
    lb = ljung_box(resid)
    cmp.checks.append(Check("residual whiteness (Ljung-Box p)", lb["p"], f"report only (>= {th['ljung_box_p_min']} is white)", None,
                            "residuals are structured: the model is missing dynamics" if lb["p"] < th["ljung_box_p_min"] else ""))
    cmp.checks.append(Check("residual vs input max |xcorr|", input_cross_correlation(resid, run.V), "report only", None))
    return cmp


def simulate_like(run: Run, cfg: dict, joint=None, true_values: Optional[dict] = None) -> Dict[str, np.ndarray]:
    """Simulate the twin for a closed-loop ``run`` (uses its gains and target); returns arrays on the same time base."""
    import math as _m

    from models.factory import build_twin_from_config
    from simulation.sensitivity import perturbed_cfg

    if run.gains is None or run.target_deg is None:
        raise ValueError("run has no gains/target: simulate open-loop runs with validation.synthetic.simulate_open_loop")
    c = perturbed_cfg(cfg, true_values or {})
    tw = build_twin_from_config(c, *run.gains, joint=joint, dt=run.dt)
    log = tw.run(_m.radians(run.target_deg), len(run.t))
    return {"theta_deg": np.degrees(np.asarray(log["theta_out_meas"])), "i": np.asarray(log["i_motor"])}
