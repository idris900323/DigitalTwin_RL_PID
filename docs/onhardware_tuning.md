# On-hardware tuning protocol (Tier 3)

Status: **protocol and analysis tooling only; never run on hardware so far**. It refines a Tier 2 recommendation from a short relay-feedback test on the real joint. Everything else in `docs/validation_plan.md` section 3 (safety setup) applies first. The person running the rig reviews this protocol and may stop at any time.

## When to use it

Only after the motor has been identified (Tier 2: `validation/identify.py`, thresholds passed). The relay test checks and corrects the inertia seen by the controller (arm, payload, coupling) under the real loop, including delay and friction, which bench tests on the bare shaft do not capture.

## Relay-feedback test

The controller is temporarily replaced by a relay: the output is +d volts when the error is above +h and -d volts when it is below -h. The loop oscillates around the target with period Tu; the amplitude a of the oscillation gives the ultimate gain Ku = 4 d / (pi a).

**Settings (start small, increase only if the oscillation is too small to measure):**
- relay amplitude d: 10-20 % of the supply voltage (for a 12 V motor start at 1.5 V; never above 3 V on the first run);
- hysteresis h: 0.5 deg (about 13 encoder counts at 9360 counts/rev) so that quantisation noise does not chatter the relay;
- start with the arm at the target angle, payload attached as for the task; sample at 1 kHz; run 5 s (at least 6 full cycles; the analysis skips the first two).

**Safety limits and abort conditions (all automatic in the logging tool, in addition to the hard stops and the supply current limit):**
1. current limit on the supply at or below the driver rating; relay output clipped to the stated amplitude;
2. travel limit: abort if the angle leaves +-20 deg of the target (an oscillation amplitude of about 1-2 deg is expected);
3. abort if the motor-housing temperature exceeds the limit of the validation plan, or if the current exceeds 1.2 x the expected peak;
4. abort on any watchdog or timing fault (`loop_dt_us` above 100 us jitter);
5. no test with the legacy default gains or with a payload outside the range of the load definition.

## Analysis

```python
from tuning.closing import relay_analysis, refine_with_relay
relay = relay_analysis(t, theta_rad, d_volts)          # Ku, Tu, amplitude, cycles; raises if fewer than 6 cycles
rec3  = refine_with_relay(rec2, relay, d_volts=d, hysteresis_rad=h)     # re-tunes at Tier 3
```

`refine_with_relay` adjusts the rotor-inertia estimate (the least certain and most influential parameter) until the twin reproduces the measured relay oscillation (period and amplitude), narrows its interval to +-5 %, and recomputes the recommendation. The tier label becomes **Tier 3 - refined on hardware**. The Ziegler-Nichols and Tyreus-Luyben gains from the relay result are also returned for reference; they are not used directly because a second-order servo with delay needs the model-based design.

## Tier rules

A recommendation is Tier 1 until measured data is loaded, Tier 2 only after an identification that **passed** the validation thresholds on held-out data (`tuning.closing.tier_after_identification` refuses otherwise), and Tier 3 only after this relay refinement on top of Tier 2. Simulated relay tests in `tests/test_closing.py` check the analysis; they are not evidence about any real motor.
