# Controller comparison (PRE-VALIDATION, simulated on the unvalidated twin)

100 held-out paired TEST scenarios per regime (seeds 70000..70099); 40 VALIDATION scenarios (seeds 40000..40039) were used to choose `best_constant` and the reported PPO seed; neither set was used in training. Every controller sees the same plant, payload, target, delay and noise for a given seed. `return` is the environment reward (higher is better).
`random_search` is an ORACLE (best of 48 random sets + a 20-point Ki = 0 grid + Tuned + bandit + best_constant per scenario, chosen with hindsight): an upper bound for any adaptive tuner of this kind, not a deployable controller. Primary metric: episode return (success rate is descriptive).

**Analysis status: confirmatory.** These seeds were not used to train, select or tune anything; they confirm (or not) a design fixed earlier. Nothing may be re-tuned on them. One primary comparison: validation-selected PPO minus `best_constant`, `static` regime, feasible scenarios, paired median difference of return with a 95 % bootstrap CI. All other comparisons are secondary: paired Wilcoxon p-values, Holm-adjusted across the whole secondary family (feasible scenarios, all regimes). Infeasible scenarios (torque margin < 1.0 at any point, including after a payload change) are reported separately.

## Regime `static`

Best constant gains (chosen on validation): Kp 18.94, Ki 0.01, Kd 1.317 (validation return -8.099).
PPO seeds, validation mean return: td3_s0 -9.114, td3_s1 -8.975, td3_s2 -8.124. Selected on validation: `td3_s2`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 93 feasible scenarios of 100, the 7 infeasible ones are tabulated separately below.

Feasible scenarios: 93 of 100; infeasible: 7.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -10.072 ± 9.102 | -7.088 | -1.617 [-2.694, -1.190] | -2.713 [-3.416, -2.079] | [-3.997, -0.365] | 9.3e-14 | 2.14e-12 | 32.9 | 16.2 | 0.783 | 20 % | 0 % | 0 % |
| legacy | -45.726 ± 70.121 | -24.785 | -18.995 [-26.105, -15.374] | -38.366 [-53.995, -26.635] | [-39.091, -11.671] | 1.78e-16 | 4.63e-15 | 63.2 | 52.9 | 1.356 | 2 % | 0 % | 0 % |
| best_constant | -7.359 ± 8.164 | -5.412 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 29.5 | 2.9 | 0.523 | 66 % | 0 % | 0 % |
| zn | -16.948 ± 24.872 | -6.258 | -1.132 [-1.374, -1.034] | -9.588 [-14.302, -5.611] | [-2.020, -0.886] | 7.13e-10 | 1.07e-08 | 55.9 | 7.8 | 0.615 | 56 % | 100 % | 0 % |
| bandit | -7.115 ± 8.064 | -5.323 | -0.114 [-0.191, -0.073] | +0.245 [-0.150, +0.746] | [-0.398, +0.058] | 0.0141 | 0.127 | 25.8 | 5.6 | 0.509 | 77 % | 26 % | 0 % |
| bandit_retune | -7.115 ± 8.064 | -5.323 | -0.114 [-0.191, -0.073] | +0.245 [-0.150, +0.746] | [-0.398, +0.058] | 0.0141 | 0.127 | 25.8 | 5.6 | 0.509 | 77 % | 26 % | 0 % |
| random_search | -5.958 ± 7.901 | -4.503 | +0.736 [+0.565, +0.840] | +1.401 [+1.025, +1.883] | [+0.470, +1.223] | 5.57e-17 | 1.62e-15 | 27.9 | 1.1 | 0.509 | 78 % | 26 % | 0 % |
| td3 (selected) **(primary)** | -7.193 ± 7.872 | -5.434 | -0.170 [-0.285, +0.089] | +0.166 [-0.092, +0.447] | [-0.639, +0.541] | 0.874 | nan | 30.1 | 1.6 | 0.694 | 77 % | 0 % | 0 % |
| td3_s0 | -8.508 ± 8.301 | -6.244 | -1.019 [-1.152, -0.842] | -1.149 [-1.569, -0.734] | [-1.605, -0.716] | 7.43e-11 | 1.19e-09 | 28.1 | 4.7 | 0.550 | 62 % | 0 % | 0 % |
| td3_s1 | -8.423 ± 8.270 | -6.277 | -0.704 [-0.848, -0.463] | -1.063 [-1.402, -0.744] | [-1.364, -0.149] | 7.31e-10 | 1.07e-08 | 29.8 | 1.9 | 0.528 | 70 % | 0 % | 0 % |
| td3_s2 | -7.193 ± 7.872 | -5.434 | -0.170 [-0.285, +0.089] | +0.166 [-0.092, +0.447] | [-0.639, +0.541] | 0.874 | 1 | 30.1 | 1.6 | 0.694 | 77 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +1.401 (19.0 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected 12 %; per seed td3_s0 -82 %, td3_s1 -76 %, td3_s2 12 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.114 [-0.191, -0.073].

TD3 across training seeds (feasible test scenarios, mean return): td3_s0 -8.508, td3_s1 -8.423, td3_s2 -7.193. Seed mean -8.041, std 0.601, range [-8.508, -7.193]; best constant -7.359.

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
| td3 (selected) | 7 | -41.938 | -43.628 |
| td3_s0 | 7 | -42.193 | -44.601 |
| td3_s1 | 7 | -43.717 | -43.185 |
| td3_s2 | 7 | -41.938 | -43.628 |

Infeasible seeds (min margin): 70012 (0.69), 70013 (0.77), 70016 (0.98), 70022 (0.69), 70057 (0.79), 70065 (0.55), 70088 (0.43)

## Regime `changes`

Best constant gains (chosen on validation): Kp 29.59, Ki 0.01, Kd 1.317 (validation return -19.770).
PPO seeds, validation mean return: td3_s0 -22.454, td3_s1 -25.517, td3_s2 -22.507. Selected on validation: `td3_s0`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 86 feasible scenarios of 100, the 14 infeasible ones are tabulated separately below.

Note: in this regime the target and payload change mid-episode, so overshoot, settling and success refer to the final target only; the return is the headline.

Feasible scenarios: 86 of 100; infeasible: 14.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -27.295 ± 40.380 | -16.422 | -3.227 [-4.758, -1.756] | -7.401 [-11.870, -4.525] | [-8.123, -0.854] | 1.2e-13 | 2.63e-12 | 59.8 | 49.3 | 1.286 | 19 % | 0 % | 0 % |
| legacy | -88.413 ± 109.533 | -50.379 | -34.145 [-39.606, -27.631] | -68.519 [-92.698, -48.474] | [-68.759, -17.921] | 9.2e-16 | 2.21e-14 | 86.0 | 90.5 | 1.692 | 2 % | 0 % | 0 % |
| best_constant | -19.894 ± 34.807 | -11.532 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 53.9 | 38.4 | 1.060 | 36 % | 0 % | 0 % |
| zn | -27.411 ± 35.287 | -11.943 | -0.961 [-1.190, -0.638] | -7.517 [-15.121, -0.518] | [-1.960, -0.246] | 6.08e-06 | 6.08e-05 | 70.2 | 35.2 | 1.124 | 45 % | 100 % | 0 % |
| bandit | -19.596 ± 35.789 | -10.083 | -0.052 [-0.115, +0.069] | +0.297 [-0.316, +0.873] | [-0.251, +0.850] | 0.383 | 1 | 52.3 | 38.8 | 1.067 | 50 % | 24 % | 0 % |
| bandit_retune | -20.049 ± 35.901 | -10.524 | -0.527 [-0.795, -0.237] | -0.155 [-0.813, +0.459] | [-0.947, +0.436] | 0.0676 | 0.471 | 52.0 | 39.0 | 1.080 | 53 % | 34 % | 0 % |
| random_search | -12.908 ± 14.550 | -9.040 | +1.337 [+0.919, +2.225] | +6.986 [+3.234, +11.897] | [+0.641, +4.390] | 7.99e-16 | 2e-14 | 49.3 | 15.6 | 0.999 | 64 % | 41 % | 0 % |
| td3 (selected) | -21.951 ± 32.746 | -14.473 | -2.126 [-2.499, -1.823] | -2.058 [-2.907, -0.720] | [-3.699, -1.169] | 2.36e-13 | 4.96e-12 | 54.4 | 37.8 | 1.112 | 40 % | 0 % | 0 % |
| td3_s0 | -21.951 ± 32.746 | -14.473 | -2.126 [-2.499, -1.823] | -2.058 [-2.907, -0.720] | [-3.699, -1.169] | 2.36e-13 | 4.96e-12 | 54.4 | 37.8 | 1.112 | 40 % | 0 % | 0 % |
| td3_s1 | -25.041 ± 34.732 | -13.586 | -2.385 [-4.082, -1.886] | -5.147 [-7.162, -3.438] | [-6.747, -1.333] | 3.69e-11 | 6.27e-10 | 56.4 | 34.8 | 1.089 | 43 % | 0 % | 0 % |
| td3_s2 | -21.819 ± 33.330 | -11.662 | -1.493 [-2.137, -0.804] | -1.925 [-3.186, -0.558] | [-4.107, -0.057] | 2.83e-06 | 3.11e-05 | 55.0 | 34.7 | 1.109 | 43 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +6.986 (35.1 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected -29 %; per seed td3_s0 -29 %, td3_s1 -74 %, td3_s2 -28 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.052 [-0.115, +0.069].

TD3 across training seeds (feasible test scenarios, mean return): td3_s0 -21.951, td3_s1 -25.041, td3_s2 -21.819. Seed mean -22.937, std 1.488, range [-25.041, -21.819]; best constant -19.894.

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
| td3 (selected) | 14 | -54.664 | -43.643 |
| td3_s0 | 14 | -54.664 | -43.643 |
| td3_s1 | 14 | -106.143 | -59.616 |
| td3_s2 | 14 | -63.471 | -38.135 |

Infeasible seeds (min margin): 70012 (0.69), 70013 (0.77), 70016 (0.98), 70021 (0.79), 70022 (0.69), 70031 (0.65), 70056 (0.81), 70057 (0.79), 70065 (0.55), 70072 (0.46), 70076 (0.74), 70079 (0.97)...

## Regime `ood`

Best constant gains (chosen on validation): Kp 23.67, Ki 0.01, Kd 1.317 (validation return -10.173).
PPO seeds, validation mean return: td3_s0 -11.198, td3_s1 -11.587, td3_s2 -10.265. Selected on validation: `td3_s2`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 93 feasible scenarios of 100, the 7 infeasible ones are tabulated separately below.

Feasible scenarios: 93 of 100; infeasible: 7.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -11.633 ± 13.324 | -7.024 | -1.032 [-1.854, -0.295] | -2.668 [-3.716, -1.806] | [-4.268, +0.341] | 4.71e-08 | 6.12e-07 | 37.0 | 13.3 | 0.719 | 33 % | 0 % | 0 % |
| legacy | -47.064 ± 77.044 | -22.377 | -15.665 [-21.897, -11.182] | -38.099 [-55.320, -25.471] | [-33.642, -9.201] | 1.52e-16 | 4.1e-15 | 63.2 | 46.7 | 1.354 | 2 % | 0 % | 0 % |
| best_constant | -8.965 ± 11.556 | -5.606 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 33.2 | 4.4 | 0.570 | 63 % | 0 % | 0 % |
| zn | -17.473 ± 24.287 | -6.401 | -1.208 [-1.482, -1.022] | -8.508 [-12.789, -4.982] | [-2.252, -0.703] | 2.72e-11 | 4.89e-10 | 57.1 | 8.4 | 0.645 | 57 % | 100 % | 0 % |
| bandit | -8.642 ± 11.364 | -5.395 | -0.101 [-0.149, -0.033] | +0.323 [-0.081, +0.872] | [-0.252, +0.125] | 0.0673 | 0.471 | 30.8 | 5.9 | 0.542 | 73 % | 26 % | 0 % |
| bandit_retune | -8.642 ± 11.364 | -5.395 | -0.101 [-0.149, -0.033] | +0.323 [-0.081, +0.872] | [-0.252, +0.125] | 0.0673 | 0.471 | 30.8 | 5.9 | 0.542 | 73 % | 26 % | 0 % |
| random_search | -7.176 ± 11.120 | -4.827 | +0.796 [+0.744, +0.952] | +1.789 [+1.282, +2.443] | [+0.638, +1.453] | 5.57e-17 | 1.62e-15 | 32.7 | 1.0 | 0.560 | 78 % | 26 % | 0 % |
| td3 (selected) | -8.773 ± 11.214 | -5.561 | -0.100 [-0.258, +0.043] | +0.192 [-0.133, +0.539] | [-0.662, +0.473] | 0.556 | 1 | 34.8 | 2.2 | 0.694 | 73 % | 0 % | 0 % |
| td3_s0 | -10.178 ± 11.804 | -6.477 | -0.888 [-1.021, -0.792] | -1.213 [-1.679, -0.811] | [-1.258, -0.668] | 1.41e-11 | 2.68e-10 | 32.8 | 5.1 | 0.564 | 62 % | 0 % | 0 % |
| td3_s1 | -10.286 ± 11.833 | -6.560 | -0.704 [-0.854, -0.427] | -1.321 [-1.844, -0.841] | [-1.729, +0.017] | 6.1e-08 | 7.32e-07 | 34.6 | 2.7 | 0.603 | 68 % | 0 % | 0 % |
| td3_s2 | -8.773 ± 11.214 | -5.561 | -0.100 [-0.258, +0.043] | +0.192 [-0.133, +0.539] | [-0.662, +0.473] | 0.556 | 1 | 34.8 | 2.2 | 0.694 | 73 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +1.789 (20.0 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected 11 %; per seed td3_s0 -68 %, td3_s1 -74 %, td3_s2 11 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.101 [-0.149, -0.033].

TD3 across training seeds (feasible test scenarios, mean return): td3_s0 -10.178, td3_s1 -10.286, td3_s2 -8.773. Seed mean -9.746, std 0.689, range [-10.286, -8.773]; best constant -8.965.

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
| td3 (selected) | 7 | -38.595 | -22.199 |
| td3_s0 | 7 | -38.898 | -23.145 |
| td3_s1 | 7 | -39.982 | -22.091 |
| td3_s2 | 7 | -38.595 | -22.199 |

Infeasible seeds (min margin): 70012 (0.69), 70013 (0.77), 70016 (0.98), 70022 (0.69), 70057 (0.79), 70065 (0.55), 70088 (0.43)

## Verdict

**Primary** (static, feasible, n=93): validation-selected TD3 (`td3_s2`) is NOT distinguishable from the best constant gains: paired median difference of return -0.170, 95 % CI [-0.285, +0.089] (Wilcoxon p = 0.874, single primary test, unadjusted; analysis status: confirmatory).

Secondary comparisons against best_constant with Holm-adjusted p < 0.05: static/tuned (p=2.1e-12), static/legacy (p=4.6e-15), static/zn (p=1.1e-08), static/random_search (p=1.6e-15), static/td3_s0 (p=1.2e-09), static/td3_s1 (p=1.1e-08), changes/tuned (p=2.6e-12), changes/legacy (p=2.2e-14), changes/zn (p=6.1e-05), changes/random_search (p=2e-14), changes/ppo (p=5e-12), changes/td3_s0 (p=5e-12), changes/td3_s1 (p=6.3e-10), changes/td3_s2 (p=3.1e-05), ood/tuned (p=6.1e-07), ood/legacy (p=4.1e-15), ood/zn (p=4.9e-10), ood/random_search (p=1.6e-15), ood/td3_s0 (p=2.7e-10), ood/td3_s1 (p=7.3e-07). The sign of the median difference in the tables gives the direction.

Everything above is simulated on the preliminary twin and has not been validated on hardware.
