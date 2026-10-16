"""G2.3: regression checks for the Qt CAD demo on a REAL display (not offscreen).

Offscreen Qt renders neither the 3D view nor text, so these run only when you opt in on a machine with a display:

    set DTRL_QT_GUI=1        (PowerShell: $env:DTRL_QT_GUI = "1")
    pytest tests/gui -q

They reproduce the section 8.7 checks of PROJECT_OVERVIEW.md against the demo that now goes through the shared
joint model (models/joint.py), and add the gravity checkbox / torque-margin line.
"""

import os
import sys
import time

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(os.environ.get("DTRL_QT_GUI") != "1", reason="set DTRL_QT_GUI=1 on a machine with a display")

QtWidgets = pytest.importorskip("PyQt5.QtWidgets")
pytest.importorskip("pyvistaqt")

from simulation.metrics import overshoot_pct, settling_time  # noqa: E402


def pump(app, ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()


@pytest.fixture(scope="module")
def win(cfg):
    import simulation.cad_pid_visualizer as v
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    w = v.MainWindow(cfg)
    w.resize(1500, 1000)
    w.show()
    w.app = app
    pump(app, 1500)
    yield w
    w.close()


def test_starts_in_spin_and_sweeps(win):
    assert win.mode == "spin"
    angles = []
    for _ in range(10):
        pump(win.app, 120)
        angles.append(win.actor.orientation[2])
    assert 0 <= min(angles) and max(angles) <= 180 and max(angles) - min(angles) > 5


def test_unchecking_spin_stops_it(win):
    win.spin_btn.setChecked(False)
    pump(win.app, 200)
    assert win.mode == "idle"


def test_tuned_preset_metrics_and_default_arm(win):
    win._apply_preset("tuned")
    pump(win.app, 300)
    t, y = np.array(win.run_t), np.array(win.run_theta)
    assert overshoot_pct(y, 90.0) == pytest.approx(1.76, abs=0.1)         # 1.8 % at the default 50 mm / 20 g arm
    assert settling_time(t, y, 90.0) == pytest.approx(0.292, abs=0.01)
    win.run_btn.setChecked(False)


def test_arm_physics_and_camera_refit(win):
    win.kp_ctrl.set_value(15); win.ki_ctrl.set_value(0); win.kd_ctrl.set_value(0.3)
    dists = []
    for L, M, os_, settle in [(50, 20, 1.76, 0.292), (120, 100, 2.56, 0.444)]:
        win.length_ctrl.set_value(L); win.mass_ctrl.set_value(M)
        win.run_btn.setChecked(True)
        pump(win.app, 300)
        t, y = np.array(win.run_t), np.array(win.run_theta)
        assert overshoot_pct(y, 90.0) == pytest.approx(os_, abs=0.1)
        assert settling_time(t, y, 90.0) == pytest.approx(settle, abs=0.01)
        dists.append(np.linalg.norm(win.plotter.camera.GetPosition()))
        win.run_btn.setChecked(False)
        pump(win.app, 100)
    assert dists[1] > 2.5 * dists[0]                                        # camera moved back when the arm grew


def test_gain_change_during_run_reruns(win):
    win.run_btn.setChecked(True)
    pump(win.app, 300)
    idx = win.run_idx
    win.kp_ctrl.set_value(45)
    pump(win.app, 100)
    assert win.run_idx < idx + 20 and "Kp=45.00" in win.status_label.text()
    win.run_btn.setChecked(False)


def test_gravity_checkbox_shows_margin_and_changes_response(win):
    win.length_ctrl.set_value(120); win.mass_ctrl.set_value(100)
    win.gravity_chk.setChecked(False)
    win.run_btn.setChecked(True)
    pump(win.app, 300)
    assert "torque margin" not in win.status_label.text()
    no_g = np.array(win.run_theta)
    win.gravity_chk.setChecked(True)
    pump(win.app, 300)
    text = win.status_label.text()
    assert "torque margin" in text and "upper bound" in text
    assert not np.allclose(no_g, np.array(win.run_theta))                  # gravity changed the simulated response
    win.run_btn.setChecked(False)
