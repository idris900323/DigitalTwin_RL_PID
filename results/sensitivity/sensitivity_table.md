# Sensitivity analysis (preliminary twin, simulated)

Tuned gains (15.0, 0.0, 0.3), 90 deg step, bare shaft, parameter set `method_c`, seed 0, Morris r = 30. Ranges come from `sensitivity_ranges` in the YAML (datasheet +-5 %, calculated +-20 %, assumed +-50 %, Jm/Bm x/ divided by 3, L 0.1-5 mH, delay 0-3 samples). Nothing here has been validated on hardware.

## Overall ranking (Morris, mean of the normalised mu* over overshoot, settling, IAE, peak current, SSE)

| rank | parameter | score | what to measure first |
|---|---|---|---|
| 1 | Jm | 0.85 | rotor inertia: free-run speed decay / mechanical time constant, ideally with a known added inertia |
| 2 | R | 0.41 | winding resistance: low-voltage locked-rotor test with a current limit (or 4-wire ohmmeter) |
| 3 | Kt | 0.30 | torque constant: measure stall/low-speed torque against current with a torque arm |
| 4 | Ke | 0.25 | back-EMF constant: speed-versus-voltage line at several voltages, or coast-down generator voltage |
| 5 | Bm | 0.17 | viscous friction: steady-state speed versus current at low speeds, both directions |
| 6 | V_supply | 0.08 | supply voltage under load: log the rail during a step with the real supply and wiring |
| 7 | L | 0.07 | armature inductance: LCR meter or a voltage-step current rise |
| 8 | delay_steps | 0.03 | loop dead time: timing audit of the real controller/driver (scope on command and PWM) |
| 9 | eta | 0.00 | gearbox efficiency: loaded versus no-load current at a known output torque |

**Recommendation: measure Jm, R and Kt on the bench first** (they dominate the predicted closed-loop behaviour over their plausible ranges).

## Ke / Kt consistency

Forcing Ke = Kt (to Kt, to Ke, or to their geometric mean) moves the Tuned-gain overshoot across a span of 23.7 percentage points (nominal Ke/Kt = 3.22), versus 3.4 points for the largest +-20 % effect among R, Jm, Bm and eta (Jm). Monte-Carlo overshoot: independent Ke, Kt (+-20 %) mean 2.3 % with SD 2.0; one shared K between Kt and Ke has mean 7.2 % with SD 7.8. The Ke/Kt inconsistency is therefore a leading driver of the predicted behaviour, not a detail.

## RL tuner robustness preview

Gains the committed policy picks for this condition's 90 deg case: Kp 37.47, Ki 0.117, Kd 1.758 (a preview only: pre-validation prototype). See `sensitivity_rl_robustness.csv` for every perturbed plant.

- RL policy (committed): overshoot 0.0-2.1 %, within 2 % of target in 33 of 33 perturbed plants.
- Tuned preset: overshoot 0.0-14.6 %, within 2 % of target in 33 of 33 perturbed plants.
- Legacy default: overshoot 34.2-57.2 %, within 2 % of target in 22 of 33 perturbed plants.

## One-at-a-time table (Tuned gains)

| parameter | level | overshoot_pct | settle_s | rise_s | iae_deg_s | peak_current_A | sse_deg |
|---|---|---|---|---|---|---|---|
| nominal | nominal | 1.728 | 0.292 | 0.19 | 13 | 7.5 | -0.01058 |
| R | -50% | 0 | 0.343 | 0.193 | 11.28 | 15 | -0.01453 |
| R | -20% | 0.4264 | 0.301 | 0.188 | 12.15 | 9.375 | 0.001009 |
| R | +20% | 3.24 | 0.481 | 0.194 | 13.95 | 6.25 | 0.004371 |
| R | +50% | 5.394 | 0.551 | 0.202 | 15.41 | 5 | 0.01582 |
| Kt | -50% | 8.341 | 0.633 | 0.218 | 17.8 | 7.5 | -0.01067 |
| Kt | -20% | 3.616 | 0.495 | 0.196 | 14.19 | 7.5 | 0.008527 |
| Kt | +20% | 0.6035 | 0.299 | 0.188 | 12.28 | 7.5 | -0.004002 |
| Kt | +50% | 0.0219 | 0.317 | 0.188 | 11.72 | 7.5 | 0.01879 |
| Ke | -50% | 14.65 | 0.577 | 0.132 | 12.64 | 7.5 | 0.01874 |
| Ke | -20% | 5.236 | 0.444 | 0.164 | 12.42 | 7.5 | 0.01841 |
| Ke | +20% | 0.1775 | 0.362 | 0.223 | 14.1 | 7.5 | 0.006711 |
| Ke | +50% | 0 | 0.49 | 0.28 | 16.37 | 7.5 | -0.01265 |
| Jm | -50% | 0 | 0.369 | 0.206 | 11.77 | 7.5 | -0.01567 |
| Jm | -20% | 0.2799 | 0.311 | 0.193 | 12.31 | 7.5 | 0.004207 |
| Jm | +20% | 3.657 | 0.485 | 0.191 | 13.88 | 7.5 | 0.008627 |
| Jm | +50% | 6.647 | 0.55 | 0.195 | 15.33 | 7.5 | 0.002198 |
| Bm | -50% | 2.623 | 0.426 | 0.181 | 12.76 | 7.5 | -0.001675 |
| Bm | -20% | 2.06 | 0.399 | 0.187 | 12.9 | 7.5 | -0.005952 |
| Bm | +20% | 1.426 | 0.3 | 0.194 | 13.11 | 7.5 | -0.01703 |
| Bm | +50% | 1.032 | 0.312 | 0.2 | 13.29 | 7.5 | -0.01917 |
| eta | -50% | 1.728 | 0.292 | 0.19 | 13 | 7.5 | -0.01058 |
| eta | -20% | 1.728 | 0.292 | 0.19 | 13 | 7.5 | -0.01058 |
| eta | +20% | 1.728 | 0.292 | 0.19 | 13 | 7.5 | -0.01058 |
| eta | +50% | 1.728 | 0.292 | 0.19 | 13 | 7.5 | -0.01058 |
| L | 0.1 mH | 1.727 | 0.292 | 0.19 | 13 | 7.396 | -0.01045 |
| L | 0.5 mH | 1.721 | 0.292 | 0.19 | 13.01 | 7.299 | -0.01053 |
| L | 1 mH | 1.711 | 0.292 | 0.19 | 13.01 | 7.145 | -0.01048 |
| L | 2 mH | 1.695 | 0.291 | 0.189 | 13.02 | 7.054 | -0.01053 |
| L | 5 mH | 1.645 | 0.29 | 0.187 | 13.04 | 6.69 | -0.01053 |
| delay_steps | 1 sample(s) | 1.844 | 0.291 | 0.189 | 13.08 | 7.5 | -0.00804 |
| delay_steps | 2 sample(s) | 1.969 | 0.289 | 0.188 | 13.15 | 7.5 | -0.006391 |
| delay_steps | 3 sample(s) | 2.101 | 0.406 | 0.187 | 13.23 | 7.5 | -0.00474 |
| V_supply | -5% | 1.671 | 0.299 | 0.195 | 13.38 | 7.125 | -0.01144 |
| V_supply | +5% | 1.779 | 0.286 | 0.186 | 12.66 | 7.875 | -0.01009 |
| parameter set | method_a | 23.7 | 0.602 | 0.117 | 13.79 | 7.5 | 0.005479 |
| parameter set | method_c | 1.728 | 0.292 | 0.19 | 13 | 7.5 | -0.01058 |
