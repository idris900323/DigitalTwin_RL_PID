"""Identify motor parameters (R, Ke, Kt, Jm, Bm [, tau_c]) from bench logs, and say which ones the data can determine.

Method: output-error least squares (``scipy.optimize.least_squares``) on the log-parameters. The measured terminal
voltage ``V`` drives a fast open-loop simulation of motor + gearbox; the residuals are the output angle (and the
armature current, if logged). Because the measured voltage is the model input, closed-loop step responses and
open-loop excitation are handled the same way.

Identifiability is judged from the Jacobian at the optimum, not assumed. Its singular value decomposition separates the
well-determined parameter combinations from the null space. A parameter whose axis leaks into the null space is
reported as NOT identifiable (no value, no confidence interval), together with the combinations that ARE determined.
The classic cases for L = 0:

  * angle data only (no current): only the two lumped dynamics parameters  Kt/(R*Jm)  and  (Kt*Ke/R + Bm)/Jm  are
    determined, so R, Kt, Ke, Jm and Bm are all unidentifiable (in particular Ke and Kt cannot be separated);
  * angle + current: R, Ke, Jm/Kt and Bm/Kt are determined; Kt, Jm and Bm are not separately (a common scale
    factor cancels), so Kt needs one more fact: a run with a KNOWN added inertia on the output shaft (``Run.extra``
    key ``J_added_out`` via the ``added_inertia`` argument) or a torque measurement.

The result never overwrites the active configuration: ``write_candidate_yaml`` writes a separate file.
"""

from __future__ import annotations

import hashlib
import math
import pathlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import yaml
from scipy.optimize import least_squares

from validation.load_bench_csv import Run
from validation.synthetic import simulate_open_loop

PARAMS = ("R", "Ke", "Kt", "Jm", "Bm")
DEFAULT_BOUNDS = {"R": (0.2, 20.0), "Ke": (1e-4, 5e-2), "Kt": (1e-4, 5e-2), "Jm": (1e-8, 1e-4), "Bm": (1e-8, 1e-4)}
NULL_LEAK_TOL = 1e-3          # a parameter axis with more than this much weight in the null space is "unidentifiable" (identifiable ones are ~1e-8)
RANK_TOL = 1e-9               # singular values below RANK_TOL * largest are numerically zero
MIN_SINGULAR = 1.0            # with noise-weighted residuals 1/s is the 1-sigma log-uncertainty: s < 1 means over 100 % uncertain = not determined


@dataclass
class ParamEstimate:
    name: str
    value: Optional[float]            # None when not identifiable
    ci95: Optional[tuple]
    rel_se: Optional[float]
    identifiable: bool
    leak: float                        # fraction of this parameter's axis lying in the null space


@dataclass
class IdentResult:
    status: str                        # "ok", "partially_identifiable" or "unidentifiable"
    estimates: Dict[str, ParamEstimate]
    fixed: Dict[str, float]
    cost: float
    n_obs: int
    rank: int
    n_free: int
    singular_values: List[float]
    null_space: List[str]              # human-readable null-space directions
    combinations: List[dict]           # well-determined log-parameter combinations
    theta_hat: Dict[str, float]        # the optimiser's full parameter vector (NOT to be reported for non-identifiable entries)
    log_cov: Optional[np.ndarray] = field(repr=False, default=None)
    null_basis: Optional[np.ndarray] = field(repr=False, default=None)    # columns span the undetermined log-parameter directions
    free: Sequence[str] = ()
    notes: List[str] = field(default_factory=list)

    def values(self) -> Dict[str, float]:
        """Only the parameters the data determines."""
        return {k: e.value for k, e in self.estimates.items() if e.identifiable}

    def summary(self) -> str:
        lines = [f"status: {self.status}  (rank {self.rank} of {self.n_free} free parameters, {self.n_obs} residuals)"]
        for n, e in self.estimates.items():
            if e.identifiable:
                lines.append(f"  {n:3s} = {e.value:.4g}  (95 % CI {e.ci95[0]:.4g} .. {e.ci95[1]:.4g})")
            else:
                lines.append(f"  {n:3s} : NOT IDENTIFIABLE from this data (axis weight in null space {e.leak:.2f})")
        for s in self.null_space:
            lines.append("  undetermined direction: " + s)
        return "\n".join(lines)


def _residual_builder(runs: Sequence[Run], free: Sequence[str], fixed: Dict[str, float], ratio: float, eta: float,
                      added_inertia: Sequence[float], sigma_theta_deg: float, sigma_i: float, use_current: bool):
    def full(x):
        p = dict(fixed)
        p.update({n: math.exp(v) for n, v in zip(free, x)})
        return p

    def resid(x):
        p = full(x)
        out = []
        for r, ja in zip(runs, added_inertia):
            th, _w, i = simulate_open_loop(p, r.V, r.dt, ratio=ratio, eta=eta, J_added_out=ja)
            out.append((np.degrees(th) - r.theta_deg) / sigma_theta_deg)
            if use_current and r.i is not None:
                out.append((i - r.i) / sigma_i)
        return np.concatenate(out)

    return resid, full


def identify(runs: Sequence[Run], cfg: dict, *, free: Sequence[str] = PARAMS, fixed: Optional[Dict[str, float]] = None,
             bounds: Optional[Dict[str, tuple]] = None, added_inertia: Optional[Sequence[float]] = None, n_starts: int = 3,
             seed: int = 0, sigma_theta_deg: Optional[float] = None, sigma_i: float = 0.05, use_current: bool = True) -> IdentResult:
    """Fit ``free`` parameters to ``runs``; everything else is taken from ``fixed`` or, failing that, the active YAML set.

    added_inertia   known extra inertia on the OUTPUT shaft for each run [kg*m^2] (0 for an ordinary run)
    sigma_theta_deg angle noise; default = encoder quantisation LSB / sqrt(12)
    """
    ratio = cfg["gearbox"]["ratio"]
    cpr = cfg["encoder"]["output_cpr"]
    eta = cfg["gearbox"]["efficiency"]
    sc = cfg["simulation"]["active_electrical_scenario"]
    d, e = cfg["base_motor"]["derived"][sc], cfg["base_motor"]["estimated"]
    nominal = {"R": d["R_ohm"], "Ke": d["Ke_V_s_per_rad"], "Kt": d["Kt_Nm_per_A"], "Jm": e["Jm_kgm2"], "Bm": e["Bm_Nms_per_rad"]}
    fixed_full = {k: v for k, v in nominal.items() if k not in free}
    fixed_full.update(fixed or {})
    added = list(added_inertia) if added_inertia is not None else [0.0] * len(runs)
    sig_th = sigma_theta_deg if sigma_theta_deg is not None else (360.0 / cpr) / math.sqrt(12.0)
    resid, full = _residual_builder(runs, free, fixed_full, ratio, eta, added, sig_th, sigma_i, use_current)

    b = dict(DEFAULT_BOUNDS)
    b.update(bounds or {})
    lo = np.array([math.log(b[n][0]) for n in free])
    hi = np.array([math.log(b[n][1]) for n in free])
    rng = np.random.default_rng(seed)
    x0s = [np.clip(np.array([math.log(nominal[n]) for n in free]), lo, hi)]
    for _ in range(max(n_starts - 1, 0)):
        x0s.append(np.clip(x0s[0] + rng.uniform(-1.5, 1.5, len(free)), lo, hi))

    best = None  # least_squares result with the lowest cost
    for x0 in x0s:
        sol = least_squares(resid, x0, bounds=(lo, hi), x_scale=1.0, method="trf", max_nfev=200, xtol=1e-10, ftol=1e-10)
        if best is None or sol.cost < best.cost:
            best = sol
    assert best is not None
    x = best.x
    J = best.jac
    n_obs = len(best.fun)
    U, s, Vt = np.linalg.svd(J, full_matrices=False)
    keep = (s > RANK_TOL * s[0]) & (s > MIN_SINGULAR)      # a direction counts as determined if it is not numerically null AND its uncertainty is below 100 %
    rank = int(np.sum(keep))
    Vr, sr = Vt[keep].T, s[keep]
    Vn = Vt[~keep].T if (~keep).any() else np.zeros((len(free), 0))
    s2 = 2.0 * best.cost / max(n_obs - rank, 1)
    cov = s2 * (Vr / sr ** 2) @ Vr.T                    # covariance of the log-parameters in the determined subspace

    ests = {}
    for j, n in enumerate(free):
        leak = float(np.sum(Vn[j] ** 2)) if Vn.shape[1] else 0.0
        ok = leak < NULL_LEAK_TOL
        if ok:
            se = float(math.sqrt(max(cov[j, j], 0.0)))
            val = math.exp(x[j])
            ests[n] = ParamEstimate(n, val, (val * math.exp(-1.96 * se), val * math.exp(1.96 * se)), se, True, leak)
        else:
            ests[n] = ParamEstimate(n, None, None, None, False, leak)

    null_desc = []
    for k in range(Vn.shape[1]):
        v = Vn[:, k]
        v = v / np.max(np.abs(v)) if np.max(np.abs(v)) > 0 else v
        terms = [f"{c:+.2f}*log({n})" for n, c in zip(free, v) if abs(c) > 0.1]
        null_desc.append(" ".join(terms) + " is not determined (any value of this combination fits equally well)")
    combos = []
    for k in range(rank):
        v = Vr[:, k]
        val = math.exp(float(v @ x))
        combos.append({"coefficients": {n: float(c) for n, c in zip(free, v) if abs(c) > 1e-3}, "value": val, "rel_se": float(math.sqrt(s2) / sr[k])})

    n_id = sum(1 for e_ in ests.values() if e_.identifiable)
    status = "ok" if n_id == len(free) else ("partially_identifiable" if n_id else "unidentifiable")
    notes = []
    if not use_current or all(r.i is None for r in runs):
        notes.append("no current data: only Kt/(R*Jm) and (Kt*Ke/R + Bm)/Jm are determined by the angle response")
    res = IdentResult(status, ests, {k: v for k, v in fixed_full.items() if k not in free}, float(best.cost), n_obs, rank, len(free),
                      [float(v) for v in s], null_desc, combos, full(x), cov, Vn, tuple(free), notes)
    return res


def lumped_estimates(result: IdentResult) -> Dict[str, dict]:
    """Named lumped quantities with delta-method standard errors, valid even when R, Kt, Ke, Jm, Bm are not identifiable.

    Each entry reports whether the quantity itself is determined (its gradient has no component in the null space)."""
    th = result.theta_hat
    free = list(result.free)
    defs = {
        "Kt/(R*Jm)": lambda t: t["Kt"] / (t["R"] * t["Jm"]),
        "(Kt*Ke/R+Bm)/Jm": lambda t: (t["Kt"] * t["Ke"] / t["R"] + t["Bm"]) / t["Jm"],
        "Jm/Kt": lambda t: t["Jm"] / t["Kt"],
        "Bm/Kt": lambda t: t["Bm"] / t["Kt"],
    }
    out = {}
    for name, f in defs.items():
        if not all(k in th for k in ("R", "Ke", "Kt", "Jm", "Bm")):
            continue
        base = math.log(f(th))
        g = np.zeros(len(free))
        for j, n in enumerate(free):
            t2 = dict(th); t2[n] = th[n] * math.exp(1e-6)
            g[j] = (math.log(f(t2)) - base) / 1e-6
        Vn = result.null_basis
        leak = float(np.linalg.norm(Vn.T @ g) / np.linalg.norm(g)) if Vn is not None and Vn.shape[1] and np.linalg.norm(g) > 0 else 0.0
        var = float(g @ result.log_cov @ g)
        out[name] = {"value": f(th), "rel_se": math.sqrt(max(var, 0.0)), "identifiable": leak < NULL_LEAK_TOL, "null_leak": leak}
    return out


def write_candidate_yaml(result: IdentResult, path, *, source_csv: Optional[str] = None, note: str = "") -> pathlib.Path:
    """Write a CANDIDATE parameter file (never the active config): identified values with intervals, provenance EXPERIMENTAL."""
    path = pathlib.Path(path)
    doc = {
        "status": "candidate -- not applied; review before copying anything into config/motor_parameters.yaml",
        "provenance": "EXPERIMENTAL (identified from bench data)",
        "identification_status": result.status,
        "identified": {n: {"value": e.value, "ci95": list(e.ci95)} for n, e in result.estimates.items() if e.identifiable},
        "not_identifiable": [n for n, e in result.estimates.items() if not e.identifiable],
        "undetermined_directions": result.null_space,
        "held_fixed_at": result.fixed,
        "fit": {"cost": result.cost, "n_residuals": result.n_obs, "rank": result.rank},
    }
    if source_csv:
        doc["source_csv"] = pathlib.Path(source_csv).name
        doc["source_csv_sha256"] = hashlib.sha256(pathlib.Path(source_csv).read_bytes()).hexdigest()
    if note:
        doc["note"] = note
    path.write_text("# CANDIDATE parameters from validation/identify.py -- does not modify config/motor_parameters.yaml\n"
                    + yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path
