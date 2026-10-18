# Controller comparison (PRE-VALIDATION, simulated on the unvalidated twin)

100 held-out paired TEST scenarios per regime (seeds 50000..50099); 40 VALIDATION scenarios (seeds 40000..40039) were used to choose `best_constant` and the reported PPO seed; neither set was used in training. Every controller sees the same plant, payload, target, delay and noise for a given seed. `return` is the environment reward (higher is better).
`random_search` is an ORACLE (best of 48 random sets + a 20-point Ki = 0 grid + Tuned + bandit + best_constant per scenario, chosen with hindsight): an upper bound for any adaptive tuner of this kind, not a deployable controller. Primary metric: episode return (success rate is descriptive).

**Analysis status: pre-specified.** One primary comparison: validation-selected PPO minus `best_constant`, `static` regime, feasible scenarios, paired median difference of return with a 95 % bootstrap CI. All other comparisons are secondary: paired Wilcoxon p-values, Holm-adjusted across the whole secondary family (feasible scenarios, all regimes). Infeasible scenarios (torque margin < 1.0 at any point, including after a payload change) are reported separately.

## Regime `static`

Best constant gains (chosen on validation): Kp 18.94, Ki 0.01, Kd 1.317 (validation return -8.099).
PPO seeds, validation mean return: ppo_s0 -10.251, ppo_s1 -9.508, ppo_s2 -9.645, ppo_s3 -10.359, ppo_s4 -9.895. Selected on validation: `ppo_s1`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 94 feasible scenarios of 100, the 6 infeasible ones are tabulated separately below.

Feasible scenarios: 94 of 100; infeasible: 6.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -11.596 ± 9.104 | -9.278 | -2.611 [-3.882, -1.688] | -3.665 [-4.406, -2.953] | [-5.736, -1.003] | 7.85e-15 | 1.96e-13 | 35.2 | 19.5 | 1.026 | 13 % | 0 % | 0 % |
| legacy | -54.669 ± 51.614 | -36.098 | -28.032 [-43.053, -20.570] | -46.738 [-57.542, -37.176] | [-59.444, -13.684] | 9.33e-17 | 2.89e-15 | 76.5 | 58.4 | 1.384 | 2 % | 0 % | 0 % |
| best_constant | -7.931 ± 8.108 | -5.822 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 29.9 | 4.5 | 0.585 | 54 % | 0 % | 0 % |
| zn | -16.884 ± 24.305 | -6.675 | -1.207 [-1.481, -1.095] | -8.953 [-13.704, -4.913] | [-2.566, -0.877] | 4.35e-12 | 7.39e-11 | 52.4 | 10.1 | 0.656 | 46 % | 100 % | 0 % |
| bandit | -7.951 ± 8.143 | -5.914 | -0.162 [-0.236, -0.050] | -0.020 [-0.274, +0.256] | [-0.388, +0.158] | 0.0247 | 0.124 | 27.0 | 6.8 | 0.534 | 63 % | 37 % | 0 % |
| bandit_retune | -7.951 ± 8.143 | -5.914 | -0.162 [-0.236, -0.050] | -0.020 [-0.274, +0.256] | [-0.388, +0.158] | 0.0247 | 0.124 | 27.0 | 6.8 | 0.534 | 63 % | 37 % | 0 % |
| random_search | -6.534 ± 7.991 | -4.968 | +0.813 [+0.675, +1.108] | +1.397 [+1.158, +1.671] | [+0.478, +1.939] | 3.81e-17 | 1.33e-15 | 28.8 | 0.7 | 0.556 | 85 % | 39 % | 0 % |
| ppo (selected) **(primary)** | -9.663 ± 7.746 | -7.292 | -1.751 [-2.003, -1.526] | -1.732 [-2.060, -1.388] | [-2.437, -1.261] | 7.48e-13 | nan | 28.4 | 11.0 | 0.701 | 31 % | 100 % | 0 % |
| ppo_s0 | -11.167 ± 8.289 | -8.520 | -2.633 [-3.614, -2.282] | -3.236 [-3.777, -2.704] | [-4.996, -1.613] | 6e-15 | 1.56e-13 | 30.0 | 17.1 | 0.936 | 20 % | 100 % | 0 % |
| ppo_s1 | -9.663 ± 7.746 | -7.292 | -1.751 [-2.003, -1.526] | -1.732 [-2.060, -1.388] | [-2.437, -1.261] | 7.48e-13 | 1.35e-11 | 28.4 | 11.0 | 0.701 | 31 % | 100 % | 0 % |
| ppo_s2 | -9.602 ± 7.704 | -7.775 | -1.723 [-1.939, -1.576] | -1.671 [-1.939, -1.396] | [-2.443, -1.172] | 8.85e-14 | 1.95e-12 | 28.8 | 8.1 | 0.607 | 44 % | 100 % | 0 % |
| ppo_s3 | -10.299 ± 7.808 | -7.836 | -2.224 [-2.381, -1.943] | -2.368 [-2.596, -2.145] | [-3.136, -1.696] | 4.47e-17 | 1.48e-15 | 28.5 | 11.3 | 1.028 | 46 % | 100 % | 0 % |
| ppo_s4 | -10.911 ± 8.452 | -8.051 | -2.441 [-3.420, -2.020] | -2.980 [-3.544, -2.418] | [-4.790, -1.212] | 9.11e-14 | 1.95e-12 | 30.4 | 17.9 | 0.752 | 18 % | 100 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +1.397 (17.6 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected -124 %; per seed ppo_s0 -232 %, ppo_s1 -124 %, ppo_s2 -120 %, ppo_s3 -169 %, ppo_s4 -213 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.162 [-0.236, -0.050].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -11.167, ppo_s1 -9.663, ppo_s2 -9.602, ppo_s3 -10.299, ppo_s4 -10.911. Seed mean -10.328, std 0.635, range [-11.167, -9.602]; best constant -7.931.

### Infeasible scenarios (reported separately)

| controller | n | return mean | median |
|---|---|---|---|
| tuned | 6 | -57.700 | -58.332 |
| legacy | 6 | -57.210 | -58.332 |
| best_constant | 6 | -57.515 | -58.657 |
| zn | 6 | -83.740 | -94.188 |
| bandit | 6 | -57.072 | -58.332 |
| bandit_retune | 6 | -57.072 | -58.332 |
| random_search | 6 | -57.068 | -58.332 |
| ppo (selected) | 6 | -57.634 | -58.878 |
| ppo_s0 | 6 | -57.634 | -58.892 |
| ppo_s1 | 6 | -57.634 | -58.878 |
| ppo_s2 | 6 | -57.690 | -58.913 |
| ppo_s3 | 6 | -57.642 | -58.884 |
| ppo_s4 | 6 | -57.625 | -58.824 |

Infeasible seeds (min margin): 50017 (0.81), 50024 (0.66), 50041 (0.67), 50064 (0.55), 50079 (0.52), 50081 (0.63)

## Regime `changes`

Best constant gains (chosen on validation): Kp 29.59, Ki 0.01, Kd 1.317 (validation return -19.770).
PPO seeds, validation mean return: ppo_s0 -21.950, ppo_s1 -22.029, ppo_s2 -21.697, ppo_s3 -21.419, ppo_s4 -21.524. Selected on validation: `ppo_s3`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 89 feasible scenarios of 100, the 11 infeasible ones are tabulated separately below.

Note: in this regime the target and payload change mid-episode, so overshoot, settling and success refer to the final target only; the return is the headline.

Feasible scenarios: 89 of 100; infeasible: 11.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -28.791 ± 27.314 | -21.237 | -5.713 [-7.290, -3.636] | -7.476 [-9.452, -5.769] | [-10.458, -1.752] | 9.76e-14 | 1.95e-12 | 63.5 | 70.4 | 1.337 | 16 % | 0 % | 0 % |
| legacy | -95.526 ± 78.509 | -72.824 | -56.103 [-69.435, -41.227] | -74.211 [-89.771, -60.724] | [-94.733, -23.573] | 3.96e-16 | 1.15e-14 | 95.7 | 118.4 | 1.614 | 0 % | 0 % | 0 % |
| best_constant | -21.315 ± 23.926 | -13.900 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 57.0 | 56.5 | 1.100 | 34 % | 0 % | 0 % |
| zn | -29.423 ± 34.572 | -14.655 | -0.878 [-1.088, -0.618] | -8.108 [-14.174, -3.421] | [-1.694, -0.087] | 1.1e-05 | 8.82e-05 | 67.2 | 53.2 | 1.150 | 39 % | 100 % | 0 % |
| bandit | -20.189 ± 23.629 | -12.751 | +0.325 [+0.110, +0.890] | +1.126 [+0.543, +1.739] | [-0.067, +1.534] | 6.34e-06 | 5.7e-05 | 55.3 | 55.8 | 1.099 | 45 % | 37 % | 0 % |
| bandit_retune | -20.493 ± 23.419 | -13.424 | +0.039 [-0.362, +0.326] | +0.822 [+0.205, +1.505] | [-0.777, +1.113] | 0.348 | 1 | 54.9 | 56.0 | 1.111 | 49 % | 40 % | 0 % |
| random_search | -13.944 ± 13.142 | -10.507 | +2.221 [+1.383, +3.742] | +7.371 [+4.742, +10.593] | [+0.693, +6.547] | 2.55e-16 | 7.65e-15 | 48.4 | 18.9 | 0.998 | 58 % | 47 % | 0 % |
| ppo (selected) | -22.294 ± 23.348 | -14.663 | -1.349 [-1.676, -1.189] | -0.979 [-1.495, -0.406] | [-2.145, -0.467] | 2.05e-06 | 2.26e-05 | 56.0 | 59.1 | 1.434 | 45 % | 100 % | 0 % |
| ppo_s0 | -23.397 ± 23.437 | -16.104 | -2.329 [-2.900, -1.767] | -2.082 [-2.785, -1.359] | [-3.687, -1.273] | 8.43e-08 | 1.01e-06 | 56.7 | 65.7 | 1.330 | 30 % | 100 % | 0 % |
| ppo_s1 | -23.031 ± 26.142 | -15.073 | -1.418 [-1.886, -0.989] | -1.716 [-3.122, -0.516] | [-3.050, -0.045] | 0.000405 | 0.00283 | 57.1 | 58.4 | 1.211 | 30 % | 100 % | 0 % |
| ppo_s2 | -22.049 ± 25.665 | -13.980 | -1.530 [-1.898, -1.228] | -0.734 [-2.488, +1.307] | [-2.644, -0.026] | 0.000431 | 0.00283 | 55.9 | 54.1 | 1.126 | 26 % | 94 % | 0 % |
| ppo_s3 | -22.294 ± 23.348 | -14.663 | -1.349 [-1.676, -1.189] | -0.979 [-1.495, -0.406] | [-2.145, -0.467] | 2.05e-06 | 2.26e-05 | 56.0 | 59.1 | 1.434 | 45 % | 100 % | 0 % |
| ppo_s4 | -24.169 ± 25.596 | -16.145 | -1.837 [-2.914, -1.438] | -2.854 [-3.979, -1.862] | [-4.514, -0.818] | 3.37e-08 | 4.38e-07 | 57.5 | 67.6 | 1.138 | 29 % | 100 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +7.371 (34.6 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected -13 %; per seed ppo_s0 -28 %, ppo_s1 -23 %, ppo_s2 -10 %, ppo_s3 -13 %, ppo_s4 -39 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): +0.325 [+0.110, +0.890].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -23.397, ppo_s1 -23.031, ppo_s2 -22.049, ppo_s3 -22.294, ppo_s4 -24.169. Seed mean -22.988, std 0.765, range [-24.169, -22.049]; best constant -21.315.

### Infeasible scenarios (reported separately)

| controller | n | return mean | median |
|---|---|---|---|
| tuned | 11 | -80.530 | -52.124 |
| legacy | 11 | -183.830 | -49.490 |
| best_constant | 11 | -115.307 | -40.569 |
| zn | 11 | -97.332 | -97.678 |
| bandit | 11 | -114.615 | -42.017 |
| bandit_retune | 11 | -114.535 | -42.049 |
| random_search | 11 | -44.003 | -38.277 |
| ppo (selected) | 11 | -119.518 | -43.883 |
| ppo_s0 | 11 | -118.783 | -35.654 |
| ppo_s1 | 11 | -120.570 | -42.208 |
| ppo_s2 | 11 | -119.525 | -44.431 |
| ppo_s3 | 11 | -119.518 | -43.883 |
| ppo_s4 | 11 | -117.730 | -38.713 |

Infeasible seeds (min margin): 50017 (0.81), 50024 (0.66), 50031 (0.58), 50041 (0.67), 50042 (0.83), 50046 (0.68), 50052 (0.75), 50064 (0.46), 50079 (0.52), 50081 (0.63), 50083 (0.98)

## Regime `ood`

Best constant gains (chosen on validation): Kp 23.67, Ki 0.01, Kd 1.317 (validation return -10.173).
PPO seeds, validation mean return: ppo_s0 -12.190, ppo_s1 -11.740, ppo_s2 -11.714, ppo_s3 -12.387, ppo_s4 -11.686. Selected on validation: `ppo_s4`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 94 feasible scenarios of 100, the 6 infeasible ones are tabulated separately below.

Feasible scenarios: 94 of 100; infeasible: 6.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -14.029 ± 14.512 | -9.385 | -2.072 [-3.466, -1.021] | -3.609 [-4.595, -2.655] | [-5.060, -0.139] | 7.39e-12 | 1.18e-10 | 40.7 | 17.5 | 0.872 | 23 % | 0 % | 0 % |
| legacy | -55.589 ± 55.621 | -35.247 | -21.791 [-35.817, -17.132] | -45.168 [-56.997, -34.521] | [-60.348, -11.775] | 7.71e-17 | 2.47e-15 | 78.1 | 55.1 | 1.372 | 1 % | 0 % | 0 % |
| best_constant | -10.420 ± 13.072 | -6.216 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 35.0 | 6.7 | 0.632 | 49 % | 0 % | 0 % |
| zn | -18.265 ± 24.330 | -7.147 | -1.289 [-1.539, -1.063] | -7.845 [-11.903, -4.325] | [-2.307, -0.738] | 5.83e-13 | 1.11e-11 | 55.1 | 10.9 | 0.781 | 48 % | 100 % | 0 % |
| bandit | -10.344 ± 13.110 | -6.137 | -0.093 [-0.155, -0.045] | +0.077 [-0.130, +0.300] | [-0.247, +0.287] | 0.381 | 1 | 33.0 | 7.5 | 0.628 | 63 % | 37 % | 0 % |
| bandit_retune | -10.344 ± 13.110 | -6.137 | -0.093 [-0.155, -0.045] | +0.077 [-0.130, +0.300] | [-0.247, +0.287] | 0.381 | 1 | 33.0 | 7.5 | 0.628 | 63 % | 37 % | 0 % |
| random_search | -8.392 ± 12.741 | -5.176 | +0.943 [+0.820, +1.292] | +2.029 [+1.541, +2.611] | [+0.598, +2.296] | 3.81e-17 | 1.33e-15 | 34.7 | 0.9 | 0.625 | 85 % | 35 % | 0 % |
| ppo (selected) | -13.225 ± 13.589 | -8.026 | -1.993 [-2.663, -1.558] | -2.804 [-3.447, -2.208] | [-4.190, -0.868] | 2.95e-14 | 7.09e-13 | 36.2 | 16.3 | 0.776 | 28 % | 100 % | 0 % |
| ppo_s0 | -13.416 ± 13.238 | -8.403 | -2.164 [-3.022, -1.812] | -2.996 [-3.550, -2.444] | [-4.361, -1.387] | 4.87e-15 | 1.31e-13 | 35.7 | 15.6 | 0.991 | 33 % | 100 % | 0 % |
| ppo_s1 | -11.874 ± 12.480 | -7.858 | -1.504 [-1.820, -1.311] | -1.454 [-1.844, -1.018] | [-2.355, -0.770] | 9.15e-11 | 1.37e-09 | 34.3 | 10.4 | 0.686 | 33 % | 100 % | 0 % |
| ppo_s2 | -11.645 ± 12.391 | -8.384 | -1.768 [-1.941, -1.489] | -1.225 [-1.637, -0.704] | [-2.273, -0.646] | 1.4e-10 | 1.96e-09 | 34.6 | 7.6 | 0.704 | 40 % | 100 % | 0 % |
| ppo_s3 | -12.568 ± 12.643 | -8.387 | -2.067 [-2.275, -1.787] | -2.147 [-2.432, -1.849] | [-2.853, -1.390] | 1.03e-15 | 2.9e-14 | 34.4 | 10.8 | 1.198 | 53 % | 100 % | 0 % |
| ppo_s4 | -13.225 ± 13.589 | -8.026 | -1.993 [-2.663, -1.558] | -2.804 [-3.447, -2.208] | [-4.190, -0.868] | 2.95e-14 | 7.09e-13 | 36.2 | 16.3 | 0.776 | 28 % | 100 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +2.029 (19.5 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected -138 %; per seed ppo_s0 -148 %, ppo_s1 -72 %, ppo_s2 -60 %, ppo_s3 -106 %, ppo_s4 -138 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.093 [-0.155, -0.045].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -13.416, ppo_s1 -11.874, ppo_s2 -11.645, ppo_s3 -12.568, ppo_s4 -13.225. Seed mean -12.545, std 0.704, range [-13.416, -11.645]; best constant -10.420.

### Infeasible scenarios (reported separately)

| controller | n | return mean | median |
|---|---|---|---|
| tuned | 6 | -57.792 | -60.289 |
| legacy | 6 | -57.055 | -60.304 |
| best_constant | 6 | -57.318 | -60.614 |
| zn | 6 | -83.731 | -95.146 |
| bandit | 6 | -56.998 | -60.289 |
| bandit_retune | 6 | -56.998 | -60.289 |
| random_search | 6 | -56.957 | -60.289 |
| ppo (selected) | 6 | -57.477 | -60.785 |
| ppo_s0 | 6 | -57.567 | -60.845 |
| ppo_s1 | 6 | -57.554 | -60.842 |
| ppo_s2 | 6 | -57.541 | -60.872 |
| ppo_s3 | 6 | -57.523 | -60.853 |
| ppo_s4 | 6 | -57.477 | -60.785 |

Infeasible seeds (min margin): 50017 (0.81), 50024 (0.66), 50041 (0.67), 50064 (0.55), 50079 (0.52), 50081 (0.63)

## Verdict

**Primary** (static, feasible, n=94): validation-selected PPO (`ppo_s1`) is WORSE than the best constant gains: paired median difference of return -1.751, 95 % CI [-2.003, -1.526] (Wilcoxon p = 7.48e-13, single primary test, unadjusted; analysis status: pre-specified).

Secondary comparisons against best_constant with Holm-adjusted p < 0.05: static/tuned (p=2e-13), static/legacy (p=2.9e-15), static/zn (p=7.4e-11), static/random_search (p=1.3e-15), static/ppo_s0 (p=1.6e-13), static/ppo_s1 (p=1.3e-11), static/ppo_s2 (p=1.9e-12), static/ppo_s3 (p=1.5e-15), static/ppo_s4 (p=1.9e-12), changes/tuned (p=2e-12), changes/legacy (p=1.1e-14), changes/zn (p=8.8e-05), changes/bandit (p=5.7e-05), changes/random_search (p=7.7e-15), changes/ppo (p=2.3e-05), changes/ppo_s0 (p=1e-06), changes/ppo_s1 (p=0.0028), changes/ppo_s2 (p=0.0028), changes/ppo_s3 (p=2.3e-05), changes/ppo_s4 (p=4.4e-07), ood/tuned (p=1.2e-10), ood/legacy (p=2.5e-15), ood/zn (p=1.1e-11), ood/random_search (p=1.3e-15), ood/ppo (p=7.1e-13), ood/ppo_s0 (p=1.3e-13), ood/ppo_s1 (p=1.4e-09), ood/ppo_s2 (p=2e-09), ood/ppo_s3 (p=2.9e-14), ood/ppo_s4 (p=7.1e-13). The sign of the median difference in the tables gives the direction.

Everything above is simulated on the preliminary twin and has not been validated on hardware.
