# Changelog

All results are simulated on the preliminary twin unless stated; nothing has been validated on hardware.

## Group 4-5 (RL environment, comparison, PyBullet interface)
- `RL_PID_Env` (Gymnasium, shared twin physics, domain randomisation, mid-episode payload/target changes, reward breakdown), `rl/train_ppo.py` (PPO/SAC/TD3 with SB3, multi-seed), `simulation/compare_controllers.py` (paired held-out scenarios, bootstrap CIs, Wilcoxon, failure analysis, OOD regime).
- Result (simulated, pre-validation): 3 PPO seeds beat the Tuned preset but are indistinguishable from the one-shot bandit tuner and worse than a random-search oracle; no demonstrated benefit of step-wise adaptation, including with mid-episode changes.
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
