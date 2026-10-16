# Validation plan: bench protocol for the preliminary digital twin (Phase 11)

Status: **plan only; no hardware data exists yet**. Until the acceptance thresholds in section 7 are met on bench data, the twin is a *preliminary* physics-based model. Written so that someone with the motor, a bench supply, a scope or logger and a microcontroller can follow it without asking questions. Every expected value below comes from the twin (method_c, plus the alternatives of `docs/parameter_derivation.md`); the tools in `validation/` turn the logs into parameters and pass/fail tables.

The person running the rig reviews every step of this plan before use and has the authority to stop. The plan was written without access to the rig; the equipment it assumes is listed in section 9 so it can be corrected.

## 1. What is being validated

The model chain *12 V DC motor -> 180:1 gearbox -> output shaft -> arm/payload -> output-side quadrature encoder (9360 counts/rev) -> fixed PID at 1 kHz*, as implemented in `models/`, `controllers/` and checked in simulation by `tests/`. The motor validates the **methodology only**; nothing here supports claims about industrial (ABB-class) joints.

## 2. Open flags to resolve first (they decide which parameter set is plausible)

| Flag | Why it matters | Settled by |
|---|---|---|
| Datasheet title block says RMCS-3013, the project says RMCS-3070 | Which datasheet applies | Read the label on the actual motor; record it in the lab notebook |
| Is 7.5 A the locked-rotor current or a maximum rating? | Fixes R (1.6 ohm if it is stall) | Test T2 (locked rotor at low voltage) |
| Is 27.18 kg.cm the theoretical or a practical stall torque? | Gearbox efficiency 0.35 vs 0.80 (method_d vs d2) | Test T2 with a torque arm, T9 |
| 151 g.cm "base motor rated torque" equals 27.18 kg.cm / 180 exactly | Probably a reflected, not measured, value | Not used as data; T2/T3 give the real numbers |

## 3. Safety and setup

Complete and initial before **every** session (`hardware/safety/checklist.md` is generated from this list in the paper-preparation phase):

1. Bench supply current limit set **below the motor and driver ratings** (start at 2 A; never above 3 A for any locked-rotor step; 7.5 A only for a deliberate, supervised full-current test).
2. **Locked-rotor limit:** at most 2 s per test at 2 V or less, 60 s cool-down; never lock the rotor at 12 V.
3. Shaft guard fitted, arm free to move through its full range, **mechanical hard stops** at both ends of travel, nothing within reach of the arm.
4. Emergency stop in the motor supply path, tested at the start of the session. Firmware watchdog tested (halt the host: the motor must stop within 100 ms). Over-current and over-travel trips enabled.
5. Motor housing temperature probe fitted; stop at 60 C (or the datasheet limit if lower) and cool down for at least 10 min.
6. No high-gain or legacy-default test (Kp = 5, Ki = 20, Kd = 0.05 overshoots 42 % in simulation) unless the current limit and the hard stops are in place.
7. Wiring per `hardware/wiring/` (to be written): encoder 5 V supply, A/B channel pull-ups, common ground between supply, driver and microcontroller, logic levels checked before connecting the encoder to a 3.3 V board.
8. Firmware in safe-start state (motor disabled until a host handshake), soft start, and the same PID as the twin (1 kHz, derivative filter tau 10 ms, anti-windup by conditional integration, +-12 V saturation).

## 4. Tests

Common: sample at the control rate (1 kHz) or faster; log in the bench schema of section 6; randomise condition order within a session; record ambient and motor temperature, supply voltage and session id; repeat each measurement at least 10 times (5 for the long ones) and use the spread as the uncertainty. "Twin expects" values are method_c unless stated and are *predictions to be tested*, not targets.

### T1 Instrument and rig check (before any parameter test)
- **Purpose:** know the measurement uncertainty so later differences are not over-read.
- **Procedure:** (a) rotate the output shaft exactly one turn by hand from a marked position, 10 times, read counts: expect **9360 +- 1**. (b) Scope the control-loop timing pin: record `loop_dt_us` over 10 min; allow jitter below 100 us. (c) Current sensor: zero offset with the motor unpowered; gain against a reference meter with a resistor load (say 2 ohm at 4 V). (d) Voltage sense against a meter at 3 voltages. (e) Repeat one identical open-loop command 30 times and note the spread.
- **Measured:** counts per turn, timing histogram, sensor offset/gain, repeatability (coefficient of variation).
- **Twin expects:** 9360 counts per output revolution (13 Hall x 4 x 180 / 1 per datasheet).

### T2 Winding resistance and stall relationship (locked rotor, low voltage)
- **Purpose:** R, the stall current, and the output torque per ampere Kt*N*eta: the single most informative test (see `docs/parameter_derivation.md`).
- **Procedure:** lock the output shaft (clamp the arm against a force gauge or torque arm of known length). With the supply current-limited at 2 A, apply 0.5, 1.0 and 2.0 V for at most 2 s each; log current, voltage and the force on the arm. Optionally a 4-wire measurement of the winding at the motor terminals.
- **Measured:** `V`, `i` at steady state, force F at arm length L_arm; output torque = F*L_arm.
- **Extraction:** R = V/i (slope of V versus i over the three voltages, intercept = brush/contact drop); output torque per ampere `k_out = tau_out / i` = Kt*N*eta.
- **Twin expects:** R = 1.6 ohm (i = 0.625 A at 1 V, 1.25 A at 2 V). Torque per ampere: method_c 0.284 N.m/A (0.355 N.m at 2 V, about 3.6 kg.cm), method_d 0.355 N.m/A, method_d2 0.819 N.m/A. A measured value near 0.82 means the gearbox is efficient and 27.18 kg.cm is a practical rating; near 0.35 means a lossy gearbox.

### T3 No-load speed and current versus voltage
- **Purpose:** K = Ke (slope) and the friction current (intercept) -> Bm; decides the Ke/Kt question.
- **Procedure:** output free, motor unloaded. At 6 voltages from 2 to 12 V (current-limited supply), hold each for 3 s after the transient; log speed (from encoder counts over a 1 s window), voltage at the motor terminals and current. 10 repeats per voltage.
- **Extraction:** w_motor = N*w_out; fit w = (V - R*i)/Ke at each point -> Ke from the slope; no-load friction torque Kt*i0 = Bm*w + tau_c -> Bm from the current-versus-speed slope, tau_c from its intercept.
- **Twin expects (output shaft):** method_c 22 / 44 / 67 / 89 RPM at 3 / 6 / 9 / 12 V with 0.85 A at 12 V; method_d family 25 / 50 / 75 / 100 RPM with 0.80 A at 12 V (datasheet: 100 RPM output at 12 V).

### T4 Back-EMF constant (cross-check)
- **Purpose:** independent Ke.
- **Procedure:** spin the output shaft with a drill at a steady speed (or coast down from 6 V with the driver disconnected), read the open-circuit terminal voltage with the scope.
- **Extraction:** Ke = V_open / w_motor.
- **Twin expects:** Ke = 6.37 mV.s/rad (method_c) or 5.69 mV.s/rad (method_d family) versus Kt = 1.97 mV.s/rad (method_a/c): the SI identity Ke = Kt either holds or it does not.

### T5 Armature inductance
- **Purpose:** L (assumed 0; plausible 0.1-5 mH).
- **Procedure:** LCR meter at 1 kHz across the terminals with the rotor locked, or a voltage step on the locked rotor at 1 V with a fast scope capture of the current rise.
- **Extraction:** L from the LCR reading; or L = R*tau where tau is the 63 % rise time of the current.
- **Twin expects:** L = 0 (neglected). A measured L/R above 0.5 ms invalidates the L = 0 simplification at the 1 kHz loop.

### T6 Rotor inertia
- **Purpose:** Jm (estimated 5e-7 kg.m^2; the dominant uncertainty in the simulated sensitivity study).
- **Procedure:** free-run speed decay from 6 V with the supply switched to open circuit (or short-circuit braking), plus the same with a known disc of inertia J_add (a calibrated steel disc on the output shaft, J_out known from mass and radius). Log counts at 1 kHz.
- **Extraction:** mechanical time constant tau_m = J_total/(Bm + Kt*Ke/R); with and without the added inertia, tau_m(2)/tau_m(1) = (Jm + J_add/N^2)/Jm, which yields Jm. Use `validation/identify.py` with the added-inertia argument to fit all parameters jointly.
- **Twin expects:** tau_m = 56 ms for method_c (Jm 5e-7). With a 0.012 kg.m^2 disc on the output (0.5 kg at 15 cm) the reflected addition is 3.7e-7, about 74 % of Jm, enough to separate Kt from Jm.

### T7 Friction map
- **Purpose:** Bm, Coulomb tau_c, direction asymmetry.
- **Procedure:** steady-state speed versus current at low speed (0.5 to 20 RPM at the output) in both directions; 5 speeds per direction, 5 repeats.
- **Extraction:** Kt*i = tau_c*sign(w) + Bm*w -> intercept and slope per direction.
- **Twin expects:** tau_c = 0 and Bm = 1e-6 N.m.s/rad (method_c); method_d family Bm 2.4e-6.

### T8 Gearbox efficiency
- **Purpose:** eta (0.80 estimated; 0.35 under method_d).
- **Procedure:** with a known output torque (a calibrated mass on a lever arm, arm horizontal), compare the motor current at slow steady speed with the no-load current at the same speed.
- **Extraction:** eta = tau_out / (N*Kt*(i_loaded - i_noload)).
- **Twin expects:** 0.80 (method_c), 0.347 (method_d).

### T9 Backlash and encoder dead zone
- **Procedure:** command a slow reversing ramp (+-2 deg), find the output angle at which the motor-side motion reverses the output; or use a dial indicator on the arm with the motor shaft held.
- **Twin expects:** none (ideal gearbox). Report the measured dead zone in degrees.

### T10 Open-loop twin comparison
- **Procedure:** apply held-out PRBS voltage sequences (not used for fitting, amplitude +-6 V, hold 40 ms, 5 s long) and record angle and current.
- **Expected:** the twin driven by the measured voltage reproduces angle and current within the thresholds of section 7.

### T11 Closed-loop step responses (the final comparison)
- **Procedure:** with the firmware PID, step the target 0 -> 90 deg (and 0 -> 45, 0 -> 180) for the gain sets of the simulated sequence (low P 1.5/0/0; 15/0/0; 45/0/0; Tuned 15/0/0.3; P+I 15/20/0; PID 15/5/0.3), 10 repeats per condition, order randomised; add the arm and payload only after the bare-shaft results are in. Hard stops and the current limit in place.
- **Twin expects (bare shaft, method_c):** Tuned 1.73 % overshoot and 0.292 s settling; low P still 8 deg short at 2 s; 45/0/0 11.2 % overshoot; legacy gains 42 % (see `results/pid_test_sequence.md`).

## 5. Parameter identification method

`validation/identify.py` fits R, Ke, Kt, Jm, Bm (and tau_c if added) by output-error least squares: the measured terminal voltage drives a simulation of motor + gearbox and the residuals are the measured angle (counts) and current. Starting points from the YAML, bounds wide, three starts. **Identifiability is checked, not assumed** (Jacobian SVD):

- angle only: just two lumped quantities are determined, Kt/(R*Jm) and (Kt*Ke/R + Bm)/Jm, so no individual parameter is reported (Ke and Kt cannot be separated);
- angle + current: R, Ke, Jm/Kt and Bm/Kt are determined; Kt, Jm and Bm are not separately (a common scale cancels);
- a second run with a **known added output inertia** (T6) or a torque measurement (T2) resolves the scale, and then all five are determined (the synthetic tests recover them within 1 %).

Confidence intervals come from the Jacobian (linearised, white residuals assumed) and should be cross-checked by bootstrap over the 10 repeats; cross-validate on the held-out T10 sequences. Candidate parameter files are written to a separate YAML and never overwrite `config/motor_parameters.yaml`. Parameters changed only through this path, never by hand until the plot looks right.

## 6. Data format and logging

CSV in the project raw-log schema (`simulation/rawlog.py`, loader `validation/load_bench_csv.py`). Required columns: `t_s`, `v_applied_V` (alias `v_meas_V`, the voltage measured at the motor terminals) and `theta_counts` (output encoder) or `theta_deg`. Recommended: `i_A`, `target_deg`, `v_cmd_V`, `kp`, `ki`, `kd`, `temp_C`, `vsupply_V`, `loop_dt_us`, `sat_flag`, `encoder_raw`, `adc_raw_i`, `adc_raw_v`, `run_id`, `experiment_id`, `session_id`, `unit_id`, `method`.

- File naming: `<experiment>_<unit>_<session>_<yyyymmddThhmmss>.csv`, one file per session, runs distinguished by `run_id`.
- Raw files are read-only after capture; the SHA-256 goes in the session notebook entry (`meta.json` per run: commit, firmware hash, operator, ambient temperature, anomalies).
- The loader runs automatic sanity checks (time order, gaps, NaN, voltage/current ranges, saturation fraction, loop jitter); a run that fails an *error* check is repeated, not edited.
- Notebook template: date/time, session id, operator, unit id, ambient and housing temperature (start/end), supply voltage and limit, firmware hash, run-order file, safety checklist initials, calibrations (pass/fail), runs completed/aborted, anomalies, deviations.

## 7. Acceptance thresholds for the word "validated"

Proposed values (they live in `config/motor_parameters.yaml` under `validation_thresholds` and are applied by `validation/compare.py`). They must be agreed before the confirmatory runs and not tuned afterwards.

| Quantity | Threshold | Reasoning |
|---|---|---|
| Angle NRMSE (RMSE / peak-to-peak) | <= 5 % | A step response that deviates by more than 5 % of the step is visibly different; above the measurement uncertainty (about 0.04 deg) by two orders of magnitude |
| Angle FIT | >= 90 % | Standard system-identification fit measure; 90 % leaves about a third of the residual energy relative to a mean-only model |
| Overshoot difference | <= 3 percentage points | Overshoot varies by 3-10 points across the plausible parameter ranges (see `results/sensitivity/`); a tighter bound than the uncertainty it is meant to test |
| Settling-time difference | <= max(15 %, 50 ms) | Settling is sensitive to ringing and noise at the 2 % band |
| Rise-time difference | <= 10 % | Rise time is saturation-limited and robust, so a tighter bound is justified |
| Steady-state error difference | <= 0.5 deg | A few encoder counts plus friction dead band |
| Current NRMSE | <= 10 % | Current sensing is noisier than angle |
| Peak current difference | <= 15 % | Sensor accuracy plus supply sag |
| Residual whiteness (Ljung-Box) | reported, not a criterion | A structured residual shows missing dynamics even when the thresholds pass |

**Scope of the claim.** The twin may be called validated only for the quantities and conditions that pass, with the thresholds and the numbers stated (for example "bare shaft, 90 deg step, Tuned gains, unit 1"). Passing on one unit does not validate other units; the between-unit spread must be reported.

**If a threshold fails:** (1) check the instrument first (T1, timing, sensor calibration); (2) look at the residual structure (Ljung-Box, residual-input cross-correlation) to see what dynamics are missing (friction, delay, supply sag, backlash); (3) add that effect to the model through the identification path, label it, and re-run on *new* data; (4) never loosen a threshold after seeing the data; record any change as a deviation.

## 8. Report template

`validation/report_template.md`: one filled copy per experiment family, with the comparison tables produced by `validation/compare.py`.

## 9. Assumptions about the equipment (please correct)

The plan assumes: a current-limited bench supply (2-3 A range at least), a scope or logic analyser (loop timing, back-EMF), an LCR meter, calibrated masses and a steel disc of known inertia, a force gauge or torque arm, a motor-housing temperature probe, a microcontroller with hardware quadrature decoding and a 1 kHz timer, an H-bridge driver with a current sensor or a shunt, the motor mounted on a rigid clamp with a shaft guard and hard stops, and a host PC that logs over USB-serial at 1 kHz or buffers on the board. Open questions: which driver and PWM frequency (its voltage drop and dead time matter for the twin), how many motor units are available, and whether a second encoder or camera can serve as an independent angle reference.
