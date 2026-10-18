# Controller comparison (PRE-VALIDATION, simulated on the unvalidated twin)

100 held-out paired TEST scenarios per regime (seeds 70000..70099); 40 VALIDATION scenarios (seeds 40000..40039) were used to choose `best_constant` and the reported PPO seed; neither set was used in training. Every controller sees the same plant, payload, target, delay and noise for a given seed. `return` is the environment reward (higher is better).
`random_search` is an ORACLE (best of 48 random sets + a 20-point Ki = 0 grid + Tuned + bandit + best_constant per scenario, chosen with hindsight): an upper bound for any adaptive tuner of this kind, not a deployable controller. Primary metric: episode return (success rate is descriptive).

**Analysis status: confirmatory.** These seeds were not used to train, select or tune anything; they confirm (or not) a design fixed earlier. Nothing may be re-tuned on them. One primary comparison: validation-selected PPO minus `best_constant`, `static` regime, feasible scenarios, paired median difference of return with a 95 % bootstrap CI. All other comparisons are secondary: paired Wilcoxon p-values, Holm-adjusted across the whole secondary family (feasible scenarios, all regimes). Infeasible scenarios (torque margin < 1.0 at any point, including after a payload change) are reported separately.

## Regime `static`

Best constant gains (chosen on validation): Kp 18.94, Ki 0.01, Kd 1.317 (validation return -8.099).
PPO seeds, validation mean return: sac_s0 -7.989, sac_s1 -8.346, sac_s2 -8.289. Selected on validation: `sac_s0`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 93 feasible scenarios of 100, the 7 infeasible ones are tabulated separately below.

Feasible scenarios: 93 of 100; infeasible: 7.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -10.072 ± 9.102 | -7.088 | -1.617 [-2.694, -1.190] | -2.713 [-3.416, -2.079] | [-3.997, -0.365] | 9.3e-14 | 2.14e-12 | 32.9 | 16.2 | 0.783 | 20 % | 0 % | 0 % |
| legacy | -45.726 ± 70.121 | -24.785 | -18.995 [-26.105, -15.374] | -38.366 [-53.995, -26.635] | [-39.091, -11.671] | 1.78e-16 | 4.63e-15 | 63.2 | 52.9 | 1.356 | 2 % | 0 % | 0 % |
| best_constant | -7.359 ± 8.164 | -5.412 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 29.5 | 2.9 | 0.523 | 66 % | 0 % | 0 % |
| zn | -16.948 ± 24.872 | -6.258 | -1.132 [-1.374, -1.034] | -9.588 [-14.302, -5.611] | [-2.020, -0.886] | 7.13e-10 | 1.43e-08 | 55.9 | 7.8 | 0.615 | 56 % | 100 % | 0 % |
| bandit | -7.115 ± 8.064 | -5.323 | -0.114 [-0.191, -0.073] | +0.245 [-0.150, +0.746] | [-0.398, +0.058] | 0.0141 | 0.127 | 25.8 | 5.6 | 0.509 | 77 % | 26 % | 0 % |
| bandit_retune | -7.115 ± 8.064 | -5.323 | -0.114 [-0.191, -0.073] | +0.245 [-0.150, +0.746] | [-0.398, +0.058] | 0.0141 | 0.127 | 25.8 | 5.6 | 0.509 | 77 % | 26 % | 0 % |
| random_search | -5.958 ± 7.901 | -4.503 | +0.736 [+0.565, +0.840] | +1.401 [+1.025, +1.883] | [+0.470, +1.223] | 5.57e-17 | 1.62e-15 | 27.9 | 1.1 | 0.509 | 78 % | 26 % | 0 % |
| sac (selected) **(primary)** | -7.307 ± 8.221 | -5.161 | +0.253 [+0.120, +0.315] | +0.053 [-0.181, +0.279] | [-0.289, +0.407] | 0.116 | nan | 29.3 | 4.5 | 0.560 | 56 % | 0 % | 0 % |
| sac_s0 | -7.307 ± 8.221 | -5.161 | +0.253 [+0.120, +0.315] | +0.053 [-0.181, +0.279] | [-0.289, +0.407] | 0.116 | 0.471 | 29.3 | 4.5 | 0.560 | 56 % | 0 % | 0 % |
| sac_s1 | -7.621 ± 8.231 | -5.667 | +0.084 [-0.106, +0.251] | -0.261 [-0.442, -0.098] | [-0.389, +0.290] | 0.752 | 1 | 29.2 | 4.2 | 0.556 | 61 % | 0 % | 0 % |
| sac_s2 | -7.583 ± 8.119 | -5.643 | -0.235 [-0.572, +0.228] | -0.224 [-0.334, -0.114] | [-0.611, +0.307] | 8.12e-05 | 0.00106 | 29.7 | 3.2 | 0.529 | 63 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +1.401 (19.0 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected 4 %; per seed sac_s0 4 %, sac_s1 -19 %, sac_s2 -16 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.114 [-0.191, -0.073].

SAC across training seeds (feasible test scenarios, mean return): sac_s0 -7.307, sac_s1 -7.621, sac_s2 -7.583. Seed mean -7.503, std 0.140, range [-7.621, -7.307]; best constant -7.359.

### Infeasible scenarios (reported separately)

| controller | n | return mean | median |
|---|---|---|---|
| tuned | 7 | -42.573 | -43.113 |
| legacy | 7 | -40.811 | -43.122 |
| best_constant | 7 | -42.337 | -43.438 |
| zn | 7 | -68.185 | -92.789 |
| bandit | 7 | -40.433 | -43.113 |
| bandit_retune | 7 | -40.433 | -43.113 |
| random_search | 7 | -40.379 | -43.113 |
| sac (selected) | 7 | -41.441 | -43.196 |
| sac_s0 | 7 | -41.441 | -43.196 |
| sac_s1 | 7 | -42.056 | -43.127 |
| sac_s2 | 7 | -42.160 | -43.127 |

Infeasible seeds (min margin): 70012 (0.69), 70013 (0.77), 70016 (0.98), 70022 (0.69), 70057 (0.79), 70065 (0.55), 70088 (0.43)

## Regime `changes`

Best constant gains (chosen on validation): Kp 29.59, Ki 0.01, Kd 1.317 (validation return -19.770).
PPO seeds, validation mean return: sac_s0 -21.677, sac_s1 -22.360, sac_s2 -22.014. Selected on validation: `sac_s0`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 86 feasible scenarios of 100, the 14 infeasible ones are tabulated separately below.

Note: in this regime the target and payload change mid-episode, so overshoot, settling and success refer to the final target only; the return is the headline.

Feasible scenarios: 86 of 100; infeasible: 14.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -27.295 ± 40.380 | -16.422 | -3.227 [-4.758, -1.756] | -7.401 [-11.870, -4.525] | [-8.123, -0.854] | 1.2e-13 | 2.63e-12 | 59.8 | 49.3 | 1.286 | 19 % | 0 % | 0 % |
| legacy | -88.413 ± 109.533 | -50.379 | -34.145 [-39.606, -27.631] | -68.519 [-92.698, -48.474] | [-68.759, -17.921] | 9.2e-16 | 2.21e-14 | 86.0 | 90.5 | 1.692 | 2 % | 0 % | 0 % |
| best_constant | -19.894 ± 34.807 | -11.532 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 53.9 | 38.4 | 1.060 | 36 % | 0 % | 0 % |
| zn | -27.411 ± 35.287 | -11.943 | -0.961 [-1.190, -0.638] | -7.517 [-15.121, -0.518] | [-1.960, -0.246] | 6.08e-06 | 9.73e-05 | 70.2 | 35.2 | 1.124 | 45 % | 100 % | 0 % |
| bandit | -19.596 ± 35.789 | -10.083 | -0.052 [-0.115, +0.069] | +0.297 [-0.316, +0.873] | [-0.251, +0.850] | 0.383 | 1 | 52.3 | 38.8 | 1.067 | 50 % | 24 % | 0 % |
| bandit_retune | -20.049 ± 35.901 | -10.524 | -0.527 [-0.795, -0.237] | -0.155 [-0.813, +0.459] | [-0.947, +0.436] | 0.0676 | 0.471 | 52.0 | 39.0 | 1.080 | 53 % | 34 % | 0 % |
| random_search | -12.908 ± 14.550 | -9.040 | +1.337 [+0.919, +2.225] | +6.986 [+3.234, +11.897] | [+0.641, +4.390] | 7.99e-16 | 2e-14 | 49.3 | 15.6 | 0.999 | 64 % | 41 % | 0 % |
| sac (selected) | -21.468 ± 34.950 | -13.130 | -0.255 [-1.140, -0.063] | -1.575 [-2.387, -0.860] | [-2.373, +0.115] | 2.77e-05 | 0.000415 | 55.4 | 37.5 | 1.090 | 37 % | 0 % | 0 % |
| sac_s0 | -21.468 ± 34.950 | -13.130 | -0.255 [-1.140, -0.063] | -1.575 [-2.387, -0.860] | [-2.373, +0.115] | 2.77e-05 | 0.000415 | 55.4 | 37.5 | 1.090 | 37 % | 0 % | 0 % |
| sac_s1 | -21.820 ± 34.257 | -13.628 | -0.968 [-1.752, -0.569] | -1.926 [-2.888, -1.053] | [-3.315, -0.045] | 2.88e-08 | 5.19e-07 | 55.6 | 37.2 | 1.094 | 38 % | 0 % | 0 % |
| sac_s2 | -21.813 ± 34.321 | -13.327 | -1.398 [-1.586, -0.948] | -1.919 [-2.734, -1.135] | [-3.139, -0.519] | 2.19e-09 | 4.16e-08 | 55.5 | 36.2 | 1.090 | 42 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +6.986 (35.1 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected -23 %; per seed sac_s0 -23 %, sac_s1 -28 %, sac_s2 -27 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.052 [-0.115, +0.069].

SAC across training seeds (feasible test scenarios, mean return): sac_s0 -21.468, sac_s1 -21.820, sac_s2 -21.813. Seed mean -21.700, std 0.164, range [-21.820, -21.468]; best constant -19.894.

### Infeasible scenarios (reported separately)

| controller | n | return mean | median |
|---|---|---|---|
| tuned | 14 | -97.918 | -58.690 |
| legacy | 14 | -221.387 | -102.874 |
| best_constant | 14 | -64.782 | -36.514 |
| zn | 14 | -84.350 | -81.967 |
| bandit | 14 | -55.996 | -27.947 |
| bandit_retune | 14 | -55.276 | -26.305 |
| random_search | 14 | -37.721 | -21.207 |
| sac (selected) | 14 | -58.721 | -39.459 |
| sac_s0 | 14 | -58.721 | -39.459 |
| sac_s1 | 14 | -61.761 | -50.891 |
| sac_s2 | 14 | -69.087 | -44.823 |

Infeasible seeds (min margin): 70012 (0.69), 70013 (0.77), 70016 (0.98), 70021 (0.79), 70022 (0.69), 70031 (0.65), 70056 (0.81), 70057 (0.79), 70065 (0.55), 70072 (0.46), 70076 (0.74), 70079 (0.97)...

## Regime `ood`

Best constant gains (chosen on validation): Kp 23.67, Ki 0.01, Kd 1.317 (validation return -10.173).
PPO seeds, validation mean return: sac_s0 -10.032, sac_s1 -10.461, sac_s2 -10.412. Selected on validation: `sac_s0`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 93 feasible scenarios of 100, the 7 infeasible ones are tabulated separately below.

Feasible scenarios: 93 of 100; infeasible: 7.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -11.633 ± 13.324 | -7.024 | -1.032 [-1.854, -0.295] | -2.668 [-3.716, -1.806] | [-4.268, +0.341] | 4.71e-08 | 8.01e-07 | 37.0 | 13.3 | 0.719 | 33 % | 0 % | 0 % |
| legacy | -47.064 ± 77.044 | -22.377 | -15.665 [-21.897, -11.182] | -38.099 [-55.320, -25.471] | [-33.642, -9.201] | 1.52e-16 | 4.1e-15 | 63.2 | 46.7 | 1.354 | 2 % | 0 % | 0 % |
| best_constant | -8.965 ± 11.556 | -5.606 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 33.2 | 4.4 | 0.570 | 63 % | 0 % | 0 % |
| zn | -17.473 ± 24.287 | -6.401 | -1.208 [-1.482, -1.022] | -8.508 [-12.789, -4.982] | [-2.252, -0.703] | 2.72e-11 | 5.7e-10 | 57.1 | 8.4 | 0.645 | 57 % | 100 % | 0 % |
| bandit | -8.642 ± 11.364 | -5.395 | -0.101 [-0.149, -0.033] | +0.323 [-0.081, +0.872] | [-0.252, +0.125] | 0.0673 | 0.471 | 30.8 | 5.9 | 0.542 | 73 % | 26 % | 0 % |
| bandit_retune | -8.642 ± 11.364 | -5.395 | -0.101 [-0.149, -0.033] | +0.323 [-0.081, +0.872] | [-0.252, +0.125] | 0.0673 | 0.471 | 30.8 | 5.9 | 0.542 | 73 % | 26 % | 0 % |
| random_search | -7.176 ± 11.120 | -4.827 | +0.796 [+0.744, +0.952] | +1.789 [+1.282, +2.443] | [+0.638, +1.453] | 5.57e-17 | 1.62e-15 | 32.7 | 1.0 | 0.560 | 78 % | 26 % | 0 % |
| sac (selected) | -8.993 ± 11.751 | -5.582 | +0.238 [+0.190, +0.289] | -0.028 [-0.282, +0.177] | [-0.022, +0.366] | 0.00268 | 0.0295 | 34.0 | 4.7 | 0.616 | 60 % | 0 % | 0 % |
| sac_s0 | -8.993 ± 11.751 | -5.582 | +0.238 [+0.190, +0.289] | -0.028 [-0.282, +0.177] | [-0.022, +0.366] | 0.00268 | 0.0295 | 34.0 | 4.7 | 0.616 | 60 % | 0 % | 0 % |
| sac_s1 | -9.280 ± 11.705 | -5.753 | +0.067 [-0.060, +0.198] | -0.315 [-0.535, -0.129] | [-0.323, +0.241] | 0.494 | 1 | 33.9 | 4.5 | 0.639 | 61 % | 0 % | 0 % |
| sac_s2 | -9.267 ± 11.584 | -5.920 | -0.206 [-0.530, +0.202] | -0.302 [-0.516, -0.106] | [-0.680, +0.294] | 0.000673 | 0.00807 | 34.4 | 3.7 | 0.612 | 65 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +1.789 (20.0 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected -2 %; per seed sac_s0 -2 %, sac_s1 -18 %, sac_s2 -17 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.101 [-0.149, -0.033].

SAC across training seeds (feasible test scenarios, mean return): sac_s0 -8.993, sac_s1 -9.280, sac_s2 -9.267. Seed mean -9.180, std 0.132, range [-9.280, -8.993]; best constant -8.965.

### Infeasible scenarios (reported separately)

| controller | n | return mean | median |
|---|---|---|---|
| tuned | 7 | -38.822 | -21.558 |
| legacy | 7 | -38.532 | -20.896 |
| best_constant | 7 | -38.281 | -20.851 |
| zn | 7 | -67.771 | -89.819 |
| bandit | 7 | -37.451 | -20.523 |
| bandit_retune | 7 | -37.451 | -20.523 |
| random_search | 7 | -37.369 | -20.523 |
| sac (selected) | 7 | -38.062 | -21.299 |
| sac_s0 | 7 | -38.062 | -21.299 |
| sac_s1 | 7 | -38.344 | -21.120 |
| sac_s2 | 7 | -38.470 | -21.189 |

Infeasible seeds (min margin): 70012 (0.69), 70013 (0.77), 70016 (0.98), 70022 (0.69), 70057 (0.79), 70065 (0.55), 70088 (0.43)

## Verdict

**Primary** (static, feasible, n=93): validation-selected SAC (`sac_s0`) is MIXED against (the median CI excludes zero, direction positive, but the Wilcoxon test is not significant) the best constant gains: paired median difference of return +0.253, 95 % CI [+0.120, +0.315] (Wilcoxon p = 0.116, single primary test, unadjusted; analysis status: confirmatory).

Secondary comparisons against best_constant with Holm-adjusted p < 0.05: static/tuned (p=2.1e-12), static/legacy (p=4.6e-15), static/zn (p=1.4e-08), static/random_search (p=1.6e-15), static/sac_s2 (p=0.0011), changes/tuned (p=2.6e-12), changes/legacy (p=2.2e-14), changes/zn (p=9.7e-05), changes/random_search (p=2e-14), changes/ppo (p=0.00041), changes/sac_s0 (p=0.00041), changes/sac_s1 (p=5.2e-07), changes/sac_s2 (p=4.2e-08), ood/tuned (p=8e-07), ood/legacy (p=4.1e-15), ood/zn (p=5.7e-10), ood/random_search (p=1.6e-15), ood/ppo (p=0.029), ood/sac_s0 (p=0.029), ood/sac_s2 (p=0.0081). The sign of the median difference in the tables gives the direction.

Everything above is simulated on the preliminary twin and has not been validated on hardware.
