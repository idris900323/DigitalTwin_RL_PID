# Changelog

All results are simulated on the preliminary twin unless stated; nothing has been validated on hardware.

## Group 4-5 (RL environment, comparison, PyBullet interface)
- `RL_PID_Env` (Gymnasium, shared twin physics, domain randomisation, mid-episode payload/target changes, reward breakdown), `rl/train_ppo.py` (PPO/SAC/TD3 with SB3, multi-seed), `simulation/compare_controllers.py` (paired held-out scenarios, bootstrap CIs, Wilcoxon, failure analysis, OOD regime).
- Revised after review: Ki can rise from zero (`ki_seed`), Kd bound 2 (noise), chatter weight 0.5, 5 PPO seeds, policies committed (`rl/policies/ppo_v2`). Comparison now has a best-constant baseline and a re-tuning bandit, both chosen/defined without the test seeds, validation-selected PPO seed, one pre-specified primary test, Holm-adjusted secondary tests, infeasible scenarios reported separately, policy hashes and library versions in the manifest.
- Review round 3: v3 confirmed on fresh seeds 60000-60099 (`results/controller_comparison_v3_fresh/`, labelled confirmatory; 50000+ relabelled exploratory); headroom captured, per-seed Holm wording, success rate descriptive; PyBullet Linux CI job passed (9 tests, none skipped).
- Review round 2: PPO weights now actually committed (`*.zip` had been ignored, contrary to the earlier note), SHA-256 in meta and manifest; stronger hindsight oracle (48 random + Ki=0 grid + best constant/bandit/Tuned); validation-selected checkpoints; training-instability report; v3 residual experiment (`docs/rl_findings.md`): +0.51 median return over the best constant (CI [+0.30, +0.83]), design chosen after seeing v2 test results.
- Result (simulated, pre-validation): PPO is WORSE than the best constant gains in all three regimes (primary: median return difference -1.75, CI [-2.00, -1.53]); the original 'PPO beats the bandit-level baselines' reading of PR #10 is withdrawn.
- The bandit README table gained a best-constant row: it matches the policy's share within 2 % (94.7 %) at about 9 % higher cost.
- Zoo sampling ranges moved into the YAML; PyBullet URDF tensors made valid (untested against PyBullet; Linux CI job added).
- PyBullet could not be installed here; `docs/pybullet_install_windows.md` records what was tried; `pybullet_sim/` has a tested URDF generator and an untested wrapper.

## Group 3B (bring your own motor)
- Motor profiles with provenance, units and validation; derivation engine with intervals and conflict reports; `--motor` on scripts, trainer and demos.
- Datasheet ingestion (text, CSV, text PDF, optional OCR) with mandatory per-value confirmation, ambiguity questions and a curve digitiser.
- Load/task definitions; analytic, optimised and robust PID tuning with margins, sanity checks, tier labels, reports and code export (Python, C, Arduino).
- Closing the loop: identification to a candidate profile (Tier 2 only if the fit passes), relay-feedback refinement (Tier 3), on-hardware protocol.
- `dtrl` command-line interface, browser motor dropdown, synthetic motor zoo (20 motors) with stability, spec, price-of-uncertainty and calibration results.

## Group 3 (simulation programme and validation tooling)
- G3.1 Full metric set (IAE, ISE, ITAE, MAE, effort, peak current, energy, time to band), raw-log schema and manifests, fixed method styles, `simulation/simulate_pid.py` with regenerable, byte-identical results.
- G3.2 Sensitivity study (`simulation/sensitivity.py`): one-at-a-time, Morris screening with bootstrap CIs, Ke/Kt consistency, RL robustness preview, bare and loaded conditions; command-delay support in the twin.
- G3.3 Datasheet-consistency derivation and inactive alternative parameter sets `method_d`, `method_d2`, `method_d3` (`docs/parameter_derivation.md`).
- G3.4 Bench validation plan and report template (`docs/validation_plan.md`).
- G3.5 `validation/`: bench-CSV loader with sanity checks, identifiability-aware identification, comparison and pass/fail, synthetic data.
- G3.6 Documentation pass (README status, architecture, glossary, ruff/mypy configuration).

## Group 2 (single source of truth)
- YAML is the only place motor constants live; generated JS config, shared `physics.js`, 83k-triangle CAD mesh embedded by the generator.
- Joint model (inertia, gravity, friction, disturbances), optional driver current limit, factory.
- Cross-implementation tests, base-code oracle (CI-aware), unit tests, 99 % coverage of `models/`, `controllers/`, `simulation/metrics.py`.
- Bugs fixed: explicit RK4 unstable for L > 0 (now sub-steps; raises beyond a cap), negative-step metrics.

## Group 1 (bug fixes)
- Real armature current logged when L = 0; Tuned preset as default gains (legacy kept); non-overlapping matplotlib layout; browser fixes (arm default, camera refit, badge, favicon); torque-feasibility check and banner; seeded trainer with metadata and parity tests; repository hygiene.
