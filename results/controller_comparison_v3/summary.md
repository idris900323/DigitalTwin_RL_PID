# Controller comparison (PRE-VALIDATION, simulated on the unvalidated twin)

100 held-out paired TEST scenarios per regime (seeds 50000..50099); 40 VALIDATION scenarios (seeds 40000..40039) were used to choose `best_constant` and the reported PPO seed; neither set was used in training. Every controller sees the same plant, payload, target, delay and noise for a given seed. `return` is the environment reward (higher is better).
`random_search` is an ORACLE (best of 48 random sets + a 20-point Ki = 0 grid + Tuned + bandit + best_constant per scenario, chosen with hindsight): an upper bound for any adaptive tuner of this kind, not a deployable controller. Primary metric: episode return (success rate is descriptive).

**Analysis status: exploratory.** The policy design under test was chosen after seeing results on an earlier test set that overlaps these seeds, so this set is exploratory, not confirmatory. One primary comparison: validation-selected PPO minus `best_constant`, `static` regime, feasible scenarios, paired median difference of return with a 95 % bootstrap CI. All other comparisons are secondary: paired Wilcoxon p-values, Holm-adjusted across the whole secondary family (feasible scenarios, all regimes). Infeasible scenarios (torque margin < 1.0 at any point, including after a payload change) are reported separately.

## Regime `static`

Best constant gains (chosen on validation): Kp 18.94, Ki 0.01, Kd 1.317 (validation return -8.099).
PPO seeds, validation mean return: ppo_s0 -7.671, ppo_s1 -7.489, ppo_s2 -7.671. Selected on validation: `ppo_s1`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 94 feasible scenarios of 100, the 6 infeasible ones are tabulated separately below.

Feasible scenarios: 94 of 100; infeasible: 6.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -11.596 ± 9.104 | -9.278 | -2.611 [-3.882, -1.688] | -3.665 [-4.406, -2.953] | [-5.736, -1.003] | 7.85e-15 | 1.73e-13 | 35.2 | 19.5 | 1.026 | 13 % | 0 % | 0 % |
| legacy | -54.669 ± 51.614 | -36.098 | -28.032 [-43.053, -20.570] | -46.738 [-57.542, -37.176] | [-59.444, -13.684] | 9.33e-17 | 2.33e-15 | 76.5 | 58.4 | 1.384 | 2 % | 0 % | 0 % |
| best_constant | -7.931 ± 8.108 | -5.822 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 29.9 | 4.5 | 0.585 | 54 % | 0 % | 0 % |
| zn | -16.884 ± 24.305 | -6.675 | -1.207 [-1.481, -1.095] | -8.953 [-13.704, -4.913] | [-2.566, -0.877] | 4.35e-12 | 6.52e-11 | 52.4 | 10.1 | 0.656 | 46 % | 100 % | 0 % |
| bandit | -7.951 ± 8.143 | -5.914 | -0.162 [-0.236, -0.050] | -0.020 [-0.274, +0.256] | [-0.388, +0.158] | 0.0247 | 0.148 | 27.0 | 6.8 | 0.534 | 63 % | 37 % | 0 % |
| bandit_retune | -7.951 ± 8.143 | -5.914 | -0.162 [-0.236, -0.050] | -0.020 [-0.274, +0.256] | [-0.388, +0.158] | 0.0247 | 0.148 | 27.0 | 6.8 | 0.534 | 63 % | 37 % | 0 % |
| random_search | -6.534 ± 7.991 | -4.968 | +0.813 [+0.675, +1.108] | +1.397 [+1.158, +1.671] | [+0.478, +1.939] | 3.81e-17 | 1.1e-15 | 28.8 | 0.7 | 0.556 | 85 % | 39 % | 0 % |
| ppo (selected) **(primary)** | -7.101 ± 7.973 | -5.381 | +0.505 [+0.303, +0.826] | +0.830 [+0.657, +1.020] | [+0.095, +1.485] | 1.26e-14 | nan | 28.3 | 2.2 | 0.536 | 74 % | 0 % | 0 % |
| ppo_s0 | -7.624 ± 8.124 | -5.822 | +0.197 [+0.174, +0.231] | +0.307 [+0.111, +0.531] | [+0.108, +0.364] | 1.14e-06 | 1.36e-05 | 28.3 | 5.3 | 0.570 | 61 % | 0 % | 0 % |
| ppo_s1 | -7.101 ± 7.973 | -5.381 | +0.505 [+0.303, +0.826] | +0.830 [+0.657, +1.020] | [+0.095, +1.485] | 1.26e-14 | 2.65e-13 | 28.3 | 2.2 | 0.536 | 74 % | 0 % | 0 % |
| ppo_s2 | -7.478 ± 8.065 | -5.480 | +0.371 [+0.348, +0.402] | +0.453 [+0.412, +0.500] | [+0.325, +0.486] | 3.81e-17 | 1.1e-15 | 29.5 | 4.4 | 0.587 | 56 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +1.397 (17.6 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected 59 %; per seed ppo_s0 22 %, ppo_s1 59 %, ppo_s2 32 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.162 [-0.236, -0.050].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -7.624, ppo_s1 -7.101, ppo_s2 -7.478. Seed mean -7.401, std 0.220, range [-7.624, -7.101]; best constant -7.931.

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
| ppo (selected) | 6 | -57.191 | -58.361 |
| ppo_s0 | 6 | -57.429 | -58.601 |
| ppo_s1 | 6 | -57.191 | -58.361 |
| ppo_s2 | 6 | -57.134 | -58.340 |

Infeasible seeds (min margin): 50017 (0.81), 50024 (0.66), 50041 (0.67), 50064 (0.55), 50079 (0.52), 50081 (0.63)

## Regime `changes`

Best constant gains (chosen on validation): Kp 29.59, Ki 0.01, Kd 1.317 (validation return -19.770).
PPO seeds, validation mean return: ppo_s0 -19.516, ppo_s1 -19.216, ppo_s2 -19.949. Selected on validation: `ppo_s1`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 89 feasible scenarios of 100, the 11 infeasible ones are tabulated separately below.

Note: in this regime the target and payload change mid-episode, so overshoot, settling and success refer to the final target only; the return is the headline.

Feasible scenarios: 89 of 100; infeasible: 11.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -28.791 ± 27.314 | -21.237 | -5.713 [-7.290, -3.636] | -7.476 [-9.452, -5.769] | [-10.458, -1.752] | 9.76e-14 | 1.85e-12 | 63.5 | 70.4 | 1.337 | 16 % | 0 % | 0 % |
| legacy | -95.526 ± 78.509 | -72.824 | -56.103 [-69.435, -41.227] | -74.211 [-89.771, -60.724] | [-94.733, -23.573] | 3.96e-16 | 9.12e-15 | 95.7 | 118.4 | 1.614 | 0 % | 0 % | 0 % |
| best_constant | -21.315 ± 23.926 | -13.900 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 57.0 | 56.5 | 1.100 | 34 % | 0 % | 0 % |
| zn | -29.423 ± 34.572 | -14.655 | -0.878 [-1.088, -0.618] | -8.108 [-14.174, -3.421] | [-1.694, -0.087] | 1.1e-05 | 9.02e-05 | 67.2 | 53.2 | 1.150 | 39 % | 100 % | 0 % |
| bandit | -20.189 ± 23.629 | -12.751 | +0.325 [+0.110, +0.890] | +1.126 [+0.543, +1.739] | [-0.067, +1.534] | 6.34e-06 | 6.34e-05 | 55.3 | 55.8 | 1.099 | 45 % | 37 % | 0 % |
| bandit_retune | -20.493 ± 23.419 | -13.424 | +0.039 [-0.362, +0.326] | +0.822 [+0.205, +1.505] | [-0.777, +1.113] | 0.348 | 1 | 54.9 | 56.0 | 1.111 | 49 % | 40 % | 0 % |
| random_search | -13.944 ± 13.142 | -10.507 | +2.221 [+1.383, +3.742] | +7.371 [+4.742, +10.593] | [+0.693, +6.547] | 2.55e-16 | 6.12e-15 | 48.4 | 18.9 | 0.998 | 58 % | 47 % | 0 % |
| ppo (selected) | -19.845 ± 24.573 | -11.421 | +0.554 [+0.253, +1.486] | +1.470 [+0.559, +2.549] | [-0.149, +2.662] | 1e-05 | 9.02e-05 | 55.8 | 49.5 | 1.049 | 44 % | 0 % | 0 % |
| ppo_s0 | -20.415 ± 23.948 | -12.831 | +0.569 [+0.388, +0.917] | +0.900 [+0.469, +1.368] | [+0.071, +1.422] | 2.14e-06 | 2.35e-05 | 56.3 | 54.0 | 1.093 | 43 % | 0 % | 0 % |
| ppo_s1 | -19.845 ± 24.573 | -11.421 | +0.554 [+0.253, +1.486] | +1.470 [+0.559, +2.549] | [-0.149, +2.662] | 1e-05 | 9.02e-05 | 55.8 | 49.5 | 1.049 | 44 % | 0 % | 0 % |
| ppo_s2 | -21.253 ± 24.578 | -13.438 | +0.352 [+0.138, +0.604] | +0.062 [-0.699, +0.866] | [-0.579, +1.045] | 0.135 | 0.539 | 57.6 | 52.3 | 1.102 | 40 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +7.371 (34.6 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected 20 %; per seed ppo_s0 12 %, ppo_s1 20 %, ppo_s2 1 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): +0.325 [+0.110, +0.890].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -20.415, ppo_s1 -19.845, ppo_s2 -21.253. Seed mean -20.504, std 0.578, range [-21.253, -19.845]; best constant -21.315.

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
| ppo (selected) | 11 | -123.348 | -41.293 |
| ppo_s0 | 11 | -114.120 | -40.819 |
| ppo_s1 | 11 | -123.348 | -41.293 |
| ppo_s2 | 11 | -98.885 | -40.680 |

Infeasible seeds (min margin): 50017 (0.81), 50024 (0.66), 50031 (0.58), 50041 (0.67), 50042 (0.83), 50046 (0.68), 50052 (0.75), 50064 (0.46), 50079 (0.52), 50081 (0.63), 50083 (0.98)

## Regime `ood`

Best constant gains (chosen on validation): Kp 23.67, Ki 0.01, Kd 1.317 (validation return -10.173).
PPO seeds, validation mean return: ppo_s0 -9.933, ppo_s1 -9.707, ppo_s2 -9.799. Selected on validation: `ppo_s1`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 94 feasible scenarios of 100, the 6 infeasible ones are tabulated separately below.

Feasible scenarios: 94 of 100; infeasible: 6.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -14.029 ± 14.512 | -9.385 | -2.072 [-3.466, -1.021] | -3.609 [-4.595, -2.655] | [-5.060, -0.139] | 7.39e-12 | 1.03e-10 | 40.7 | 17.5 | 0.872 | 23 % | 0 % | 0 % |
| legacy | -55.589 ± 55.621 | -35.247 | -21.791 [-35.817, -17.132] | -45.168 [-56.997, -34.521] | [-60.348, -11.775] | 7.71e-17 | 2e-15 | 78.1 | 55.1 | 1.372 | 1 % | 0 % | 0 % |
| best_constant | -10.420 ± 13.072 | -6.216 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 35.0 | 6.7 | 0.632 | 49 % | 0 % | 0 % |
| zn | -18.265 ± 24.330 | -7.147 | -1.289 [-1.539, -1.063] | -7.845 [-11.903, -4.325] | [-2.307, -0.738] | 5.83e-13 | 1.05e-11 | 55.1 | 10.9 | 0.781 | 48 % | 100 % | 0 % |
| bandit | -10.344 ± 13.110 | -6.137 | -0.093 [-0.155, -0.045] | +0.077 [-0.130, +0.300] | [-0.247, +0.287] | 0.381 | 1 | 33.0 | 7.5 | 0.628 | 63 % | 37 % | 0 % |
| bandit_retune | -10.344 ± 13.110 | -6.137 | -0.093 [-0.155, -0.045] | +0.077 [-0.130, +0.300] | [-0.247, +0.287] | 0.381 | 1 | 33.0 | 7.5 | 0.628 | 63 % | 37 % | 0 % |
| random_search | -8.392 ± 12.741 | -5.176 | +0.943 [+0.820, +1.292] | +2.029 [+1.541, +2.611] | [+0.598, +2.296] | 3.81e-17 | 1.1e-15 | 34.7 | 0.9 | 0.625 | 85 % | 35 % | 0 % |
| ppo (selected) | -9.361 ± 12.832 | -5.668 | +0.572 [+0.258, +0.962] | +1.059 [+0.807, +1.336] | [+0.068, +1.836] | 6.88e-13 | 1.17e-11 | 34.0 | 3.3 | 0.616 | 69 % | 0 % | 0 % |
| ppo_s0 | -10.018 ± 13.064 | -6.234 | +0.291 [+0.213, +0.394] | +0.403 [+0.244, +0.563] | [+0.153, +0.639] | 8.4e-10 | 1.09e-08 | 34.3 | 6.2 | 0.656 | 57 % | 0 % | 0 % |
| ppo_s1 | -9.361 ± 12.832 | -5.668 | +0.572 [+0.258, +0.962] | +1.059 [+0.807, +1.336] | [+0.068, +1.836] | 6.88e-13 | 1.17e-11 | 34.0 | 3.3 | 0.616 | 69 % | 0 % | 0 % |
| ppo_s2 | -9.835 ± 12.967 | -5.740 | +0.418 [+0.319, +0.575] | +0.586 [+0.465, +0.731] | [+0.278, +0.687] | 1.46e-14 | 2.92e-13 | 35.4 | 5.3 | 0.668 | 57 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +2.029 (19.5 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected 52 %; per seed ppo_s0 20 %, ppo_s1 52 %, ppo_s2 29 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.093 [-0.155, -0.045].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -10.018, ppo_s1 -9.361, ppo_s2 -9.835. Seed mean -9.738, std 0.276, range [-10.018, -9.361]; best constant -10.420.

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
| ppo (selected) | 6 | -57.059 | -60.553 |
| ppo_s0 | 6 | -57.358 | -60.559 |
| ppo_s1 | 6 | -57.059 | -60.553 |
| ppo_s2 | 6 | -57.009 | -60.297 |

Infeasible seeds (min margin): 50017 (0.81), 50024 (0.66), 50041 (0.67), 50064 (0.55), 50079 (0.52), 50081 (0.63)

## Verdict

**Primary** (static, feasible, n=94): validation-selected PPO (`ppo_s1`) is BETTER than the best constant gains: paired median difference of return +0.505, 95 % CI [+0.303, +0.826] (Wilcoxon p = 1.26e-14, single primary test, unadjusted; analysis status: exploratory).

Secondary comparisons against best_constant with Holm-adjusted p < 0.05: static/tuned (p=1.7e-13), static/legacy (p=2.3e-15), static/zn (p=6.5e-11), static/random_search (p=1.1e-15), static/ppo_s0 (p=1.4e-05), static/ppo_s1 (p=2.6e-13), static/ppo_s2 (p=1.1e-15), changes/tuned (p=1.9e-12), changes/legacy (p=9.1e-15), changes/zn (p=9e-05), changes/bandit (p=6.3e-05), changes/random_search (p=6.1e-15), changes/ppo (p=9e-05), changes/ppo_s0 (p=2.4e-05), changes/ppo_s1 (p=9e-05), ood/tuned (p=1e-10), ood/legacy (p=2e-15), ood/zn (p=1e-11), ood/random_search (p=1.1e-15), ood/ppo (p=1.2e-11), ood/ppo_s0 (p=1.1e-08), ood/ppo_s1 (p=1.2e-11), ood/ppo_s2 (p=2.9e-13). The sign of the median difference in the tables gives the direction.

Everything above is simulated on the preliminary twin and has not been validated on hardware.
