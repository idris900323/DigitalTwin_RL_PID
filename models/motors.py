"""Resolve a motor id to a simulation config: ``get_cfg('rmcs_3070')`` or any profile in ``motors/``.

The reference motor ``rmcs_3070`` keeps using the project's active parameter set from ``config/motor_parameters.yaml``
(profile block ``derived_model``), so every baseline number is unchanged. Any other profile goes through
``models.derive``: a physically consistent model with intervals, converted to the same config layout so all scripts,
the twin factory and the trainer's batch simulator work unchanged.
"""

from __future__ import annotations

from typing import Optional

import yaml

from models.derive import derive_model, to_config
from models.motor_profile import ROOT, Profile, list_motors, load_profile

DEFAULT_CONFIG = ROOT / "config" / "motor_parameters.yaml"
DEFAULT_MOTOR = "rmcs_3070"


def load_base_config(path=DEFAULT_CONFIG) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_profile(motor_id: str) -> Profile:
    return load_profile(motor_id)


def get_cfg(motor_id: str = DEFAULT_MOTOR, answers: Optional[dict] = None, base_cfg: Optional[dict] = None) -> dict:
    """Config for ``motor_id`` (see module docstring). ``answers`` resolves datasheet ambiguities for derived motors."""
    base = base_cfg if base_cfg is not None else load_base_config()
    prof = load_profile(motor_id)
    ref = prof.data.get("derived_model")
    if ref:
        cfg = load_base_config(ROOT / ref["source_config"]) if base_cfg is None else base
        cfg["motor_id"] = motor_id
        return cfg
    return to_config(derive_model(prof, answers), base)


def motor_from_argv(argv=None) -> str:
    """Peek at ``--motor`` before the full parser runs (some defaults come from the config, which depends on the motor)."""
    import argparse

    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--motor", default=DEFAULT_MOTOR)
    return pre.parse_known_args(argv)[0].motor


def add_motor_argument(parser) -> None:
    """Add the common ``--motor`` option to an argparse parser."""
    parser.add_argument("--motor", default=DEFAULT_MOTOR, choices=list_motors() or None,
                        help="motor profile in motors/ (default: %(default)s, the reference RMCS-3070 parameter set)")
