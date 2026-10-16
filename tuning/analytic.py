"""Model-based starting points for PID gains on the linearised plant (see ``tuning.linear``).

* ``pole_placement``: closed-loop poles s^2 + 2 zeta wn s + wn^2 for the PD part, optional small Ki. When the plant is already
  overdamped at that bandwidth (large back-EMF damping) Kd = 0 and the dominant real pole is placed at -wn instead.
* ``imc_lambda``: IMC/lambda tuning of the integrating second-order plant, equivalent to critically damped placement with
  wn = 1 / lambda.
* ``ziegler_nichols``: classic ultimate-gain baseline, with Ku found on the loop *including* the digital delay (without a delay a
  second-order plant has no ultimate gain).

Pole placement uses the plant without the controller's derivative filter and the loop delay; the margins in
``tuning.linear`` check what those omissions cost, and ``design`` lowers wn until the requested margins hold.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

import numpy as np

from tuning.linear import LinearPlant

Gains = Tuple[float, float, float]


def pole_placement(plant: LinearPlant, wn: float, zeta: float = 1.0, ki_ratio: float = 0.0) -> Gains:
    """(Kp, Ki, Kd) placing the PD closed-loop poles at wn, zeta; Ki = ki_ratio * Kp * wn (0 = none)."""
    if 2.0 * zeta * wn < plant.a:
        # The plant's own damping (a = (Kt Ke/R + Bm)/J) already exceeds what the requested poles need, so Kd would be negative.
        # Use Kd = 0 and choose Kp so that the DOMINANT real pole sits at -wn: s^2 + a s + (c + b Kp/N) = (s + p)(s + a - p).
        p = wn
        kp = max(plant.N * (p * (plant.a - p) - plant.c) / plant.b, 0.0)
        return kp, ki_ratio * kp * wn, 0.0
    kp = plant.N * (wn ** 2 - plant.c) / plant.b
    kd = plant.N * (2.0 * zeta * wn - plant.a) / plant.b
    kp, kd = max(kp, 0.0), max(kd, 0.0)
    return kp, ki_ratio * kp * wn, kd


def imc_lambda(plant: LinearPlant, lam: float, ki_ratio: float = 0.0) -> Gains:
    """IMC/lambda tuning with closed-loop time constant ``lam`` [s] (critically damped, wn = 1/lam)."""
    return pole_placement(plant, 1.0 / lam, 1.0, ki_ratio)


def ziegler_nichols(plant: LinearPlant) -> Gains:
    """Classic ZN PID from the ultimate gain Ku and period Tu of the P-only loop (delay included)."""
    lo, hi = 1e-3, 1.0
    while plant.is_stable(hi, 0.0, 0.0) and hi < 1e9:
        lo, hi = hi, hi * 2.0
    for _ in range(80):                                  # bisection on stability
        mid = math.sqrt(lo * hi)
        if plant.is_stable(mid, 0.0, 0.0):
            lo = mid
        else:
            hi = mid
    ku = lo
    w = np.logspace(0, math.log10(0.8 * math.pi / plant.dt), 40000)
    L, _, _ = plant.frequency_response(ku, 0.0, 0.0, w)
    ph = np.unwrap(np.angle(L))
    i = int(np.argmin(np.abs(ph + math.pi)))
    tu = 2.0 * math.pi / w[i]
    return 0.6 * ku, 1.2 * ku / tu, 0.075 * ku * tu


def design(plant: LinearPlant, *, settle_s: float, min_pm_deg: float = 45.0, min_gm_db: float = 6.0, zeta: float = 1.0,
           ki_ratio: float = 0.0) -> Dict[str, object]:
    """Pole-placement gains with the fastest wn (from the settling target) that still meets the margin requirements.

    wn starts at 4/(zeta*settle_s) (2 % settling of a second-order response) and is reduced by 10 % until the linear loop,
    including filter and delay, has the requested gain/phase margins and is stable."""
    wn = 4.0 / (zeta * settle_s)
    for _ in range(80):
        g = pole_placement(plant, wn, zeta, ki_ratio)
        m = plant.margins(*g)
        if m["stable"] and m["phase_margin_deg"] >= min_pm_deg and m["gain_margin_db"] >= min_gm_db:
            return {"gains": g, "wn": wn, "margins": m, "note": "meets the requested margins"}
        wn *= 0.9
    return {"gains": g, "wn": wn, "margins": m, "note": "margins could not be met; lowest bandwidth returned"}
