# Digital Twin RL-PID — Robotic Joint

A physics-based digital twin of a single robotic revolute joint — DC motor →
gearbox → joint → encoder → PID — validated first on a low-cost DC geared
motor prototype, with reinforcement-learning-based adaptive PID gain tuning
layered on top once the fixed-gain baseline and digital twin are validated.
Long-term target is an ABB industrial robot arm joint; the prototype motor
validates methodology only.

**Read [`master_prompt_digital_twin_rl_pid.md`](master_prompt_digital_twin_rl_pid.md)
before contributing.** It's the canonical project spec — architecture,
hard engineering rules (§20), and the phase order (§21) that must not be
skipped. This README is an onboarding summary, not a replacement for it.
See [`FILES.md`](FILES.md) for a description of what every tracked file
in the repo actually is and does.

## Software stack

Python 3.x, [Gymnasium](https://gymnasium.farama.org/), NumPy, SciPy,
Pandas, Matplotlib, [PyBullet](https://pybullet.org/),
[Stable-Baselines3](https://stable-baselines3.readthedocs.io/) (+ PyTorch).
Fixed per master prompt §1 — don't swap in MuJoCo/MATLAB/etc. without
justifying it in a PR. CAD→mesh visualization additionally uses trimesh,
cascadio, and pyvista (VTK); its interactive demo's window/controls use
pyvistaqt + PyQt5 — see [Known issues](#known-issues-platform-notes) below
for a PyBullet installation caveat on some platforms.

## Current status

**Phases 5–9 minimally combined** (gearbox, bare output shaft with no arm
yet, encoder, fixed PID, closed-loop digital twin simulation), on top of
**Phase 4** (DC motor ODE). Phase 10 (CAD visualization) brought forward in
minimal, visualization-only form — see the demo section below. **Not yet
implemented:** a real arm/payload (Phase 6 proper — needs physical specs),
PyBullet-integrated physics (Phase 10's actual physics engine — the CAD demo
is render-only, no PyBullet), Gymnasium environment / RL (Phase 13+). Full
parameter provenance and open flags: [`datasheet/parameter_table.md`](datasheet/parameter_table.md).

## Folder structure

```
DigitalTwin_RL_PID/
├── README.md
├── master_prompt_digital_twin_rl_pid.md   # canonical spec — read first
├── requirements.txt
├── data/                  # planned, not created yet
├── datasheet/              # source datasheet PDF + parameter_table.md
├── cad/                    # reference CAD (see caveat below) + converted mesh
├── config/
│   └── motor_parameters.yaml   # all parameters, provenance-tagged, no hard-coding
├── models/                 # dc_motor, gearbox, joint, encoder, digital_twin, units
├── controllers/
│   └── pid.py               # fixed-gain PID: saturation, anti-windup, filtered D
├── simulation/              # phase-by-phase check scripts + demos (see below)
├── pybullet/                # planned, not created yet — Phase 10 proper
├── environments/            # planned, not created yet — Phase 13, Gymnasium env
├── rl/                      # planned, not created yet — Phase 14+
├── validation/              # planned, not created yet — Phase 11
├── results/                 # generated plots/data — gitignored, not source of truth
└── reference/
    └── legacy_demo/          # pid_demo.pdf/.sch/.ino — see note below
```

`cad/` contains the JGB37-520 reference CAD — a **similar but not verified
identical** motor to the project's actual RMCS-3013/3070, used for geometry
reference only (master prompt §3). Don't assume its dimensions/mass without
checking the provenance tags in `datasheet/parameter_table.md`.

`reference/legacy_demo/` holds the original Arduino Pro Mini + L293D +
potentiometer-tuned PID demo board (the YouTube video that inspired this
project). **Historical/conceptual context only** — none of its component
choices, especially the L293D driver, are a spec for this project. The real
motor driver for eventual hardware deployment has not been chosen yet.

## Setup

```bash
git clone <REPO_URL>
cd DigitalTwin_RL_PID
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Run from the repo root with it on `PYTHONPATH`:

```bash
PYTHONPATH=. python simulation/simulate_motor.py          # Phase 4 sanity check
PYTHONPATH=. python simulation/interactive_pid_twin.py     # matplotlib sliders, line plots
PYTHONPATH=. python simulation/cad_pid_visualizer.py       # 3D CAD viewer, live PID, presets
```

`interactive_pid_twin.py` and `cad_pid_visualizer.py` also bootstrap the
repo root onto `sys.path` themselves at import time, so you can equally just
open either file in an editor (VS Code's Run button, `F5`, etc.) and run it
directly — no `PYTHONPATH` needed either way. `cad_pid_visualizer.py`
additionally needs a Qt binding installed (`pip install PyQt5`, now in
`requirements.txt`) — `pyvistaqt`/`QtPy` only provide the glue, not a
binding themselves.

### CAD 3D PID demo (`simulation/cad_pid_visualizer.py`)

The most complete demo right now: a real Qt window (pyvistaqt + PyQt5, not
raw pyvista overlay widgets — those had no layout engine and kept
overlapping each other/the 3D view as controls were added) split into a 3D
view on the left, and embedded matplotlib graphs + a controls panel on the
right. The 3D view renders the JGB37-520 CAD (motor housing static, output
shaft + coupler rotating) with a rod+ball **arm** rigidly attached to the
shaft so overshoot/oscillation/damping are actually visible; the camera
re-fits itself to the arm's *current* length every time it changes
(startup included), so it stays framed reasonably tight and the arm can
never be lengthened out of view. The three graphs (angle, error,
control voltage) autoscale to each run's actual data, and the angle graph
carries two live markers: a dot tracking position along the current PID run
(when one is playing), and a dashed line tracking the shaft's actual current
angle at all times (including during the idle spin demo, where there's no
PID run to show a dot for).

The arm's **length and weight are adjustable** (drag the slider or type an
exact value into the box next to it — every control here supports both) and
are not purely cosmetic: both feed extra inertia (reflected through the
gearbox, `m·L²/ratio²`) into the physics, so a heavier/longer arm visibly
slows the PID response. Gravity sag/torque is *not* modeled (the arm's
rotation plane is unspecified) — see the file's docstring for the exact
assumption. Kp/Ki/Kd stay on screen; arm length/weight and the idle
spin-demo speed live under a collapsed **"Arm / spin settings"** panel
(click to expand) so they don't take up space when you're not using them.

Two toggle buttons: **Spin (Demo)** — 0↔180° idle sweep at the slider-set
speed, no physics, starts automatically on launch, and stops cleanly when
unchecked (a real bug in the old overlay-widget version — unchecking it used
to do nothing). **Run PID** — runs the closed-loop twin once using whatever
Kp/Ki/Kd (and current arm length/weight) the controls are set to at click
time, then live-replays it; also stops cleanly if unchecked mid-run, and
re-runs automatically if you nudge a gain or arm slider while it's playing.
Three **presets** (Sluggish / Oscillatory / Tuned) set gains and run
immediately, chosen by grid-searching the model (not guessed) — see the
file's docstring for the exact gains and measured metrics (measured at
default arm settings; they'll drift if the arm sliders are moved far from
default). UI text runs a size larger than Qt's small default (app font,
chart titles/labels/ticks, status readout) for on-screen readability.

## Known issues / platform notes

- **PyBullet**: in the fixed stack (§1) but has no prebuilt wheel for some
  Python/OS combinations (hit on Windows + Python 3.11 during development —
  needs MSVC Build Tools to build from source). If `pip install pybullet`
  fails for you, either install a Python version with a prebuilt wheel, use
  WSL/Linux, or install the build tools. Not required for anything built so
  far — the current CAD demo is render-only (pyvista/VTK), no PyBullet.
- The Ke/Kt/R motor-parameter derivation has a known, documented discrepancy
  between two derivation methods — see `datasheet/parameter_table.md` and
  `simulation/simulate_motor.py`'s output. Not a bug; both are carried
  forward with explicit confidence tags.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for branching model, commit
conventions, and the PR review checklist (config-driven parameters, no
hardcoding, no fabricated datasheet values, no skipped phases).
