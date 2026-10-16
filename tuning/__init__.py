"""PID recommendation for any motor profile and load: analytic, optimised and robust tuning with uncertainty and tiers.

PRELIMINARY: every recommendation is computed on a model derived from a datasheet (Tier 1) unless bench data has been
loaded, and always carries its tier label and uncertainty. Nothing here is validated on hardware.
"""
