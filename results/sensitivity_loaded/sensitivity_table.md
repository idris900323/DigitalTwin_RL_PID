# Sensitivity analysis (preliminary twin, simulated)

Tuned gains (15.0, 0.0, 0.3), 90 deg step, gravity-loaded arm (1 kg x 10 cm), parameter set `method_c`, seed 0, Morris r = 30. Ranges come from `sensitivity_ranges` in the YAML (datasheet +-5 %, calculated +-20 %, assumed +-50 %, Jm/Bm x/ divided by 3, L 0.1-5 mH, delay 0-3 samples). Nothing here has been validated on hardware.

## Overall ranking (Morris, mean of the normalised mu* over overshoot, settling, IAE, peak current, SSE)

| rank | parameter | score | what to measure first |
|---|---|---|---|
| 1 | eta | 0.60 | gearbox efficiency: loaded versus no-load current at a known output torque |
| 2 | R | 0.39 | winding resistance: low-voltage locked-rotor test with a current limit (or 4-wire ohmmeter) |
| 3 | Ke | 0.21 | back-EMF constant: speed-versus-voltage line at several voltages, or coast-down generator voltage |
| 4 | Kt | 0.21 | torque constant: measure stall/low-speed torque against current with a torque arm |
| 5 | Bm | 0.11 | viscous friction: steady-state speed versus current at low speeds, both directions |
| 6 | Jm | 0.10 | rotor inertia: free-run speed decay / mechanical time constant, ideally with a known added inertia |
| 7 | V_supply | 0.06 | supply voltage under load: log the rail during a step with the real supply and wiring |
| 8 | L | 0.05 | armature inductance: LCR meter or a voltage-step current rise |
| 9 | delay_steps | 0.01 | loop dead time: timing audit of the real controller/driver (scope on command and PWM) |

**Recommendation: measure eta, R and Ke on the bench first** (they dominate the predicted closed-loop behaviour over their plausible ranges).

## Ke / Kt consistency

Forcing Ke = Kt (to Kt, to Ke, or to their geometric mean) moves the Tuned-gain overshoot across a span of 6.2 percentage points (nominal Ke/Kt = 3.22), versus 0.0 points for the largest +-20 % effect among R, Jm, Bm and eta (eta). Monte-Carlo overshoot: independent Ke, Kt (+-20 %) mean 0.0 % with SD 0.0; one shared K between Kt and Ke has mean 1.8 % with SD 2.3. The Ke/Kt inconsistency is therefore a leading driver of the predicted behaviour, not a detail.

## RL tuner robustness preview

Gains the committed policy picks for this condition's 90 deg case: Kp 49.22, Ki 161.683, Kd 1.664 (a preview only: pre-validation prototype). See `sensitivity_rl_robustness.csv` for every perturbed plant.

- RL policy (committed): overshoot 0.0-3.0 %, within 2 % of target in 33 of 33 perturbed plants.
- Tuned preset: overshoot 0.0-0.0 %, within 2 % of target in 0 of 33 perturbed plants.
- Legacy default: overshoot 1.9-21.9 %, within 2 % of target in 27 of 33 perturbed plants.

## One-at-a-time table (Tuned gains)

| parameter | level | overshoot_pct | settle_s | rise_s | iae_deg_s | peak_current_A | sse_deg |
|---|---|---|---|---|---|---|---|
| nominal | nominal | 0 | never | never | 48.53 | 7.5 | -19.83 |
| R | -50% | 0 | never | never | 30.46 | 15 | -10.37 |
| R | -20% | 0 | never | never | 41.63 | 9.375 | -16.21 |
| R | +20% | 0 | never | never | 54.99 | 6.25 | -23.25 |
| R | +50% | 0 | never | never | 63.85 | 5 | -27.94 |
| Kt | -50% | 0 | never | never | 76.59 | 7.5 | -34.66 |
| Kt | -20% | 0 | never | never | 56.53 | 7.5 | -24.06 |
| Kt | +20% | 0 | never | never | 42.81 | 7.5 | -16.83 |
| Kt | +50% | 0 | never | never | 36.78 | 7.5 | -13.67 |
| Ke | -50% | 0 | never | 0.184 | 45.82 | 7.5 | -19.83 |
| Ke | -20% | 0 | never | 0.273 | 47.46 | 7.5 | -19.83 |
| Ke | +20% | 0 | never | never | 49.6 | 7.5 | -19.83 |
| Ke | +50% | 0 | never | never | 51.19 | 7.5 | -19.83 |
| Jm | -50% | 0 | never | never | 48.17 | 7.5 | -19.83 |
| Jm | -20% | 0 | never | never | 48.4 | 7.5 | -19.83 |
| Jm | +20% | 0 | never | never | 48.66 | 7.5 | -19.83 |
| Jm | +50% | 0 | never | never | 48.83 | 7.5 | -19.83 |
| Bm | -50% | 0 | never | never | 48.19 | 7.5 | -19.83 |
| Bm | -20% | 0 | never | never | 48.4 | 7.5 | -19.83 |
| Bm | +20% | 0 | never | never | 48.67 | 7.5 | -19.83 |
| Bm | +50% | 0 | never | never | 48.87 | 7.5 | -19.83 |
| eta | -50% | 0 | never | never | 75.45 | 7.5 | -34.67 |
| eta | -20% | 0 | never | never | 56.15 | 7.5 | -24.06 |
| eta | +20% | 0 | never | never | 43.13 | 7.5 | -16.83 |
| eta | +50% | 0 | never | never | 42.02 | 7.5 | -16.21 |
| L | 0.1 mH | 0 | never | never | 48.54 | 7.435 | -19.83 |
| L | 0.5 mH | 0 | never | never | 48.54 | 7.36 | -19.83 |
| L | 1 mH | 0 | never | never | 48.56 | 7.261 | -19.83 |
| L | 2 mH | 0 | never | never | 48.58 | 7.18 | -19.83 |
| L | 5 mH | 0 | never | never | 48.65 | 6.903 | -19.83 |
| delay_steps | 1 sample(s) | 0 | never | never | 48.58 | 7.5 | -19.83 |
| delay_steps | 2 sample(s) | 0 | never | never | 48.63 | 7.5 | -19.83 |
| delay_steps | 3 sample(s) | 0 | never | never | 48.67 | 7.5 | -19.83 |
| V_supply | -5% | 0 | never | never | 48.95 | 7.125 | -19.83 |
| V_supply | +5% | 0 | never | never | 48.16 | 7.875 | -19.83 |
| parameter set | method_a | 6.197 | never | 0.161 | 45.55 | 7.5 | -19.78 |
| parameter set | method_c | 0 | never | never | 48.53 | 7.5 | -19.83 |
