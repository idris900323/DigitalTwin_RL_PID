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
