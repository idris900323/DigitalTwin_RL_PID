"""Shared test helpers: run the repo's own closed-loop twin and return metrics."""

import copy
import math
import pathlib
from dataclasses import dataclass

import numpy as np
import yaml

from simulation.interactive_pid_twin import build_twin
from simulation.metrics import overshoot_pct, rise_time, rmse, settling_time, steady_state_error

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "motor_parameters.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


@dataclass
class StepResult:
    t: np.ndarray
    theta_deg: np.ndarray
    error_deg: np.ndarray
    V: np.ndarray
    i: np.ndarray
    rise: float
    overshoot: float
    settle: float
    sse_deg: float
    rmse_deg: float
    log: dict


def run_step_response(
    kp: float,
    ki: float,
    kd: float,
    target_deg: float = 90.0,
    t_end: float = 2.0,
    dt: float = 1e-3,
    params: str = "method_c",
    extra_inertia: float = 0.0,
    cfg: dict | None = None,
) -> StepResult:
    """Closed-loop step response of the bare-shaft twin.

    ``params`` picks the electrical scenario (method_a / method_b / method_c)
    from the YAML; ``extra_inertia`` is added motor-side inertia in kg*m^2
    (i.e. already reflected through the gearbox, m*L^2/N^2).
    """
    cfg = copy.deepcopy(cfg if cfg is not None else load_config())
    cfg["simulation"]["active_electrical_scenario"] = params
    cfg["simulation"]["control_loop_dt_s"] = dt
    twin = build_twin(cfg, kp, ki, kd, extra_Jm_kgm2=extra_inertia)
    ref = math.radians(target_deg)
    log = twin.run(ref, int(round(t_end / dt)))
    theta = np.degrees(log["theta_out"])
    t = log["t"]
    return StepResult(
        t=t,
        theta_deg=theta,
        error_deg=np.degrees(log["error"]),
        V=log["V_cmd"],
        i=log["i_motor"],
        rise=rise_time(t, theta, target_deg),
        overshoot=overshoot_pct(theta, target_deg),
        settle=settling_time(t, theta, target_deg),
        sse_deg=steady_state_error(theta, target_deg),
        rmse_deg=rmse(theta, target_deg),
        log=log,
    )
