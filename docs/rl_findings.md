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

## v4: smaller residual range, and SAC / TD3 (the next experiment from the review)

Changes against v3 (`rl/ppo_v4.yaml`): residual range halved (Kp, Kd scale by 1.5^a instead of 2^a, Ki offset 10 instead of 20), 200k decisions, 3 seeds each of PPO, SAC and TD3 (learning rate 1e-4, buffers 200k), checkpoints selected on validation seeds 40000+. Evaluated once on seeds 70000-70099 per regime, which were never used for any choice (`results/controller_comparison_v4_{ppo,sac,td3}/`, labelled confirmatory). The summaries were re-rendered from `per_episode.csv` (no retraining, `--rerender`) so that the SAC and TD3 folders label their selected policy `sac (selected)` / `td3 (selected)` instead of the earlier, wrong `ppo` label; the tables now also show the mean paired difference with a bootstrap CI and the IQR of the paired differences next to the median CI.

| algorithm | static median difference (selected seed) | per seed s0 / s1 / s2 | changes (selected) | ood (selected) |
|---|---|---|---|---|
| PPO | **+0.352 [+0.343, +0.359]** | -0.620 / +0.329 / +0.352 | +0.179 [-0.083, +0.432] (inconclusive) | +0.337 [+0.294, +0.359] |
| SAC | +0.253 [+0.120, +0.315], but Wilcoxon p = 0.116 (Holm 0.47): **mixed** | +0.253 / +0.084 / -0.235 | -0.255 [-1.140, -0.063] (worse) | +0.238 |
| TD3 | -0.170 [-0.285, +0.089] (not distinguishable) | -1.019 / -0.704 / -0.170 | -2.126 (worse) | -0.100 (not distinguishable) |

- **PPO remains the only algorithm that beats the best constant in the median**, in `static` and `ood`, for two of three seeds; seed 0 is worse than the constant in both (-0.62, -0.56). In `changes` the selected seed is inconclusive and seed 0 is clearly worse (-1.20). The halved range gives a smaller gain (about +0.35) than v3's (+0.45 to +0.61); the test seeds differ, so the comparison with v3 is indicative only, and this work does not show that the smaller range is better.
- **TD3 did not beat the constant; SAC is mixed** at this budget and learning rate. See the next paragraph for SAC. Their validation curves peak early (selected checkpoints at 10k-60k decisions) and then degrade by 0.3-2.5 return units (SAC) and 0.9-3.3 (TD3) by the end of training (PPO v4: 0.1-0.7), the same early-peak pattern as v2. They have more seed-to-seed spread than PPO (TD3 seeds range from -1.0 to -0.17 in `static`).
- **Mean and IQR next to the narrow median CIs** (paired difference to the best constant, selected seed, feasible scenarios):

| | static: mean [95 % CI] / IQR | changes: mean [95 % CI] / IQR | ood: mean [95 % CI] / IQR |
|---|---|---|---|
| PPO | +0.378 [+0.363, +0.395] / [+0.333, +0.392] | -0.491 [-1.284, +0.185] / [-0.525, +0.771] | +0.309 [+0.139, +0.468] / [+0.250, +0.572] |
| SAC | +0.053 [-0.181, +0.279] / [-0.289, +0.407] | -1.575 [-2.387, -0.860] / [-2.373, +0.115] | -0.028 [-0.282, +0.177] / [-0.022, +0.366] |
| TD3 | +0.166 [-0.092, +0.447] / [-0.639, +0.541] | -2.058 [-2.907, -0.720] / [-3.699, -1.169] | +0.192 [-0.133, +0.539] / [-0.662, +0.473] |

  PPO's very narrow median CIs in `static` and `ood` (width about 0.02) are consistent with a tight spread of the paired differences (IQR width about 0.06 and 0.32), not with a lucky median. In `changes` PPO's median difference is positive (+0.18) but its mean is negative (-0.49) with an IQR across zero: heavy-tailed, so the regime stays inconclusive.
- **SAC statement (mixed, not "does not beat").** In `static` the selected seed's median difference is +0.253 with a 95 % CI [+0.120, +0.315] that excludes zero, but the paired Wilcoxon test is not significant (p = 0.116, Holm 0.47), the mean difference is +0.05 [-0.18, +0.28] and the IQR [-0.29, +0.41] straddles zero. The other two seeds are +0.084 (inconclusive) and -0.235 (significantly worse after Holm). In `ood` the selected seed's median (+0.238) is Holm-significant (p = 0.03) but its mean is -0.03. In `changes` all three SAC seeds are worse. The evidence is therefore mixed in `static` and `ood` and negative in `changes`; it neither supports nor rules out a small median benefit for SAC.
- **Headroom captured** on 70000+ (selected seed): PPO 27 % / -7 % / 17 % (`static` / `changes` / `ood`); SAC 4 % / -23 % / -2 %; TD3 12 % / -29 % / 11 %. `changes` is the regime where none of them helps, as in v3.
- **Infeasible scenarios** are tabulated separately in each folder (7, 14 and 7 of 100 in `static`, `changes`, `ood`); results there are mixed and not systematic: in `changes` (14 infeasible) the mean return of the selected SAC and TD3 seeds is higher than the best constant's (-58.7 and -54.7 against -64.8) while PPO's is lower (-72.4); these scenarios cannot be solved, so such differences are not evidence of better control. (An earlier version of this paragraph said the policies were no better than the constant on infeasible scenarios; that was wrong for SAC and TD3 in `changes`.)

Still untried: longer training for SAC/TD3 with a lower learning rate or a larger batch, the unconstrained (non-residual) formulation with the v3 reward and checkpoint selection, and a per-regime reference constant.

## Reproducibility

Policies are committed under `rl/policies/ppo_v2/`, `ppo_v3/`, `ppo_v4/`, `sac_v4/` and `td3_v4/` (the repository previously ignored `*.zip`, so the first push of PR #10 did not contain the weights; `rl/policies/**/*.zip` is now un-ignored). The SHA-256 of every weight file is in each seed's `meta.json` (`policy_files_sha256`) and of the loaded files in `comparison_manifest.json`, together with the torch, stable-baselines3 and gymnasium versions. Intermediate checkpoints are not committed; `val_curve.json` keeps the validation curve.
