"""Step-response performance metrics, per master prompt \xa715/\xa718.

Used by the PID demo now; reused later for the fixed-PID vs RL-PID
comparison table (Phase 16) so the definitions stay consistent.
"""

import numpy as np


def rise_time(t: np.ndarray, y: np.ndarray, ref: float, low: float = 0.1, high: float = 0.9) -> float:
    """Time from first crossing low*ref to first crossing high*ref. NaN if never reached.
    Works for negative steps too (the response is mirrored so that the step is positive)."""
    if ref == 0:
        return float("nan")
    if ref < 0:
        y, ref = -np.asarray(y), -ref
    low_thresh, high_thresh = low * ref, high * ref
    above_low = np.where(y >= low_thresh)[0]
    above_high = np.where(y >= high_thresh)[0]
    if len(above_low) == 0 or len(above_high) == 0:
        return float("nan")
    return t[above_high[0]] - t[above_low[0]]


def overshoot_pct(y: np.ndarray, ref: float) -> float:
    """Peak excursion beyond the target in the direction of the step, as a percentage of |ref| (0 if none)."""
    if ref == 0:
        return float("nan")
    if ref < 0:
        y, ref = -np.asarray(y), -ref
    peak = np.max(y)
    return max(0.0, 100.0 * (peak - ref) / ref)


def settling_time(t: np.ndarray, y: np.ndarray, ref: float, tol: float = 0.02) -> float:
    """Last time the response leaves the +-tol*ref band around ref. NaN if never settles."""
    if ref == 0:
        return float("nan")
    band = tol * abs(ref)
    outside = np.where(np.abs(y - ref) > band)[0]
    if len(outside) == 0:
        return 0.0
    last_outside = outside[-1]
    if last_outside == len(t) - 1:
        return float("nan")  # never actually settles within the simulated window
    return t[last_outside + 1]


def steady_state_error(y: np.ndarray, ref: float) -> float:
    return y[-1] - ref


def rmse(y: np.ndarray, ref: float) -> float:
    return float(np.sqrt(np.mean((y - ref) ** 2)))


# ---------------------------------------------------------------------------------------------------------------
# Integral error and effort metrics (master prompt s18). All are sampled sums with a uniform step dt = t[1] - t[0]
# (rectangle rule), so a signal of constant value c over duration T gives c*T.  Units follow the inputs:
# error in deg -> IAE [deg*s], ISE [deg^2*s], ITAE [deg*s^2]; voltage in V -> effort [V*s], [V^2*s]; current in A.
# ---------------------------------------------------------------------------------------------------------------

def _dt(t: np.ndarray) -> float:
    return float(t[1] - t[0]) if len(t) > 1 else 0.0


def iae(t: np.ndarray, e: np.ndarray) -> float:
    """Integral of absolute error, sum(|e|)*dt."""
    return float(np.sum(np.abs(e)) * _dt(t))


def ise(t: np.ndarray, e: np.ndarray) -> float:
    """Integral of squared error, sum(e^2)*dt."""
    return float(np.sum(np.asarray(e) ** 2) * _dt(t))


def itae(t: np.ndarray, e: np.ndarray) -> float:
    """Integral of time-weighted absolute error, sum(t*|e|)*dt."""
    return float(np.sum(np.asarray(t) * np.abs(e)) * _dt(t))


def mae(e: np.ndarray) -> float:
    """Mean absolute error."""
    return float(np.mean(np.abs(e)))


def control_effort_abs(t: np.ndarray, u: np.ndarray) -> float:
    """Integral of |u| dt (voltage * time)."""
    return float(np.sum(np.abs(u)) * _dt(t))


def control_effort_sq(t: np.ndarray, u: np.ndarray) -> float:
    """Integral of u^2 dt (a measure of heating / energy in the command)."""
    return float(np.sum(np.asarray(u) ** 2) * _dt(t))


def peak_current(i: np.ndarray) -> float:
    """Largest |armature current| [A]."""
    return float(np.max(np.abs(i)))


def energy_drawn(t: np.ndarray, V: np.ndarray, i: np.ndarray) -> float:
    """Electrical energy drawn from the supply [J]: sum(max(V*i, 0))*dt.

    Negative instantaneous power (regeneration / braking back into the supply) is clamped to zero: a bench
    supply cannot absorb it and the driver is assumed not to recover it. Choose a different convention
    explicitly if the real driver recovers energy."""
    return float(np.sum(np.maximum(np.asarray(V) * np.asarray(i), 0.0)) * _dt(t))


def time_to_band(t: np.ndarray, y: np.ndarray, ref: float, tol: float = 0.02) -> float:
    """First time the response enters the +-tol*|ref| band around ref (it may leave again; see settling_time)."""
    if ref == 0:
        return float("nan")
    inside = np.where(np.abs(np.asarray(y) - ref) <= tol * abs(ref))[0]
    return float(t[inside[0]]) if len(inside) else float("nan")


METRIC_NAMES = ("rise_s", "overshoot_pct", "settle_s", "time_to_2pct_s", "sse_deg", "rmse_deg", "mae_deg", "iae_deg_s",
                "ise_deg2_s", "itae_deg_s2", "effort_abs_Vs", "effort_sq_V2s", "peak_current_A", "energy_J")


def all_metrics(t, theta_deg, ref_deg, V, i, error_deg=None) -> dict:
    """Every metric for one step response, as a dict keyed by ``METRIC_NAMES``.

    ``error_deg`` is the tracking error used for the integral metrics (default ref - theta); the twin logs the
    *measured* (quantised) error, which can be passed instead."""
    t, theta_deg = np.asarray(t), np.asarray(theta_deg)
    e = (ref_deg - theta_deg) if error_deg is None else np.asarray(error_deg)
    return {
        "rise_s": rise_time(t, theta_deg, ref_deg),
        "overshoot_pct": overshoot_pct(theta_deg, ref_deg),
        "settle_s": settling_time(t, theta_deg, ref_deg),
        "time_to_2pct_s": time_to_band(t, theta_deg, ref_deg),
        "sse_deg": steady_state_error(theta_deg, ref_deg),
        "rmse_deg": rmse(theta_deg, ref_deg),
        "mae_deg": mae(e),
        "iae_deg_s": iae(t, e),
        "ise_deg2_s": ise(t, e),
        "itae_deg_s2": itae(t, e),
        "effort_abs_Vs": control_effort_abs(t, V),
        "effort_sq_V2s": control_effort_sq(t, V),
        "peak_current_A": peak_current(i),
        "energy_J": energy_drawn(t, V, i),
    }
