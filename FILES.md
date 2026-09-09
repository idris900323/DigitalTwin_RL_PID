# File-by-file guide

What every tracked file in this repo is and what it does. Organized by
directory, in the order they matter for understanding the project. See
[`README.md`](README.md) for setup/run instructions and
[`master_prompt_digital_twin_rl_pid.md`](master_prompt_digital_twin_rl_pid.md)
for the governing spec.

## Repo root

| File | What it is |
|---|---|
| `master_prompt_digital_twin_rl_pid.md` | **Canonical project spec.** Software stack, hardware target, math model, folder structure, hard engineering rules (§20), and the 18-phase development order (§21) this project follows without skipping. Read this before contributing. |
| `README.md` | Onboarding doc: project summary, stack, folder structure, setup/run commands, current phase status. |
| `FILES.md` | This file. |
| `CONTRIBUTING.md` | Branching model (`feature/<name>` → PR → 1 review → merge), commit message convention, and the PR review checklist (no hardcoded params, no fabricated datasheet values, no skipped phases). |
| `LICENSE` | MIT license. |
| `.gitignore` | Excludes `__pycache__/`, venvs, OS/IDE junk, and heavy future RL run dirs (`runs/`, `wandb/`, etc). `results/` and the converted CAD `.glb` are deliberately **not** ignored — see the comments inside the file for why. |
| `requirements.txt` | Pinned versions for everything actually installed/used so far, plus the rest of the master prompt's fixed stack (`gymnasium`, `stable-baselines3`, `pandas`, `pybullet`) listed for later phases even though no code uses them yet. |

## `datasheet/` — source specs and derived parameters

| File | What it is |
|---|---|
| `RMCS-3013_RMCS-3070_datasheet.pdf` | The manufacturer datasheet PDF for the prototype motor (title block says "RMCS-3013"; project spec says "RMCS-3070" — same Rhino/Robokits product family, specs match exactly, flagged as a naming inconsistency not fully resolved). |
| `parameter_table.md` | Every motor parameter (voltage, torque, speed, CPR, R/L/Kt/Ke/J/B, mechanical dimensions), each tagged DATASHEET/CALCULATED/ESTIMATED/ASSUMED per master prompt §3/§11, with unit conversions shown explicitly and every known inconsistency flagged (e.g. the "151 g·cm base motor rated torque" figure that's numerically identical to a reflected value, not an independent measurement; the two conflicting Ke/Kt derivation methods). This is the single most important file for understanding what's real vs. estimated in this project. |

## `cad/` — 3D reference geometry

| File | What it is |
|---|---|
| `jgb37-520-1.snapshot.4_REFERENCE_NOT_VERIFIED_MATCH/` | The source CAD files (SolidWorks parts/assembly + STEP export) for a JGB37-520 geared DC motor — a **similar but not verified identical** motor to the project's actual RMCS-3013/3070 (per master prompt §3). Used for geometry reference only. Folder name is deliberately explicit about the unverified match. Contains: `JGB37-520.STEP` (the neutral-format file everything else derives from), `JGB37-520.SLDASM`/`.SLDPRT`/`.x_b` (native SolidWorks formats), `JGB37-520.JPG` (reference photo/render), `Description.txt` (original GrabCAD listing text). |
| `convert_step_to_glb.py` | Standalone script that regenerates `JGB37-520_converted.glb` from the source STEP file via `cascadio`. Run this if the source CAD ever changes. |
| `JGB37-520_converted.glb` | The converted mesh (per-part geometry) that `simulation/cad_pid_visualizer.py` actually loads and renders — committed directly since it's small (~500KB) and required for the demo to run without an extra conversion step. |

## `config/` — all tunable parameters, nothing hardcoded

| File | What it is |
|---|---|
| `motor_parameters.yaml` | Every physical/simulation parameter used by the code: supply voltage, gear ratio, encoder CPR, the two (soon three, incl. hybrid) electrical-parameter derivation scenarios, estimated inertia/friction placeholders, mechanical dimensions, PID default gains and slider ranges. Every value is commented with its provenance tag. Code reads from here — nothing physics-related is hardcoded in `.py` files. |

## `models/` — the physics

| File | What it is |
|---|---|
| `units.py` | SI unit conversion helpers (RPM↔rad/s, kg·cm/g·cm→N·m). Used everywhere a datasheet value enters the model, so conversions are explicit and traceable, never silent. |
| `dc_motor.py` | **Phase 4.** The DC motor's electrical + mechanical ODE (`V = R·i + L·di/dt + Ke·ω`, `J·dω/dt = Kt·i − B·ω − τ_load`), base-motor-side only — no gearbox/joint/encoder mixed in. Provides both a continuous solver (`simulate()`, via `scipy.integrate.solve_ivp`, for open-loop characterization) and a fixed-step discrete RK4 stepper (`step()`, for the closed-loop control simulation, since a real-time controller needs a fixed sample time). |
| `gearbox.py` | **Phase 5.** Ideal fixed-ratio gearbox (180:1) — converts motor-side speed/position to output-side, and reflects an output-side load torque back to the motor shaft. No backlash/compliance modeled (deliberately, per master prompt §7: "start simple"). |
| `joint.py` | **Phase 6, minimal.** The output shaft with **no arm/payload** — that data hasn't been provided yet. Carries zero external torque by default. Exists so the digital twin's data flow already has the right seam to add a real arm's inertia/friction/disturbance later without restructuring anything. |
| `encoder.py` | **Phase 7.** Quadrature encoder model at 9360 CPR (confirmed = 13 Hall sensors × 4 quadrature-decode × 180 gear ratio, exact arithmetic match to the datasheet). Reads the **output** shaft position (never the motor shaft — critical constraint from master prompt §2), with quantization and optional configurable noise. |
| `digital_twin.py` | **Phase 9.** The closed-loop orchestrator: wires encoder → PID → motor → gearbox → joint together and steps them all at a fixed `dt`. This is "the digital twin" as a single object — `DigitalTwin.step()` for one control-loop tick, `.run()` to simulate a whole trajectory. |

## `controllers/` — the PID

| File | What it is |
|---|---|
| `pid.py` | **Phase 8.** Fixed-gain PID controller: voltage output saturated to ±12V (physical supply limit), conditional-integration anti-windup, first-order filtered derivative term, fixed discrete sample time. |

## `simulation/` — runnable scripts and demos

| File | What it is |
|---|---|
| `simulate_motor.py` | **Phase 4 sanity check.** Non-interactive: simulates an open-loop 12V step on the base motor alone (no load), compares the resulting no-load speed against the datasheet's stated 18,000 RPM, prints the discrepancy, and saves a plot to `results/`. This is what caught the two conflicting Ke/Kt derivation methods. |
| `metrics.py` | Step-response performance metrics used everywhere else: rise time, overshoot %, settling time, steady-state error, RMSE. Shared so the same definitions are used for the demo, and later for the fixed-PID vs. RL-PID comparison table (Phase 16). |
| `interactive_pid_twin.py` | **Phases 5–9 demo, matplotlib version.** 2D line plots (angle, error, control voltage) with Kp/Ki/Kd sliders. The first working closed-loop demo, superseded in polish by the CAD version below but still useful as a simpler, faster-loading option. Self-bootstraps the repo root onto `sys.path`, so it can be run directly without `PYTHONPATH` set. |
| `cad_pid_visualizer.py` | **The main demo.** A Qt window (pyvistaqt + PyQt5 — real widgets in real layouts, not raw pyvista overlay widgets, which had no layout engine and kept colliding as controls were added) split into a 3D view and a graphs+controls panel. 3D view: JGB37-520 CAD via pyvista/VTK, motor housing static, output shaft + coupler rotating, with a rod+ball "arm" attached so overshoot/oscillation/damping are actually visible; camera re-fits itself to the arm's *current* length every time it changes (startup included), so it stays framed reasonably tight and the arm can never be lengthened out of view. Controls: Kp/Ki/Kd always visible; arm length and arm weight (both feed real extra inertia — `m·L²/ratio²` reflected through the gearbox — into the physics, not just the visual, though gravity sag is still not modeled) plus idle-spin speed live under a collapsed "Arm / spin settings" panel. Every control is a slider *and* a spinbox typing the same value keeps them in sync either way. Two toggle buttons: Spin (Demo, auto-starts, 0↔180° sweep at the slider-set speed, no physics, stops cleanly when unchecked) and Run PID (uses current gains/arm settings, live-replays, stops cleanly when unchecked, re-runs automatically if a gain/arm control changes mid-play); three preset buttons (Sluggish/Oscillatory/Tuned — gains found by grid search, not guessed, exact values and measured metrics in the file's docstring, measured at default arm settings). Three embedded matplotlib graphs (angle, error, control voltage) autoscale to each run's data; the angle graph shows both a dot tracking position along the current PID run and a dashed line tracking the shaft's actual current angle at all times (including during the spin demo, honestly — no error/voltage data exists for a non-PID sweep, so those two graphs don't get a live marker then). Self-bootstraps the repo root onto `sys.path`, so it can be run directly (e.g. an editor's Run button) without `PYTHONPATH` set — still needs a Qt binding installed (`pip install PyQt5`, now in `requirements.txt`). See the module docstring for why matplotlib-3D was tried and discarded for the CAD itself (330-560 ms/frame vs. pyvista's 0.14-4 ms/frame), and why the arm exists. |

## `reference/legacy_demo/` — historical inspiration, not project hardware

| File | What it is |
|---|---|
| `pid_demo.pdf`, `pid_demo.sch`, `pid_demo.ino` | The original Arduino Pro Mini + L293D + potentiometer-tuned analog PID demo board (from the YouTube video that inspired this project). **Not a spec for anything** — none of its component choices, especially the L293D motor driver, should be assumed for eventual hardware. The real motor driver has not been chosen yet. Kept only as conceptual context for "take the analog knob-tuned idea and make it digital/encoder-based/RL-adaptive." |

## `results/` — generated outputs (small ones tracked)

| File | What it is |
|---|---|
| `phase4_motor_step_response.png` | Output of `simulation/simulate_motor.py` — the Phase 4 open-loop step response plot showing the no-load-speed discrepancy. Regenerable by re-running that script; kept in the repo so it's visible without doing so. |

## Empty/placeholder directories (not yet populated)

`pybullet/`, `environments/`, `rl/`, `validation/`, `data/` exist in the folder structure (per master prompt §8/§33) but have no files yet — they're for Phase 10's actual PyBullet physics integration, Phase 13's Gymnasium environment, Phase 14+'s RL code, Phase 11's validation work, and raw experimental data, respectively. Git doesn't track empty directories, so they won't appear until something is added to them.
