"""Trust tiers of a PID recommendation (G3B.0). Every output must carry its tier label and never say "perfect"/"optimal"
without the objective and constraints.

Tier 1  datasheet only (class priors where missing): robust gains across the parameter uncertainty, wide bands.
Tier 2  bench-identified: Tier 1 plus measured data whose identification passed the validation thresholds.
Tier 3  refined on hardware: Tier 2 plus a closed-loop relay/step test on the real system.
"""

from __future__ import annotations

from enum import IntEnum


class Tier(IntEnum):
    ESTIMATE = 1
    IDENTIFIED = 2
    REFINED = 3

    @property
    def label(self) -> str:
        return TIER_LABELS[int(self)]


TIER_LABELS = {
    1: "TIER 1 - datasheet estimate: safe starting point, expect to re-tune (preliminary, not validated)",
    2: "TIER 2 - identified from bench data: validated against measured data for the tested conditions only",
    3: "TIER 3 - refined on hardware: gains tuned from real closed-loop data on this unit",
}


def tier_for(*, has_bench_data: bool, identification_passed: bool, hardware_refined: bool) -> Tier:
    """Tier 1 until measured data is loaded; Tier 2 only after an identification that PASSED the validation thresholds;
    Tier 3 after on-hardware refinement (which itself requires Tier 2)."""
    if has_bench_data and identification_passed:
        return Tier.REFINED if hardware_refined else Tier.IDENTIFIED
    return Tier.ESTIMATE
