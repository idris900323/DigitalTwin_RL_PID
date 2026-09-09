"""Phase 10 (brought forward, minimal): CAD-based 3D visualization of PID
control on the output shaft, with live embedded response graphs.

Geometry source: cad/.../JGB37-520.STEP, converted via cascadio (STEP ->
GLB) and loaded with trimesh -- master prompt \xa714's STEP -> mesh ->
visualization workflow. Rendering uses pyvista (VTK), not PyBullet -- no
prebuilt PyBullet wheel exists for this Python/Windows combo, and building
it needs MSVC Build Tools, not installed without asking. This is
visualization only; nothing here is a physics engine or controller. The
rotation and all curves come entirely from models/digital_twin.py's
simulated physics -- the CAD supplies shape only, and PyBullet's own
controllers are still never used as the research PID (\xa713), moot either
way.

CAD PROVENANCE REMINDER: this is the JGB37-520 reference CAD, NOT verified
to be the exact RMCS-3013/3070 model (\xa73). Its scale is broadly consistent
with the RMCS-3013 datasheet (shaft ~6mm dia here vs 6mm datasheet; gearbox
body ~37mm here vs 36mm datasheet) -- a plausible sanity check, not a
confirmed match.

VISUALIZATION-ONLY ADDITIONS, NOT CAD/hardware features or physics (\xa720:
never hide assumptions):
  - A rod + ball "arm" rigidly attached to the output shaft. A plain round
    shaft spinning about its own axis of symmetry is visually indistinguish-
    able frame to frame; the arm makes angular position (and therefore
    overshoot/oscillation/damping) actually visible. It carries NO inertia
    or mass in the physics -- the joint is still the bare motor+gearbox
    shaft with zero external torque, per the earlier "no arm yet, Phase 6
    deferred" decision. If/when a real arm/payload is specified, this
    visual stand-in should be replaced with the real thing feeding back
    into the dynamics, not just the picture.
  - The idle "Spin (Demo)" mode sweeps 0<->180 degrees (a servo-like wag)
    instead of spinning continuously, matching the eventual bounded-joint
    framing. It is still not physics -- constant angular rate, no PID.

PID preset buttons use gains that were actually simulated and measured
against this model (not guessed) -- see the chat for the grid search:
  - Sluggish (low P):   Kp=1.5, Ki=0,  Kd=0    -- doesn't fully reach the
    target within the demo window (still ~8deg short at t=2s).
  - Oscillatory (high P): Kp=45, Ki=0, Kd=0    -- ~11% overshoot, one clear
    overshoot-and-settle cycle. Overshoot plateaus near 11% even at higher
    Kp/Ki because the +-12V voltage saturation dominates the transient once
    gains are large -- a genuine model finding, not a demo limitation
    papered over.
  - Tuned (damped):     Kp=15, Ki=0, Kd=0.3    -- ~1.7% overshoot, settles
    in ~0.29s. Found by grid search over the same model, not asserted.

Run:
    PYTHONPATH=. python simulation/cad_pid_visualizer.py
"""

import math
import pathlib
import time

import numpy as np
import pyvista as pv
import trimesh

from simulation.interactive_pid_twin import build_twin, load_config
from simulation.metrics import overshoot_pct, rise_time, settling_time, steady_state_error

ROOT = pathlib.Path(__file__).resolve().parents[1]
GLB_PATH = ROOT / "cad" / "JGB37-520_converted.glb"

ROTATING_PART_KEYWORDS = ("MOTOR SHAFT", "SHAFT COUPLER")
PLAYBACK_STRIDE = 5              # 2000 sim steps -> 400 playback frames
TICK_INTERVAL_MS = 25
SWEEP_PERIOD_S = 4.0              # idle demo: one full 0->180->0 cycle
ARM_LENGTH_M = 0.05               # visualization-only, see module docstring
ARM_RADIUS_M = 0.0015
ARM_WEIGHT_RADIUS_M = 0.006

PRESETS = {
    "sluggish": dict(Kp=1.5, Ki=0.0, Kd=0.0),
    "oscillatory": dict(Kp=45.0, Ki=0.0, Kd=0.0),
    "tuned": dict(Kp=15.0, Ki=0.0, Kd=0.3),
}


def load_cad_parts():
    scene = trimesh.load(GLB_PATH)
    static_meshes, rotating_meshes = [], []
    for name, g in scene.geometry.items():
        faces = np.hstack([np.full((len(g.faces), 1), 3), g.faces]).astype(np.int64)
        mesh = pv.PolyData(g.vertices, faces)
        (rotating_meshes if any(k in name for k in ROTATING_PART_KEYWORDS) else static_meshes).append(mesh)
    static = static_meshes[0].merge(static_meshes[1:])
    rotating = rotating_meshes[0].merge(rotating_meshes[1:])
    return static, rotating


def make_arm(rotating_bounds):
    """Rod + weight, visualization-only (see module docstring)."""
    xmin, xmax, ymin, ymax, zmin, zmax = rotating_bounds
    tip_z = zmax * 0.85
    rod = pv.Cylinder(center=(ARM_LENGTH_M / 2, 0.0, tip_z), direction=(1, 0, 0),
                       radius=ARM_RADIUS_M, height=ARM_LENGTH_M)
    weight = pv.Sphere(radius=ARM_WEIGHT_RADIUS_M, center=(ARM_LENGTH_M, 0.0, tip_z))
    return rod.merge(weight)


def main():
    cfg = load_config()
    dt = cfg["simulation"]["control_loop_dt_s"]
    duration = cfg["simulation"]["run_duration_s"]
    n_steps = int(duration / dt)
    theta_ref = math.radians(cfg["simulation"]["theta_ref_default_deg"])
    ref_deg = math.degrees(theta_ref)
    d = cfg["pid_defaults"]

    static_mesh, rotating_mesh = load_cad_parts()
    rotating_mesh = rotating_mesh.merge(make_arm(rotating_mesh.bounds))

    pl = pv.Plotter(window_size=(1600, 900))
    pl.set_background("white")
    pl.add_mesh(static_mesh, color="#b5b5b5", smooth_shading=True, specular=0.4, specular_power=15)
    actor = pl.add_mesh(rotating_mesh, color="#d95f02", smooth_shading=True, specular=0.6, specular_power=20)
    pl.add_axes()
    pl.view_isometric()
    pl.camera.azimuth += 25
    pl.reset_camera()
    pl.camera.SetWindowCenter(0.35, 0.0)  # bias the 3D content left, leave room for charts on the right

    # --- embedded live charts (right side) -----------------------------
    t_axis = np.linspace(0, duration, n_steps // PLAYBACK_STRIDE)

    chart_angle = pv.Chart2D(size=(0.32, 0.28), loc=(0.66, 0.68), x_label="t [s]", y_label="angle [deg]")
    angle_line = chart_angle.line(t_axis, np.zeros_like(t_axis), color="#1f77b4", width=2)
    angle_ref_line = chart_angle.line(np.array([0, duration]), np.array([ref_deg, ref_deg]), color="gray", width=1)
    angle_cursor = chart_angle.scatter(np.array([0.0]), np.array([0.0]), color="red", size=8)
    chart_angle.y_range = (-10, 190)
    chart_angle.title = "Output angle"

    chart_error = pv.Chart2D(size=(0.32, 0.28), loc=(0.66, 0.36), x_label="t [s]", y_label="error [deg]")
    error_line = chart_error.line(t_axis, np.zeros_like(t_axis), color="#d62728", width=2)
    error_cursor = chart_error.scatter(np.array([0.0]), np.array([0.0]), color="black", size=8)
    chart_error.y_range = (-30, 30)
    chart_error.title = "Tracking error"

    chart_v = pv.Chart2D(size=(0.32, 0.28), loc=(0.66, 0.04), x_label="t [s]", y_label="V_cmd [V]")
    v_line = chart_v.line(t_axis, np.zeros_like(t_axis), color="#2ca02c", width=2)
    v_cursor = chart_v.scatter(np.array([0.0]), np.array([0.0]), color="black", size=8)
    chart_v.y_range = (-13, 13)
    chart_v.title = "Control voltage"

    pl.add_chart(chart_angle, chart_error, chart_v)

    # --- sliders (Kp/Ki/Kd) --------------------------------------------
    state = {
        "Kp": d["Kp"], "Ki": d["Ki"], "Kd": d["Kd"],
        "mode": "idle", "sweep_t": 0.0,
        "run_t": None, "run_theta": None, "run_V": None, "run_idx": 0,
    }

    kp_slider = pl.add_slider_widget(lambda v: state.__setitem__("Kp", v), [0.0, d["Kp_max"]], value=d["Kp"],
                                      title="Kp", pointa=(0.02, 0.93), pointb=(0.28, 0.93))
    ki_slider = pl.add_slider_widget(lambda v: state.__setitem__("Ki", v), [0.0, d["Ki_max"]], value=d["Ki"],
                                      title="Ki", pointa=(0.02, 0.85), pointb=(0.28, 0.85))
    kd_slider = pl.add_slider_widget(lambda v: state.__setitem__("Kd", v), [0.0, d["Kd_max"]], value=d["Kd"],
                                      title="Kd", pointa=(0.02, 0.77), pointb=(0.28, 0.77))

    pl.add_text("Mode: idle -- click a button below", position="upper_left", font_size=11, name="status")

    # --- simulate + push a run into the charts/animation state ---------
    def do_run(Kp, Ki, Kd):
        twin = build_twin(cfg, Kp, Ki, Kd)
        log = twin.run(theta_ref, n_steps)
        t = log["t"][::PLAYBACK_STRIDE]
        theta = np.degrees(log["theta_out"])[::PLAYBACK_STRIDE]
        err = np.degrees(log["error"])[::PLAYBACK_STRIDE]
        V = log["V_cmd"][::PLAYBACK_STRIDE]

        angle_line.update(t, theta)
        error_line.update(t, err)
        v_line.update(t, V)

        rt = rise_time(t, theta, ref_deg)
        os_ = overshoot_pct(theta, ref_deg)
        st = settling_time(t, theta, ref_deg)
        sse = steady_state_error(theta, ref_deg)
        pl.add_text(
            f"Kp={Kp:.2f} Ki={Ki:.2f} Kd={Kd:.3f}  |  rise={rt:.2f}s  overshoot={os_:.1f}%  "
            f"settle={st:.2f}s  sse={sse:.2f}deg",
            position="upper_left", font_size=11, name="status",
        )

        state["run_t"], state["run_theta"], state["run_V"] = t, theta, V
        state["run_idx"] = 0
        state["mode"] = "run"
        spin_widget.GetRepresentation().SetState(0)
        run_widget.GetRepresentation().SetState(1)

    # --- buttons ----------------------------------------------------
    def on_spin(value):
        if not value:
            return
        run_widget.GetRepresentation().SetState(0)
        state["mode"] = "spin"
        state["sweep_t"] = 0.0
        pl.add_text("Mode: idle spin demo (0<->180 deg sweep, not physics)", position="upper_left", font_size=11, name="status")

    def on_run(value):
        if not value:
            return
        do_run(state["Kp"], state["Ki"], state["Kd"])

    def make_preset_handler(name):
        gains = PRESETS[name]

        def handler(value):
            if not value:
                return
            state["Kp"], state["Ki"], state["Kd"] = gains["Kp"], gains["Ki"], gains["Kd"]
            kp_slider.GetRepresentation().SetValue(gains["Kp"])
            ki_slider.GetRepresentation().SetValue(gains["Ki"])
            kd_slider.GetRepresentation().SetValue(gains["Kd"])
            do_run(gains["Kp"], gains["Ki"], gains["Kd"])
            preset_widgets[name].GetRepresentation().SetState(0)

        return handler

    spin_widget = pl.add_checkbox_button_widget(on_spin, value=False, position=(30, 30), size=36, color_on="#2ca02c")
    pl.add_text("Spin (Demo)", position=(75, 35), font_size=9, name="spin_label")
    run_widget = pl.add_checkbox_button_widget(on_run, value=False, position=(210, 30), size=36, color_on="#1f77b4")
    pl.add_text("Run PID", position=(255, 35), font_size=9, name="run_label")

    preset_widgets = {}
    preset_x = [370, 560, 750]
    preset_labels = {"sluggish": "Sluggish (low P)", "oscillatory": "Oscillatory (high P)", "tuned": "Tuned (damped)"}
    for (name, x) in zip(PRESETS, preset_x):
        w = pl.add_checkbox_button_widget(make_preset_handler(name), value=False, position=(x, 30), size=36, color_on="#9467bd")
        preset_widgets[name] = w
        pl.add_text(preset_labels[name], position=(x + 45, 35), font_size=9, name=f"preset_label_{name}")

    # Auto-start the idle sweep so motion is visible immediately.
    spin_widget.GetRepresentation().SetState(1)
    on_spin(True)

    # --- animation tick ---------------------------------------------
    def tick():
        if state["mode"] == "spin":
            state["sweep_t"] += TICK_INTERVAL_MS / 1000.0
            phase = (state["sweep_t"] % SWEEP_PERIOD_S) / SWEEP_PERIOD_S  # 0..1
            triangle = 1.0 - abs(2.0 * phase - 1.0)  # 0->1->0
            angle_deg = 180.0 * triangle
            actor.orientation = (0.0, 0.0, angle_deg)
            pl.render()
        elif state["mode"] == "run":
            i = state["run_idx"]
            if i >= len(state["run_t"]):
                state["mode"] = "idle"
                run_widget.GetRepresentation().SetState(0)
                pl.render()
                return
            actor.orientation = (0.0, 0.0, state["run_theta"][i])
            t_i = state["run_t"][i]
            angle_cursor.update(np.array([t_i]), np.array([state["run_theta"][i]]))
            error_cursor.update(np.array([t_i]), np.array([ref_deg - state["run_theta"][i]]))
            v_cursor.update(np.array([t_i]), np.array([state["run_V"][i]]))
            pl.render()
            state["run_idx"] += 1

    # Manually driven loop (not add_timer_event): a mismatched VTK timer
    # callback signature can be silently swallowed with no visible error,
    # which happened during development. Calling tick() ourselves and
    # pumping the interactor with pl.update() removes that ambiguity.
    pl.show(auto_close=False, interactive_update=True)
    while not pl._closed:
        tick()
        pl.update()
        time.sleep(TICK_INTERVAL_MS / 1000.0)


if __name__ == "__main__":
    main()
