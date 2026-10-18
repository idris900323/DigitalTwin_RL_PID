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

**Evidence status.** v3's design was chosen *after* seeing the v2 results on test seeds 50000+, so those seeds are **exploratory** for v3 (`results/controller_comparison_v3/`). The **confirmatory** result is on fresh seeds 60000-60099 per regime (`results/controller_comparison_v3_fresh/`), which were never used to train, select or tune anything and were run once; best constants were re-selected on the validation seeds only. The headline is the episode return; success rate is descriptive.

Median return difference of the validation-selected PPO seed to the best constant (feasible scenarios; 95 % bootstrap CI), with the three training seeds:

| regime | exploratory 50000+ | **confirmatory 60000+** | seeds s0 / s1 / s2 (60000+) |
|---|---|---|---|
| static (primary) | +0.505 [+0.303, +0.826] | **+0.610 [+0.286, +0.752]** | +0.226 / +0.610 / +0.405 |
| changes | +0.554 [+0.253, +1.486] | **+0.579 [+0.244, +1.227]** | +0.535 / +0.579 / +0.321 |
| ood | +0.572 [+0.258, +0.962] | **+0.452 [+0.236, +0.737]** | +0.297 / +0.452 / +0.317 |

- **Per-seed significance.** All three seeds beat the best constant in the median in every regime, and no policy sits at a gain bound. After Holm adjustment (secondary family, all regimes) seeds 0 and 1 survive in all three regimes on both seed sets. **Seed 2 in `changes` is inconclusive** (Holm-adjusted p = 1.0 on 60000+, 0.54 on 50000+), so the claim for that regime rests on two of three seeds.
- **Success rate is not stable, so it is descriptive only.** `static`: 74 % against 54 % for the best constant on 50000+, but **58 % against 49 %** on 60000+; `changes`: 44 % against 34 % and 37 % against 27 %; `ood`: 69 % against 49 % and 56 % against 47 %. Do not quote the 50000+ figure without the fresh one.
- **Headroom captured** (mean PPO gain over the best constant divided by the hindsight-oracle headroom; selected seed on 60000+): 60 % `static`, 24 % `changes`, 46 % `ood`; the seed average is 44 %, 10 % and 31 %, and one seed captures less than nothing in `changes` (-4 %). The oracle chooses its gains per scenario with hindsight, so this is the ceiling for any adaptive tuner of this kind; v3 is not close to it, and `changes` leaves the most unrealised.
- **Infeasible scenarios stay a separate table** (torque margin < 1.0 at any point). On 60000+, `changes` has 17 of 100 infeasible; there PPO is no better than the best constant (mean return -85.2 against -85.5; oracle -42.6), so the infeasible split matters for reading the regime. Numbers move with the seed set (11 of 100 on 50000+).
- **Training stability.** Peak-to-final degradation on the validation curve is 0.0, 0.07 and 0.6 (v2: about 7 on the training-evaluation stream; the two numbers are not the same measurement).

**Supported claim.** In simulation on the unvalidated twin, a PPO policy acting as a residual on a validation-tuned constant beats that constant by about 0.5-0.6 median return (about 6-10 % of |return|), consistently across training seeds and on fresh scenarios. This is not a validated or hardware result, it does not show that RL adaptation replaces tuning (the policy starts from a tuned constant, and the v2 failure shows the unconstrained setup does not find it), and the benefit in `changes` is the weakest.

**Other caveats.**
1. The reference constant was found on `static` validation scenarios and is the residual's zero point; part of v3's gain is that it starts from a good point.
2. The improvement is small against the oracle headroom and has not been checked on hardware or a validated twin.
3. The v2 failure is best described as an *unconstrained* setup (unbounded-feeling multiplicative walk to the bounds, an under-shaped reward, early-peaking checkpoints chosen on the training stream); v3 changed all of these at once, so this work does not isolate which change mattered.

## Reproducibility

Policies are committed under `rl/policies/ppo_v2/` and `rl/policies/ppo_v3/` (the repository previously ignored `*.zip`, so the first push of PR #10 did not contain the weights; `rl/policies/**/*.zip` is now un-ignored). The SHA-256 of every weight file is in each seed's `meta.json` (`policy_files_sha256`) and of the loaded files in `comparison_manifest.json`, together with the torch, stable-baselines3 and gymnasium versions. Intermediate checkpoints are not committed; `val_curve.json` keeps the validation curve.
