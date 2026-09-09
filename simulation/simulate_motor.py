"""Phase 4 check: open-loop base-motor step response, no gearbox/joint/load yet.

Purpose: (1) sanity-check the Method A derived parameters (R, Kt, Ke) against
the datasheet's independently-stated no-load speed, by simulating a 12V step
with tau_load=0 and comparing the resulting steady-state speed to 18,000 RPM.
(2) produce a first open-loop transient plot for visual inspection.

Method B is NOT simulated here: it only yields Ke, not R or Kt, so the full
electrical+mechanical ODE cannot be run from it without inventing additional
values. Its no-load-speed prediction is exact by construction (that's how it
was derived) and is reported analytically for reference, not simulated.
"""

import pathlib

import matplotlib.pyplot as plt
import numpy as np
import yaml

from models.dc_motor import DCMotor, DCMotorParams
from models.units import rad_s_to_rpm

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "motor_parameters.yaml"
RESULTS_DIR = ROOT / "results"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def build_method_a_motor(cfg: dict) -> DCMotor:
    d = cfg["base_motor"]["derived"]["method_a"]
    e = cfg["base_motor"]["estimated"]
    params = DCMotorParams(
        R=d["R_ohm"],
        L=e["L_H"],
        Kt=d["Kt_Nm_per_A"],
        Ke=d["Ke_V_s_per_rad"],
        Jm=e["Jm_kgm2"],
        Bm=e["Bm_Nms_per_rad"],
    )
    return DCMotor(params)


def main():
    cfg = load_config()
    V_rated = cfg["supply"]["V_rated"]
    datasheet_no_load_rpm = cfg["base_motor"]["no_load_speed_rpm"]

    motor = build_method_a_motor(cfg)

    t_span = (0.0, 0.5)
    t_eval = np.linspace(*t_span, 2000)
    x0 = np.array([0.0, 0.0, 0.0])  # i=0, omega_m=0, theta_m=0 at rest

    sol = motor.simulate(
        t_span=t_span,
        x0=x0,
        V_func=lambda t: V_rated,   # 12V step at t=0
        tau_load_func=lambda t: 0.0,  # no load
        t_eval=t_eval,
    )

    i_t = sol.y[0]
    omega_t = sol.y[1]
    rpm_t = rad_s_to_rpm(omega_t)

    steady_rpm = rpm_t[-1]
    pct_diff = 100.0 * (steady_rpm - datasheet_no_load_rpm) / datasheet_no_load_rpm

    # Method B's no-load speed is exact by construction (it was derived from
    # this exact equation) -- reported analytically, not simulated.
    method_b_ke = cfg["base_motor"]["derived"]["method_b"]["Ke_V_s_per_rad"]
    method_b_rpm = rad_s_to_rpm(V_rated / method_b_ke)

    print("=== Phase 4: open-loop base motor step response (Method A params) ===")
    print(f"Datasheet no-load speed:        {datasheet_no_load_rpm:.1f} RPM")
    print(f"Method A simulated steady speed: {steady_rpm:.1f} RPM  ({pct_diff:+.1f}% vs datasheet)")
    print(f"Method B analytic no-load speed: {method_b_rpm:.1f} RPM (exact by construction)")
    print()
    print("Interpretation: Method A's R/Kt/Ke were derived from the stall-side "
          "assumption chain (load_current_max_A treated as stall current, "
          "gearbox eta=1 reflection) and were NOT fit to reproduce the "
          "datasheet's no-load speed. The discrepancy above is a genuine, "
          "quantifiable inconsistency between the two derivation paths, not "
          "simulation error -- see datasheet/parameter_table.md flags.")

    RESULTS_DIR.mkdir(exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(7, 6), sharex=True)
    axes[0].plot(sol.t, rpm_t)
    axes[0].axhline(datasheet_no_load_rpm, color="gray", linestyle="--", label="datasheet no-load (18000 RPM)")
    axes[0].set_ylabel("Speed [RPM]")
    axes[0].legend()
    axes[0].set_title("Base motor open-loop 12V step response (Method A params, no load)")

    axes[1].plot(sol.t, i_t)
    axes[1].set_ylabel("Current [A]")
    axes[1].set_xlabel("Time [s]")

    fig.tight_layout()
    out_path = RESULTS_DIR / "phase4_motor_step_response.png"
    fig.savefig(out_path, dpi=150)
    print(f"\nPlot saved to {out_path}")


if __name__ == "__main__":
    main()
