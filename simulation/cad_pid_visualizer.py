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

UI TOOLKIT: built on pyvistaqt (QtInteractor) + PyQt5 + an embedded
matplotlib canvas, laid out in real Qt splitters/layouts -- NOT raw pyvista
overlay widgets (add_slider_widget/add_text) as an earlier version of this
file used. Overlay widgets are positioned in normalized viewport fractions
with no layout engine, so they silently collide with each other and with
the 3D content as more controls were added; there is also no typed-value
entry for them. Real Qt widgets give non-overlapping regions for free and
a QDoubleSpinBox next to every slider for typed input. pyvistaqt/PyQt5 are
already in requirements.txt.

CAD PROVENANCE REMINDER: this is the JGB37-520 reference CAD, NOT verified
to be the exact RMCS-3013/3070 model (\xa73). Its scale is broadly consistent
with the RMCS-3013 datasheet (shaft ~6mm dia here vs 6mm datasheet; gearbox
body ~37mm here vs 36mm datasheet) -- a plausible sanity check, not a
confirmed match.

VISUALIZATION ADDITIONS, NOT CAD/hardware features (\xa720: never hide
assumptions):
  - A rod + ball "arm" rigidly attached to the output shaft, with live
    length/weight controls (collapsed under "Arm / spin settings" by
    default -- expand to reveal). A plain round shaft spinning about its
    own axis of symmetry is visually indistinguishable frame to frame; the
    arm makes angular position (and therefore overshoot/oscillation/
    damping) actually visible. Its length/mass DO feed into the physics, as
    extra inertia reflected through the gearbox onto the motor
    (m*L^2/ratio^2) -- see the ARM_* constants below. What is still NOT
    modeled: gravity sag/torque (the arm's rotation plane -- horizontal vs
    vertical -- is unspecified) and joint-side friction/compliance from a
    real payload. The joint is still zero external torque, per the earlier
    "no arm yet, Phase 6 deferred" decision -- only its inertia is
    represented. The camera re-fits itself to the arm's CURRENT length every
    time it changes (startup included), so it's always framed reasonably
    tight while the arm can never be lengthened out of view.
  - The idle "Spin (Demo)" mode sweeps 0<->180 degrees (a servo-like wag,
    speed adjustable) instead of spinning continuously, matching the
    eventual bounded-joint framing. It is still not physics -- constant
    angular rate, no PID, no error/voltage data exists for it. The angle
    chart still shows a live dashed marker for the shaft's *current* angle
    in this mode (honest -- it's a real, known quantity); the error/voltage
    charts are not touched (there's nothing true to show there) and stay
    frozen on the last real PID run.

PID preset buttons use gains that were actually simulated and measured
against this model (not guessed) -- see the chat for the grid search:
  - Sluggish (low P):   Kp=1.5, Ki=0,  Kd=0    -- doesn't fully reach the
    target within the demo window (still ~8deg short at t=2s).
  - Oscillatory (high P): Kp=45, Ki=0, Kd=0    -- ~11% overshoot, one clear
    overshoot-and-settle cycle. Overshoot plateaus near 11% even at higher
    Kp/Ki because the +-12V voltage saturation dominates the transient once
    gains are large -- a genuine model finding, not a demo limitation
    papered over. Measured at default arm settings (see above); values
    drift if the arm sliders are moved far from default.
  - Tuned (damped):     Kp=15, Ki=0, Kd=0.3    -- ~1.7% overshoot, settles
    in ~0.29s. Found by grid search over the same model, not asserted.

Run: just open this file and hit Run (VS Code's play button, F5, etc.) --
no PYTHONPATH setup needed, see the sys.path bootstrap below. Equivalent
from a terminal: PYTHONPATH=. python simulation/cad_pid_visualizer.py
Needs a Qt binding installed (e.g. `pip install PyQt5`) in addition to
requirements.txt's pyvistaqt -- pyvistaqt/QtPy only provide the glue, not
a binding themselves.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # lets `python simulation/this_file.py` find controllers/models/simulation

import math

import matplotlib
import numpy as np
import pyvista as pv
import trimesh
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtWidgets
from pyvistaqt import QtInteractor

from simulation.interactive_pid_twin import build_twin, load_config
from simulation.metrics import overshoot_pct, rise_time, settling_time, steady_state_error

matplotlib.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "legend.fontsize": 9.5,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
})

GLB_PATH = ROOT / "cad" / "JGB37-520_converted.glb"

ROTATING_PART_KEYWORDS = ("MOTOR SHAFT", "SHAFT COUPLER")
PLAYBACK_STRIDE = 5              # 2000 sim steps -> 400 playback frames
TICK_INTERVAL_MS = 25
ARM_RADIUS_M = 0.0015              # rod thickness, not user-adjustable

# Arm length/weight are user-adjustable via the "Arm / spin settings" panel.
# They are NOT purely cosmetic: length and mass feed back into the physics
# as extra inertia reflected through the gearbox (J_extra = m*L^2/ratio^2)
# -- a real, physically-grounded effect (a heavier/longer arm is harder to
# accelerate, so the PID response visibly slows). NOT modeled: gravity
# sag/torque -- that would need the arm's rotation plane (horizontal vs
# vertical), which is unspecified (see module docstring's "never hide
# assumptions"). The preset numbers in PRESETS above were measured at the
# default arm settings, where this extra inertia is negligible (<1% of the
# base motor inertia); they will drift if the arm sliders are moved far
# from default.
ARM_LENGTH_DEFAULT_M = 0.05
ARM_LENGTH_MIN_M = 0.02
ARM_LENGTH_MAX_M = 0.12
ARM_MASS_DEFAULT_KG = 0.02
ARM_MASS_MIN_KG = 0.0
ARM_MASS_MAX_KG = 0.10
ARM_WEIGHT_RADIUS_BASE_M = 0.006   # visual ball radius at ARM_MASS_DEFAULT_KG

SPIN_SPEED_DEFAULT_DPS = 90.0      # idle demo sweep rate, deg/s
SPIN_SPEED_MIN_DPS = 15.0
SPIN_SPEED_MAX_DPS = 360.0

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


def arm_weight_radius_m(mass_kg: float) -> float:
    """Visual ball radius scales with mass^(1/3) (constant-density sphere)."""
    if mass_kg <= 0.0:
        return 0.001
    return ARM_WEIGHT_RADIUS_BASE_M * (mass_kg / ARM_MASS_DEFAULT_KG) ** (1.0 / 3.0)


def make_arm(rotating_bounds, length_m: float, mass_kg: float):
    """Rod + weight. Length/mass are visual AND (see module docstring) feed
    extra reflected inertia into the physics -- not purely cosmetic."""
    xmin, xmax, ymin, ymax, zmin, zmax = rotating_bounds
    tip_z = zmax * 0.85
    radius = arm_weight_radius_m(mass_kg)
    rod = pv.Cylinder(center=(length_m / 2, 0.0, tip_z), direction=(1, 0, 0),
                       radius=ARM_RADIUS_M, height=length_m)
    weight = pv.Sphere(radius=radius, center=(length_m, 0.0, tip_z))
    return rod.merge(weight)


def current_view_bounds(static_mesh, rotating_mesh, arm_length_m):
    """Camera-framing bounds that include the arm at its CURRENT length
    swept through a full circle (it only actually sweeps 0-180deg, but
    framing for the full circle is simpler and just as correct). Called
    again every time the length changes, so the view stays reasonably
    tight instead of being framed once for the max possible length."""
    sxmin, sxmax, symin, symax, szmin, szmax = static_mesh.bounds
    rxmin, rxmax, rymin, rymax, rzmin, rzmax = rotating_mesh.bounds
    r = arm_length_m
    return (
        min(sxmin, rxmin, -r), max(sxmax, rxmax, r),
        min(symin, rymin, -r), max(symax, rymax, r),
        min(szmin, rzmin), max(szmax, rzmax),
    )


class SliderSpin(QtWidgets.QWidget):
    """A slider + spinbox pair for one numeric parameter, kept in sync --
    lets the value be dragged OR typed directly (master prompt request)."""

    valueChanged = QtCore.pyqtSignal(float)

    def __init__(self, label, minv, maxv, value, decimals=2, step=None, suffix="", parent=None):
        super().__init__(parent)
        self._scale = 10 ** decimals
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(8)
        name = QtWidgets.QLabel(label)
        name.setFixedWidth(110)
        layout.addWidget(name, 0)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(int(round(minv * self._scale)))
        self.slider.setMaximum(int(round(maxv * self._scale)))
        self.slider.setValue(int(round(value * self._scale)))
        self.slider.setMinimumHeight(24)
        layout.addWidget(self.slider, 1)

        self.spin = QtWidgets.QDoubleSpinBox()
        self.spin.setDecimals(decimals)
        self.spin.setRange(minv, maxv)
        self.spin.setSingleStep(step if step is not None else 10 ** -decimals)
        self.spin.setSuffix(suffix)
        self.spin.setValue(value)
        self.spin.setFixedWidth(105)
        self.spin.setMinimumHeight(26)
        layout.addWidget(self.spin, 0)

        self._guard = False
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

    def _from_slider(self, ivalue):
        if self._guard:
            return
        self._guard = True
        v = ivalue / self._scale
        self.spin.setValue(v)
        self._guard = False
        self.valueChanged.emit(v)

    def _from_spin(self, v):
        if self._guard:
            return
        self._guard = True
        self.slider.setValue(int(round(v * self._scale)))
        self._guard = False
        self.valueChanged.emit(v)

    def value(self) -> float:
        return self.spin.value()

    def set_value(self, v: float):
        self.spin.setValue(v)  # cascades to the slider and emits valueChanged


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg):
        super().__init__()
        self.setWindowTitle("Digital Twin -- CAD PID demo")
        self.resize(1600, 900)

        self.cfg = cfg
        self.dt = cfg["simulation"]["control_loop_dt_s"]
        self.duration = cfg["simulation"]["run_duration_s"]
        self.n_steps = int(self.duration / self.dt)
        self.theta_ref = math.radians(cfg["simulation"]["theta_ref_default_deg"])
        self.ref_deg = math.degrees(self.theta_ref)
        d = cfg["pid_defaults"]

        self.mode = "idle"
        self.sweep_deg = 0.0
        self.spin_dps = SPIN_SPEED_DEFAULT_DPS
        self.arm_length_m = ARM_LENGTH_DEFAULT_M
        self.arm_mass_kg = ARM_MASS_DEFAULT_KG
        self.run_t = self.run_theta = self.run_err = self.run_V = None
        self.run_idx = 0

        self._build_3d_view()
        self._build_charts()
        self._build_controls(d)
        self._assemble_layout()

        self._do_run()          # populate the charts with a real run first...
        self.spin_btn.setChecked(True)  # ...then auto-start the idle sweep

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(TICK_INTERVAL_MS)

    # --- setup -----------------------------------------------------
    def _build_3d_view(self):
        self.static_mesh, self.rotating_mesh = load_cad_parts()
        self.arm_mesh = make_arm(self.rotating_mesh.bounds, self.arm_length_m, self.arm_mass_kg)

        self.plotter = QtInteractor(self)
        self.plotter.set_background("white")
        self.plotter.add_mesh(self.static_mesh, color="#b5b5b5", smooth_shading=True, specular=0.4, specular_power=15)
        self.actor = self.plotter.add_mesh(self.rotating_mesh, color="#d95f02", smooth_shading=True,
                                            specular=0.6, specular_power=20)
        # Kept as a separate actor (not merged into rotating_mesh) so its
        # geometry can be swapped live when length/weight change; it shares
        # `actor`'s orientation every frame so the two rotate together.
        self.arm_actor = self.plotter.add_mesh(self.arm_mesh, color="#c44e02", smooth_shading=True,
                                                 specular=0.6, specular_power=20)
        self.plotter.add_axes()
        self.plotter.view_isometric()
        self.plotter.camera.azimuth += 25
        self._refit_camera()

    def _refit_camera(self):
        bounds = current_view_bounds(self.static_mesh, self.rotating_mesh, self.arm_length_m)
        self.plotter.reset_camera(bounds=bounds)

    def _build_charts(self):
        self.fig = Figure()
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.ax_angle, self.ax_err, self.ax_v = self.fig.subplots(3, 1, sharex=True)
        self.fig.subplots_adjust(hspace=0.45, left=0.14, right=0.97, top=0.94, bottom=0.08)

        t0 = np.linspace(0, self.duration, self.n_steps)

        (self.line_angle,) = self.ax_angle.plot(t0, np.zeros_like(t0), color="#1f77b4", label="theta_out")
        self.ax_angle.axhline(self.ref_deg, color="gray", linestyle="--", linewidth=1, label="reference")
        (self.cursor_angle,) = self.ax_angle.plot([], [], "o", color="red", markersize=6, label="_nolegend_")
        (self.live_angle_line,) = self.ax_angle.plot(
            [0, self.duration], [0, 0], color="#ff7f0e", linewidth=1.5, alpha=0.85, label="current shaft angle")
        self.ax_angle.set_ylabel("angle [deg]")
        self.ax_angle.set_title("Output angle")
        self.ax_angle.legend(loc="lower right", fontsize=7)

        (self.line_err,) = self.ax_err.plot(t0, np.zeros_like(t0), color="#d62728")
        (self.cursor_err,) = self.ax_err.plot([], [], "o", color="black", markersize=6)
        self.ax_err.axhline(0.0, color="gray", linewidth=0.5)
        self.ax_err.set_ylabel("error [deg]")
        self.ax_err.set_title("Tracking error")

        V_rated = self.cfg["supply"]["V_rated"]
        (self.line_v,) = self.ax_v.plot(t0, np.zeros_like(t0), color="#2ca02c")
        (self.cursor_v,) = self.ax_v.plot([], [], "o", color="black", markersize=6)
        self.ax_v.axhline(V_rated, color="red", linestyle=":", linewidth=0.8)
        self.ax_v.axhline(-V_rated, color="red", linestyle=":", linewidth=0.8)
        self.ax_v.set_ylim(-V_rated - 1, V_rated + 1)
        self.ax_v.set_ylabel("V_cmd [V]")
        self.ax_v.set_xlabel("t [s]")
        self.ax_v.set_title("Control voltage")

        for ax in (self.ax_angle, self.ax_err, self.ax_v):
            ax.set_xlim(0, self.duration)

    def _build_controls(self, d):
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        self.status_label = QtWidgets.QLabel("Mode: idle")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-family: Consolas, monospace; font-size: 12pt; padding: 4px;")
        layout.addWidget(self.status_label)

        gains_box = QtWidgets.QGroupBox("PID gains")
        gains_layout = QtWidgets.QVBoxLayout(gains_box)
        self.kp_ctrl = SliderSpin("Kp", 0.0, d["Kp_max"], d["Kp"], decimals=2)
        self.ki_ctrl = SliderSpin("Ki", 0.0, d["Ki_max"], d["Ki"], decimals=2)
        self.kd_ctrl = SliderSpin("Kd", 0.0, d["Kd_max"], d["Kd"], decimals=3, step=0.001)
        for w in (self.kp_ctrl, self.ki_ctrl, self.kd_ctrl):
            gains_layout.addWidget(w)
            w.valueChanged.connect(self._on_gain_changed)
        layout.addWidget(gains_box)

        self.arm_toggle = QtWidgets.QPushButton("▸ Arm / spin settings")
        self.arm_toggle.setCheckable(True)
        self.arm_toggle.setMinimumHeight(30)
        layout.addWidget(self.arm_toggle)

        arm_box = QtWidgets.QGroupBox()
        arm_layout = QtWidgets.QVBoxLayout(arm_box)
        self.length_ctrl = SliderSpin("Arm length", ARM_LENGTH_MIN_M * 1000, ARM_LENGTH_MAX_M * 1000,
                                       ARM_LENGTH_DEFAULT_M * 1000, decimals=0, suffix=" mm")
        self.mass_ctrl = SliderSpin("Arm weight", ARM_MASS_MIN_KG * 1000, ARM_MASS_MAX_KG * 1000,
                                     ARM_MASS_DEFAULT_KG * 1000, decimals=0, suffix=" g")
        self.speed_ctrl = SliderSpin("Spin speed", SPIN_SPEED_MIN_DPS, SPIN_SPEED_MAX_DPS,
                                      SPIN_SPEED_DEFAULT_DPS, decimals=0, suffix=" deg/s")
        for w in (self.length_ctrl, self.mass_ctrl, self.speed_ctrl):
            arm_layout.addWidget(w)
        self.length_ctrl.valueChanged.connect(self._on_arm_changed)
        self.mass_ctrl.valueChanged.connect(self._on_arm_changed)
        self.speed_ctrl.valueChanged.connect(self._on_speed_changed)
        arm_box.setVisible(False)
        self.arm_toggle.toggled.connect(lambda checked: (
            arm_box.setVisible(checked),
            self.arm_toggle.setText(("▾" if checked else "▸") + " Arm / spin settings"),
        ))
        layout.addWidget(arm_box)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        self.spin_btn = QtWidgets.QPushButton("Spin (Demo)")
        self.spin_btn.setCheckable(True)
        self.run_btn = QtWidgets.QPushButton("Run PID")
        self.run_btn.setCheckable(True)
        for b in (self.spin_btn, self.run_btn):
            b.setMinimumHeight(34)
        btn_row.addWidget(self.spin_btn)
        btn_row.addWidget(self.run_btn)
        layout.addLayout(btn_row)
        self.spin_btn.toggled.connect(self._on_spin_toggled)
        self.run_btn.toggled.connect(self._on_run_toggled)

        preset_label = QtWidgets.QLabel("Presets:")
        layout.addWidget(preset_label)
        preset_row = QtWidgets.QHBoxLayout()
        preset_row.setSpacing(8)
        for name, label in (("sluggish", "Sluggish"), ("oscillatory", "Oscillatory"), ("tuned", "Tuned")):
            b = QtWidgets.QPushButton(label)
            b.setMinimumHeight(30)
            b.clicked.connect(lambda _checked=False, n=name: self._apply_preset(n))
            preset_row.addWidget(b)
        layout.addLayout(preset_row)

        layout.addStretch(1)
        self.controls_panel = panel

    def _assemble_layout(self):
        right = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        right.addWidget(self.canvas)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.controls_panel)
        right.addWidget(scroll)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(self.plotter)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.setCentralWidget(splitter)

    # --- control callbacks -------------------------------------------
    def _on_gain_changed(self, _v=None):
        if self.mode == "run":
            self._do_run()

    def _on_arm_changed(self, _v=None):
        self.arm_length_m = self.length_ctrl.value() / 1000.0
        self.arm_mass_kg = self.mass_ctrl.value() / 1000.0
        new_mesh = make_arm(self.rotating_mesh.bounds, self.arm_length_m, self.arm_mass_kg)
        self.arm_mesh.copy_from(new_mesh)
        self._refit_camera()
        self.plotter.render()
        if self.mode == "run":
            self._do_run()

    def _on_speed_changed(self, v):
        self.spin_dps = v

    def _apply_preset(self, name):
        gains = PRESETS[name]
        self.kp_ctrl.set_value(gains["Kp"])
        self.ki_ctrl.set_value(gains["Ki"])
        self.kd_ctrl.set_value(gains["Kd"])
        self._do_run()

    def _on_spin_toggled(self, checked):
        if checked:
            self.run_btn.blockSignals(True)
            self.run_btn.setChecked(False)
            self.run_btn.blockSignals(False)
            self.mode = "spin"
            self.sweep_deg = 0.0
        elif self.mode == "spin":
            self.mode = "idle"
            self.status_label.setText("Mode: idle -- click a button")

    def _on_run_toggled(self, checked):
        if checked:
            self.spin_btn.blockSignals(True)
            self.spin_btn.setChecked(False)
            self.spin_btn.blockSignals(False)
            self._do_run()
        elif self.mode == "run":
            self.mode = "idle"
            self.status_label.setText("Mode: idle -- click a button")

    # --- simulate + push a run into the charts/animation state -------
    def _do_run(self):
        ratio = self.cfg["gearbox"]["ratio"]
        extra_Jm = self.arm_mass_kg * self.arm_length_m ** 2 / (ratio ** 2)
        Kp, Ki, Kd = self.kp_ctrl.value(), self.ki_ctrl.value(), self.kd_ctrl.value()
        twin = build_twin(self.cfg, Kp, Ki, Kd, extra_Jm_kgm2=extra_Jm)
        log = twin.run(self.theta_ref, self.n_steps)
        t = log["t"]
        theta = np.degrees(log["theta_out"])
        err = np.degrees(log["error"])
        V = log["V_cmd"]

        self.line_angle.set_data(t, theta)
        self.line_err.set_data(t, err)
        self.line_v.set_data(t, V)

        # Autoscale to this run's actual data instead of a fixed guess -- a
        # fixed +-30deg error range used to clip off-chart for e.g. the
        # ~90deg initial error of this demo's default step reference.
        self.ax_angle.set_ylim(min(0.0, float(theta.min())) - 10, max(self.ref_deg, float(theta.max())) + 10)
        self.ax_err.set_ylim(min(0.0, float(err.min())) - 10, float(err.max()) + 10)

        rt = rise_time(t, theta, self.ref_deg)
        os_ = overshoot_pct(theta, self.ref_deg)
        st = settling_time(t, theta, self.ref_deg)
        sse = steady_state_error(theta, self.ref_deg)
        self.status_label.setText(
            f"Kp={Kp:.2f} Ki={Ki:.2f} Kd={Kd:.3f}  |  arm={self.arm_length_m*1000:.0f}mm {self.arm_mass_kg*1000:.0f}g\n"
            f"rise={rt:.2f}s  overshoot={os_:.1f}%  settle={st:.2f}s  sse={sse:.2f}deg"
        )
        self.canvas.draw_idle()

        self.run_t, self.run_theta, self.run_err, self.run_V = t, theta, err, V
        self.run_idx = 0
        self.mode = "run"
        self.run_btn.blockSignals(True)
        self.run_btn.setChecked(True)
        self.run_btn.blockSignals(False)
        self.spin_btn.blockSignals(True)
        self.spin_btn.setChecked(False)
        self.spin_btn.blockSignals(False)

    # --- animation tick ------------------------------------------------
    def _tick(self):
        if self.mode == "spin":
            self.sweep_deg = (self.sweep_deg + self.spin_dps * TICK_INTERVAL_MS / 1000.0) % 360.0
            triangle = 1.0 - abs(2.0 * (self.sweep_deg / 360.0) - 1.0)  # 0->1->0
            angle_deg = 180.0 * triangle
            self.actor.orientation = (0.0, 0.0, angle_deg)
            self.arm_actor.orientation = (0.0, 0.0, angle_deg)
            self.live_angle_line.set_ydata([angle_deg, angle_deg])
            self.canvas.draw_idle()
            self.plotter.render()
        elif self.mode == "run":
            i = self.run_idx
            if i >= len(self.run_t):
                self.mode = "idle"
                self.run_btn.blockSignals(True)
                self.run_btn.setChecked(False)
                self.run_btn.blockSignals(False)
                return
            angle = self.run_theta[i]
            self.actor.orientation = (0.0, 0.0, angle)
            self.arm_actor.orientation = (0.0, 0.0, angle)
            t_i = self.run_t[i]
            self.cursor_angle.set_data([t_i], [angle])
            self.cursor_err.set_data([t_i], [self.run_err[i]])
            self.cursor_v.set_data([t_i], [self.run_V[i]])
            self.live_angle_line.set_ydata([angle, angle])
            self.canvas.draw_idle()
            self.plotter.render()
            self.run_idx += PLAYBACK_STRIDE


def main():
    cfg = load_config()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    font = app.font()
    font.setPointSizeF(10.5)
    app.setFont(font)
    window = MainWindow(cfg)
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
