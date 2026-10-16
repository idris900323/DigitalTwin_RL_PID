"""Phase 7: quadrature encoder model, output-side.

9360 CPR already includes 13 Hall sensors x4 (quadrature decode) x180 (gear
ratio) -- see datasheet/parameter_table.md. This encoder reads theta_joint
(the gearbox OUTPUT shaft) directly; it is NOT a motor-shaft encoder
(critical constraint, master prompt \xa72) -- never feed it theta_m.
"""

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class EncoderParams:
    """Counts per output revolution and optional Gaussian angle noise [rad]."""
    counts_per_rev: int          # DATASHEET 9360 (52 base CPR x 180 gear ratio): comes from the YAML, no default
    noise_std_rad: float = 0.0   # ASSUMED zero by default; configurable


class Encoder:
    """Output-side quadrature encoder: quantises the true joint angle to counts, optionally with noise."""
    def __init__(self, params: EncoderParams, rng: Optional[np.random.Generator] = None):
        self.p = params
        self._rad_per_count = 2.0 * math.pi / params.counts_per_rev
        self._rng = rng or np.random.default_rng()

    def read(self, theta_true_rad: float) -> float:
        """Measured angle [rad]: the true angle plus noise, rounded to the nearest count."""
        theta = theta_true_rad
        if self.p.noise_std_rad > 0.0:
            theta = theta + self._rng.normal(0.0, self.p.noise_std_rad)
        counts = round(theta / self._rad_per_count)
        return counts * self._rad_per_count
