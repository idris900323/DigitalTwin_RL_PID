# RL gain adaptation: what was tried and what was found (PRE-VALIDATION, simulated)

Everything here is simulated on the unvalidated, datasheet-derived twin. Primary metric (fixed before the analysis): episode return of `RL_PID_Env` scored with the default reward; success rate is descriptive. One primary test: validation-selected PPO minus the best constant gains, `static` regime, feasible scenarios (torque margin >= 1.0 all episode), paired median difference with a 95 % bootstrap CI. Everything else is secondary (Holm-adjusted). Details and tables: `results/controller_comparison/` (v2) and `results/controller_comparison_v3/` (v3).

## v2: this PPO configuration did not match a tuned constant

Configuration: multiplicative actions (+-10 % per 20 ms), Kp in [0.5, 50], Ki in [0, 200], Kd in [0.005, 2], 150k decisions, 5 seeds, checkpoint = EvalCallback best on the training evaluation seeds. Result (primary): median return difference to the best constant **-1.75, CI [-2.00, -1.53]**.

- **Final gains.** Per-seed median final gains were 50 / 200 / 2 (seeds 0 and 3, Ki at its 200 maximum in 69 % and 92 % of episodes), 44 / 52 / 2, 50 / 33 / 2 and 50 / 20 / 2: Kp at 50 and Kd at 2 in most episodes, with a lot of integral action, whereas the best constant found on validation seeds has Ki about 0 (Kp 19, Kd 1.3). This says the configuration (reward, action space, training length) did not find a good solution; it is not a statement about the limits of RL adaptation.
- **Training instability.** The evaluation reward peaks early and degrades: peak at 60k-120k decisions (-11.1 to -13.3) and final -12.5 to -22.3, a drop of 0.4 to 10.3 (about 7 on average; 4 of 5 seeds drop by more than 6). `best_model.zip` is the peak on the *training* evaluation seeds (10000+), a stream that is not the validation set; v3 selects on validation seeds 40000+.
- **Bandit versus best constant (return).** The one-shot bandit is slightly worse than the best constant in `static` (median -0.16, CI [-0.24, -0.05]) and `ood`, and slightly better in `changes` (+0.33, CI [+0.11, +0.89]). The bandit's README advantage is over Tuned/Legacy, not over a tuned constant (see the README table).
- **Oracle headroom.** The stronger hindsight oracle (48 random sets + a 20-point Ki = 0 grid + Tuned + bandit + best constant per scenario) beats the best constant by 17.6 % (`static`), 34.6 % (`changes`), 19.5 % (`ood`) of |return|. This is the ceiling for any adaptive tuner on these scenarios.

## v3: residual formulation (next experiment from the review)

Changes: the action is an *offset from the best constant* (zero action = Kp 19, Ki 0, Kd 1.3, `rl_env.residual` in the YAML; Kp and Kd scale by 2^a, Ki = a * 20), learning rate 1e-4, `log_std_init` -1 (the entropy coefficient was already 0), a shaped reward (an extra time-outside-2 %-band term plus the existing overshoot term, used for training only; scoring uses the default reward), 400k decisions, 3 seeds, a checkpoint every 10k decisions selected on validation seeds 40000+ (`rl/select_checkpoints.py`).

Result (primary): validation-selected seed `ppo_s1` is **better** than the best constant: median return difference **+0.505, CI [+0.303, +0.826]**; seed means -7.40 +- 0.22 against -7.93 for the constant. Success within 2 % with overshoot <= 10 %: 74 % against 54 %. The `changes` (+0.55) and `ood` (+0.57) regimes agree in sign. No policy sits at a gain bound. The mean improvement over the constant closes about 59 % (`static`), 20 % (`changes`) and 52 % (`ood`) of the gap to the hindsight oracle. Peak-to-final degradation on the validation curve is 0.0, 0.07 and 0.6 (v2: about 7 on the training-evaluation stream; the two numbers are not the same measurement).

**Caveats, to be read with the result.**
1. v3's design was chosen *after* seeing the v2 test results, on the same test scenarios (seeds 50000+). No choice inside v3 used the test seeds, but the test set is no longer untouched with respect to the design. Confirm on fresh test seeds before relying on the result.
2. The reference constant was found on `static` validation scenarios and is the residual's zero point; part of v3's gain is that it starts from a good point. The honest reading is "a residual PPO around a tuned constant improves it modestly in simulation", not "RL replaces tuning".
3. The improvement (about 0.5 to 0.8 return units, 6 to 10 % of |return|) is small against the oracle headroom and has not been checked on hardware or on a validated twin.

## Reproducibility

Policies are committed under `rl/policies/ppo_v2/` and `rl/policies/ppo_v3/` (the repository previously ignored `*.zip`, so the first push of PR #10 did not contain the weights; `rl/policies/**/*.zip` is now un-ignored). The SHA-256 of every weight file is in each seed's `meta.json` (`policy_files_sha256`) and of the loaded files in `comparison_manifest.json`, together with the torch, stable-baselines3 and gymnasium versions. Intermediate checkpoints are not committed; `val_curve.json` keeps the validation curve.
