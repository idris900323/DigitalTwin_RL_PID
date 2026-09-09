"""Minimal operational digital twin demo: motor + gearbox + bare output shaft
+ encoder + fixed-gain PID, with Kp/Ki/Kd as live sliders so you can see the
step response change as you tune.

Scope (per current project decisions -- see conversation / README):
  - Controlled variable: output shaft position theta (deg), step reference.
  - Load: bare motor+gearbox shaft, no arm/payload (external torque = 0).
  - Electrical parameters: "method_c" hybrid (see config/motor_parameters.yaml
    and datasheet/parameter_table.md for why).
  - Not yet included: PyBullet visualization (Phase 10), real arm/payload
    (Phase 6 proper), RL (Phase 13+). This is Phases 5-9 minimally combined.

Run: just open this file and hit Run (VS Code's play button, F5, etc.) --
no PYTHONPATH setup needed, see the sys.path bootstrap below. Equivalent
from a terminal: PYTHONPATH=. python simulation/interactive_pid_twin.py
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # lets `python simulation/this_file.py` find controllers/models/simulation

import math

import matplotlib.pyplot as plt
import numpy as np
import yaml
from matplotlib.widgets import Slider

from controllers.pid import PID, PIDParams
from models.dc_motor import DCMotor, DCMotorParams
from models.digital_twin import DigitalTwin
from models.encoder import Encoder, EncoderParams
from models.gearbox import Gearbox, GearboxParams
from models.joint import Joint
from simulation.metrics import overshoot_pct, rise_time, rmse, settling_time, steady_state_error

CONFIG_PATH = ROOT / "config" / "motor_parameters.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def build_twin(cfg: dict, Kp: float, Ki: float, Kd: float, extra_Jm_kgm2: float = 0.0) -> DigitalTwin:
    """extra_Jm_kgm2: additional motor-side inertia (e.g. an arm/payload's
    point-mass inertia m*L^2 reflected through the gearbox as /ratio^2),
    added on top of the base motor's own estimated inertia. Zero by default
    (bare shaft, this module's normal scope)."""
    scenario = cfg["simulation"]["active_electrical_scenario"]
    d = cfg["base_motor"]["derived"][scenario]
    e = cfg["base_motor"]["estimated"]
    motor = DCMotor(DCMotorParams(
        R=d["R_ohm"], L=e["L_H"], Kt=d["Kt_Nm_per_A"], Ke=d["Ke_V_s_per_rad"],
        Jm=e["Jm_kgm2"] + extra_Jm_kgm2, Bm=e["Bm_Nms_per_rad"],
    ))
    gearbox = Gearbox(GearboxParams(ratio=cfg["gearbox"]["ratio"], efficiency=cfg["gearbox"]["efficiency"]))
    joint = Joint()  # no arm, zero external torque -- see module docstring
    encoder = Encoder(EncoderParams(counts_per_rev=cfg["encoder"]["output_cpr"], noise_std_rad=0.0))
    dt = cfg["simulation"]["control_loop_dt_s"]
    pid = PID(PIDParams(Kp=Kp, Ki=Ki, Kd=Kd, dt=dt, output_min=-cfg["supply"]["V_rated"], output_max=cfg["supply"]["V_rated"]))
    return DigitalTwin(motor=motor, gearbox=gearbox, joint=joint, encoder=encoder, pid=pid, dt=dt)


def main():
    cfg = load_config()
    dt = cfg["simulation"]["control_loop_dt_s"]
    duration = cfg["simulation"]["run_duration_s"]
    n_steps = int(duration / dt)
    theta_ref = math.radians(cfg["simulation"]["theta_ref_default_deg"])
    defaults = cfg["pid_defaults"]

    fig, (ax_theta, ax_err, ax_v) = plt.subplots(3, 1, figsize=(8, 8), sharex=True)
    plt.subplots_adjust(bottom=0.32, hspace=0.35)

    twin = build_twin(cfg, defaults["Kp"], defaults["Ki"], defaults["Kd"])
    log = twin.run(theta_ref, n_steps)
    theta_deg = np.degrees(log["theta_out"])
    ref_deg = math.degrees(theta_ref)

    (line_theta,) = ax_theta.plot(log["t"], theta_deg, label="theta_out")
    ax_theta.axhline(ref_deg, color="gray", linestyle="--", label="reference")
    ax_theta.set_ylabel("Angle [deg]")
    ax_theta.legend(loc="lower right")
    ax_theta.set_title("Output shaft position step response")

    (line_err,) = ax_err.plot(log["t"], np.degrees(log["error"]))
    ax_err.set_ylabel("Error [deg]")
    ax_err.axhline(0.0, color="gray", linewidth=0.5)

    (line_v,) = ax_v.plot(log["t"], log["V_cmd"])
    ax_v.axhline(cfg["supply"]["V_rated"], color="red", linestyle=":", linewidth=0.8)
    ax_v.axhline(-cfg["supply"]["V_rated"], color="red", linestyle=":", linewidth=0.8)
    ax_v.set_ylabel("Control voltage [V]")
    ax_v.set_xlabel("Time [s]")

    metrics_text = fig.text(0.02, 0.20, "", fontsize=9, family="monospace", va="top")

    def update_metrics(t, theta):
        rt = rise_time(t, theta, ref_deg)
        os_ = overshoot_pct(theta, ref_deg)
        st = settling_time(t, theta, ref_deg)
        sse = steady_state_error(theta, ref_deg)
        err_rmse = rmse(theta, ref_deg)
        metrics_text.set_text(
            f"rise time (10-90%): {rt:.3f} s\n"
            f"overshoot: {os_:.2f} %\n"
            f"settling time (2%): {st:.3f} s\n"
            f"steady-state error: {sse:.3f} deg\n"
            f"RMSE: {err_rmse:.3f} deg"
        )

    update_metrics(log["t"], theta_deg)

    ax_kp = plt.axes([0.15, 0.20, 0.65, 0.03])
    ax_ki = plt.axes([0.15, 0.15, 0.65, 0.03])
    ax_kd = plt.axes([0.15, 0.10, 0.65, 0.03])
    s_kp = Slider(ax_kp, "Kp", 0.0, defaults["Kp_max"], valinit=defaults["Kp"])
    s_ki = Slider(ax_ki, "Ki", 0.0, defaults["Ki_max"], valinit=defaults["Ki"])
    s_kd = Slider(ax_kd, "Kd", 0.0, defaults["Kd_max"], valinit=defaults["Kd"])

    def on_change(_val):
        twin_local = build_twin(cfg, s_kp.val, s_ki.val, s_kd.val)
        log_local = twin_local.run(theta_ref, n_steps)
        theta_deg_local = np.degrees(log_local["theta_out"])

        line_theta.set_ydata(theta_deg_local)
        line_err.set_ydata(np.degrees(log_local["error"]))
        line_v.set_ydata(log_local["V_cmd"])

        for ax, y in ((ax_theta, theta_deg_local), (ax_err, np.degrees(log_local["error"])), (ax_v, log_local["V_cmd"])):
            ax.relim()
            ax.autoscale_view()

        update_metrics(log_local["t"], theta_deg_local)
        fig.canvas.draw_idle()

    s_kp.on_changed(on_change)
    s_ki.on_changed(on_change)
    s_kd.on_changed(on_change)

    plt.show()


if __name__ == "__main__":
    main()
