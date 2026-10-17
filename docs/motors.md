# Bring your own motor: datasheet in, recommended PID out

Everything here is **preliminary**: gains are computed on a model derived from a datasheet and are not validated on hardware. Brushed DC (gear)motors only; BLDC and stepper motors need different physics and are out of scope.

## What "perfect PID values" can and cannot mean

A datasheet does not contain enough to give perfect gains for a real motor on a real load: inertia, friction, inductance, gearbox efficiency, backlash and even the meaning of "stall torque" are usually missing or loose. The honest promise is a **tiered recommendation**, and every output (CLI, report, browser, exported code) shows its tier and its uncertainty:

| Tier | Inputs | Output | Label |
|---|---|---|---|
| 1 | datasheet only, class priors where values are missing | robust gains across the parameter uncertainty, wide bands | "datasheet estimate: safe starting point, expect to re-tune" |
| 2 | Tier 1 + bench data whose identification passed the validation thresholds | gains tuned to the identified model, narrow bands | "identified from bench data" |
| 3 | Tier 2 + a relay test on the real system | gains refined from real closed-loop data | "refined on hardware" |

No output prints gains without the tier, and nothing is called "perfect" or "optimal" without the objective and constraints (here: the cost in `tuning/optimize.py` and the load's limits). The tool also names the **least certain parameters** and the **single most valuable next measurement**.

## Workflow

```bash
# 1. import a datasheet (text, CSV, text PDF; OCR optional) -- you confirm every value
python -m dtrl motor add --input mymotor.pdf --id my_motor --manufacturer ACME --model GM-37
# 2. look at the derived model: parameters with intervals, datasheet conflicts, least certain parameters
python -m dtrl motor derive --motor my_motor
# 3. describe the load and task in loads/my_arm.yaml (see loads/arm_1kg_10cm.yaml), then tune
python -m dtrl tune --motor my_motor --load my_arm --out-dir reports/my_motor
# 4. export controller code (Python, C, or an Arduino-style sketch), with tier, date, profile hash and "re-tune after validation"
python -m dtrl export --motor my_motor --load my_arm --format c --out dtrl_pid.h
```

**The confirmation step is mandatory.** `motor add` shows every extracted value (source page and snippet, confidence, flags) and asks you to accept, reject or edit each one. Nothing is written as `datasheet` provenance without acceptance; edited values become provenance `user`; undecided values are rejected. It asks, instead of guessing, whether the stall current is really a stall current, whether the stall torque is theoretical or practical, which shaft a figure refers to and where the encoder sits. It flags a torque that equals another divided by the gear ratio, unit styles that invite factor-1000 mistakes, decimal commas and values that disagree. Every unit conversion is logged in the profile.

## Files

| Where | What |
|---|---|
| `motors/<id>/profile.yaml` | validated profile: each field has value, unit, provenance, source, confidence (shaft side is required for torque and speed) |
| `motors/<id>/datasheets/` | the original datasheet files, so every number can be traced to a page |
| `loads/<id>.yaml` | load (arm, payload range, gravity, friction) and task (targets, accuracy, overshoot and settling limits, limits on current, voltage and noise); loads the motor cannot drive are rejected with numbers |
| `models/derive.py` | derivation engine: consistent plant model, intervals, conflict report |
| `tuning/` | analytic (pole placement, IMC, Ziegler-Nichols), nominal and robust optimisation, margins, sanity checks, report, export |
| `autotune_360/recommendations.json` | precomputed Tier 1 recommendations shown by the browser page (`tools/precompute_recommendations.py`) |

Reference profiles: `rmcs_3070` (the project motor; its simulation parameters stay in `config/motor_parameters.yaml`) and two **synthetic** examples (`synthetic_coreless_12v`, `synthetic_brushed_48v`) built to exercise other units, a 48 V supply and a motor-shaft encoder in PPR.

## Derivation (models/derive.py)

An ideal brushed motor in SI has Ke = Kt = K. From what the profile contains: R from a stated resistance, else V / stall current (widened to R/4 .. 1.1 R when the current is only labelled "max"), else a class prior; K from the no-load balance V = R I0 + K w0, cross-checked against stated constants and the stall torque; viscous friction from the no-load current (an upper bound); efficiency stated, fitted from the output stall torque or a class prior; rotor inertia stated, else a rotor-cylinder approximation from the motor mass (x/3 interval), else a wide prior; inductance 0 with an interval up to a few mH. Disagreeing sources are reported as conflicts with candidate resolutions, never forced to agree.

## Tuning methods and how the winner is chosen

All methods are evaluated on the **same held-out plausible plants** (drawn inside the derived intervals) and the load's payload and target contexts: analytic pole placement, IMC/lambda, Ziegler-Nichols (reference only), nominal-model optimisation and robust optimisation (mean plus half the mean of the worst 10 %, with stability margins, a noise limit and the task constraints as penalties). The winner has the lowest robust cost among methods that meet the margins (45 degrees phase, 6 dB gain by default, delay margin reported). The report shows why (cost breakdown, runner-up), the Monte-Carlo prediction bands (5th, median, 95th percentile), the probability of meeting each constraint, a Bode plot, a check in the full twin, and sanity warnings (derivative noise amplification, integrator windup, gains at the search bounds, weak margins).

## Evidence (all simulated)

- `results/motor_zoo/summary.md`: 20 synthetic motors with known true parameters; datasheets generated with rounding, omissions and mistakes; Tier 1 gains judged on the true plant (stability, spec, price of uncertainty, calibration of the bands).
- `tests/test_closing.py`: from a deliberately imperfect datasheet, Tier 1 -> Tier 2 shrinks the settling-time prediction error from 0.05 s to 0.003 s and the band width from 0.16 s to 0.02 s, with the truth still inside the band.

## Limitations

Step targets only; the batch optimiser ignores command delay and joint friction (the final gains are re-checked in the full twin); the browser shows stored Tier 1 results (it cannot run the optimiser); RL policies exist only for the reference motor; no BLDC/stepper models; nothing here has met real hardware.
