# Controller comparison (PRE-VALIDATION, simulated on the unvalidated twin)

100 held-out paired TEST scenarios per regime (seeds 70000..70099); 40 VALIDATION scenarios (seeds 40000..40039) were used to choose `best_constant` and the reported PPO seed; neither set was used in training. Every controller sees the same plant, payload, target, delay and noise for a given seed. `return` is the environment reward (higher is better).
`random_search` is an ORACLE (best of 48 random sets + a 20-point Ki = 0 grid + Tuned + bandit + best_constant per scenario, chosen with hindsight): an upper bound for any adaptive tuner of this kind, not a deployable controller. Primary metric: episode return (success rate is descriptive).

**Analysis status: confirmatory.** These seeds were not used to train, select or tune anything; they confirm (or not) a design fixed earlier. Nothing may be re-tuned on them. One primary comparison: validation-selected PPO minus `best_constant`, `static` regime, feasible scenarios, paired median difference of return with a 95 % bootstrap CI. All other comparisons are secondary: paired Wilcoxon p-values, Holm-adjusted across the whole secondary family (feasible scenarios, all regimes). Infeasible scenarios (torque margin < 1.0 at any point, including after a payload change) are reported separately.

## Regime `static`

Best constant gains (chosen on validation): Kp 18.94, Ki 0.01, Kd 1.317 (validation return -8.099).
PPO seeds, validation mean return: ppo_s0 -8.348, ppo_s1 -7.741, ppo_s2 -7.725. Selected on validation: `ppo_s2`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 93 feasible scenarios of 100, the 7 infeasible ones are tabulated separately below.

Feasible scenarios: 93 of 100; infeasible: 7.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -10.072 ± 9.102 | -7.088 | -1.617 [-2.694, -1.190] | 9.3e-14 | 1.95e-12 | 32.9 | 16.2 | 0.783 | 20 % | 0 % | 0 % |
| legacy | -45.726 ± 70.121 | -24.785 | -18.995 [-26.105, -15.374] | 1.78e-16 | 4.27e-15 | 63.2 | 52.9 | 1.356 | 2 % | 0 % | 0 % |
| best_constant | -7.359 ± 8.164 | -5.412 | +0.000 [+0.000, +0.000] | nan | nan | 29.5 | 2.9 | 0.523 | 66 % | 0 % | 0 % |
| zn | -16.948 ± 24.872 | -6.258 | -1.132 [-1.374, -1.034] | 7.13e-10 | 1.21e-08 | 55.9 | 7.8 | 0.615 | 56 % | 100 % | 0 % |
| bandit | -7.115 ± 8.064 | -5.323 | -0.114 [-0.191, -0.073] | 0.0141 | 0.127 | 25.8 | 5.6 | 0.509 | 77 % | 26 % | 0 % |
| bandit_retune | -7.115 ± 8.064 | -5.323 | -0.114 [-0.191, -0.073] | 0.0141 | 0.127 | 25.8 | 5.6 | 0.509 | 77 % | 26 % | 0 % |
| random_search | -5.958 ± 7.901 | -4.503 | +0.737 [+0.565, +0.840] | 5.57e-17 | 1.62e-15 | 27.9 | 1.1 | 0.509 | 78 % | 26 % | 0 % |
| ppo **(primary)** | -6.981 ± 8.150 | -5.064 | +0.352 [+0.343, +0.359] | 5.57e-17 | nan | 29.5 | 2.9 | 0.545 | 67 % | 0 % | 0 % |
| ppo_s0 | -7.635 ± 7.988 | -5.627 | -0.620 [-0.671, -0.592] | 1.61e-07 | 1.93e-06 | 28.2 | 3.6 | 0.546 | 72 % | 0 % | 0 % |
| ppo_s1 | -6.992 ± 8.137 | -5.072 | +0.329 [+0.320, +0.340] | 5.57e-17 | 1.62e-15 | 29.3 | 2.8 | 0.516 | 66 % | 0 % | 0 % |
| ppo_s2 | -6.981 ± 8.150 | -5.064 | +0.352 [+0.343, +0.359] | 5.57e-17 | 1.62e-15 | 29.5 | 2.9 | 0.545 | 67 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +1.401 (19.0 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean PPO gain over best_constant divided by the oracle headroom): selected 27 %; per seed ppo_s0 -20 %, ppo_s1 26 %, ppo_s2 27 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.114 [-0.191, -0.073].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -7.635, ppo_s1 -6.992, ppo_s2 -6.981. Seed mean -7.203, std 0.306, range [-7.635, -6.981]; best constant -7.359.

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
| ppo | 7 | -41.962 | -43.120 |
| ppo_s0 | 7 | -41.608 | -43.603 |
| ppo_s1 | 7 | -41.916 | -43.115 |
| ppo_s2 | 7 | -41.962 | -43.120 |

Infeasible seeds (min margin): 70012 (0.69), 70013 (0.77), 70016 (0.98), 70022 (0.69), 70057 (0.79), 70065 (0.55), 70088 (0.43)

## Regime `changes`

Best constant gains (chosen on validation): Kp 29.59, Ki 0.01, Kd 1.317 (validation return -19.770).
PPO seeds, validation mean return: ppo_s0 -20.973, ppo_s1 -20.397, ppo_s2 -20.291. Selected on validation: `ppo_s2`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 86 feasible scenarios of 100, the 14 infeasible ones are tabulated separately below.

Note: in this regime the target and payload change mid-episode, so overshoot, settling and success refer to the final target only; the return is the headline.

Feasible scenarios: 86 of 100; infeasible: 14.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -27.295 ± 40.380 | -16.422 | -3.227 [-4.758, -1.756] | 1.2e-13 | 2.39e-12 | 59.8 | 49.3 | 1.286 | 19 % | 0 % | 0 % |
| legacy | -88.413 ± 109.533 | -50.378 | -34.145 [-39.606, -27.631] | 9.2e-16 | 2.02e-14 | 86.0 | 90.5 | 1.692 | 2 % | 0 % | 0 % |
| best_constant | -19.894 ± 34.807 | -11.532 | +0.000 [+0.000, +0.000] | nan | nan | 53.9 | 38.4 | 1.060 | 36 % | 0 % | 0 % |
| zn | -27.411 ± 35.287 | -11.943 | -0.961 [-1.190, -0.638] | 6.08e-06 | 6.08e-05 | 70.2 | 35.2 | 1.124 | 45 % | 100 % | 0 % |
| bandit | -19.596 ± 35.790 | -10.083 | -0.053 [-0.115, +0.069] | 0.383 | 1 | 52.3 | 38.8 | 1.067 | 50 % | 24 % | 0 % |
| bandit_retune | -20.049 ± 35.901 | -10.524 | -0.527 [-0.795, -0.237] | 0.0676 | 0.471 | 52.0 | 39.0 | 1.080 | 53 % | 34 % | 0 % |
| random_search | -12.908 ± 14.550 | -9.040 | +1.337 [+0.919, +2.225] | 7.99e-16 | 1.84e-14 | 49.3 | 15.6 | 0.999 | 64 % | 41 % | 0 % |
| ppo | -20.385 ± 35.643 | -11.941 | +0.179 [-0.083, +0.432] | 0.422 | 1 | 55.4 | 35.7 | 1.067 | 40 % | 0 % | 0 % |
| ppo_s0 | -21.046 ± 35.132 | -13.062 | -1.199 [-1.317, -0.954] | 7.68e-12 | 1.46e-10 | 54.3 | 36.7 | 1.094 | 45 % | 0 % | 0 % |
| ppo_s1 | -20.364 ± 35.304 | -12.024 | +0.133 [-0.086, +0.365] | 0.841 | 1 | 55.3 | 35.7 | 1.052 | 40 % | 0 % | 0 % |
| ppo_s2 | -20.385 ± 35.643 | -11.941 | +0.179 [-0.083, +0.432] | 0.422 | 1 | 55.4 | 35.7 | 1.067 | 40 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +6.986 (35.1 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean PPO gain over best_constant divided by the oracle headroom): selected -7 %; per seed ppo_s0 -16 %, ppo_s1 -7 %, ppo_s2 -7 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.053 [-0.115, +0.069].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -21.046, ppo_s1 -20.364, ppo_s2 -20.385. Seed mean -20.598, std 0.317, range [-21.046, -20.364]; best constant -19.894.

### Infeasible scenarios (reported separately)

| controller | n | return mean | median |
|---|---|---|---|
| tuned | 14 | -97.918 | -58.690 |
| legacy | 14 | -221.387 | -102.874 |
| best_constant | 14 | -64.782 | -36.514 |
| zn | 14 | -84.350 | -81.967 |
| bandit | 14 | -55.996 | -27.947 |
| bandit_retune | 14 | -55.277 | -26.305 |
| random_search | 14 | -37.721 | -21.207 |
| ppo | 14 | -72.419 | -49.524 |
| ppo_s0 | 14 | -66.686 | -37.821 |
| ppo_s1 | 14 | -71.312 | -47.162 |
| ppo_s2 | 14 | -72.419 | -49.524 |

Infeasible seeds (min margin): 70012 (0.69), 70013 (0.77), 70016 (0.98), 70021 (0.79), 70022 (0.69), 70031 (0.65), 70056 (0.81), 70057 (0.79), 70065 (0.55), 70072 (0.46), 70076 (0.74), 70079 (0.97)...

## Regime `ood`

Best constant gains (chosen on validation): Kp 23.67, Ki 0.01, Kd 1.317 (validation return -10.173).
PPO seeds, validation mean return: ppo_s0 -10.488, ppo_s1 -9.862, ppo_s2 -9.856. Selected on validation: `ppo_s2`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 93 feasible scenarios of 100, the 7 infeasible ones are tabulated separately below.

Feasible scenarios: 93 of 100; infeasible: 7.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -11.633 ± 13.324 | -7.024 | -1.032 [-1.854, -0.295] | 4.71e-08 | 6.12e-07 | 37.0 | 13.3 | 0.719 | 33 % | 0 % | 0 % |
| legacy | -47.064 ± 77.044 | -22.377 | -15.665 [-21.897, -11.182] | 1.52e-16 | 3.79e-15 | 63.2 | 46.7 | 1.354 | 2 % | 0 % | 0 % |
| best_constant | -8.965 ± 11.556 | -5.606 | +0.000 [+0.000, +0.000] | nan | nan | 33.2 | 4.4 | 0.570 | 63 % | 0 % | 0 % |
| zn | -17.473 ± 24.287 | -6.401 | -1.208 [-1.482, -1.022] | 2.72e-11 | 4.89e-10 | 57.1 | 8.4 | 0.645 | 57 % | 100 % | 0 % |
| bandit | -8.642 ± 11.364 | -5.395 | -0.101 [-0.149, -0.033] | 0.0673 | 0.471 | 30.8 | 5.9 | 0.542 | 73 % | 26 % | 0 % |
| bandit_retune | -8.642 ± 11.364 | -5.395 | -0.101 [-0.149, -0.033] | 0.0673 | 0.471 | 30.8 | 5.9 | 0.542 | 73 % | 26 % | 0 % |
| random_search | -7.176 ± 11.120 | -4.827 | +0.796 [+0.744, +0.952] | 5.57e-17 | 1.62e-15 | 32.7 | 1.0 | 0.560 | 78 % | 26 % | 0 % |
| ppo | -8.656 ± 11.586 | -5.255 | +0.337 [+0.294, +0.359] | 1.69e-09 | 2.53e-08 | 34.2 | 3.3 | 0.606 | 66 % | 0 % | 0 % |
| ppo_s0 | -9.267 ± 11.365 | -6.049 | -0.560 [-0.611, -0.488] | 5.24e-07 | 5.76e-06 | 33.0 | 4.1 | 0.612 | 72 % | 0 % | 0 % |
| ppo_s1 | -8.660 ± 11.563 | -5.267 | +0.301 [+0.277, +0.325] | 1.27e-09 | 2.03e-08 | 34.1 | 3.3 | 0.609 | 66 % | 0 % | 0 % |
| ppo_s2 | -8.656 ± 11.586 | -5.255 | +0.337 [+0.294, +0.359] | 1.69e-09 | 2.53e-08 | 34.2 | 3.3 | 0.606 | 66 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +1.789 (20.0 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean PPO gain over best_constant divided by the oracle headroom): selected 17 %; per seed ppo_s0 -17 %, ppo_s1 17 %, ppo_s2 17 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.101 [-0.149, -0.033].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -9.267, ppo_s1 -8.660, ppo_s2 -8.656. Seed mean -8.861, std 0.287, range [-9.267, -8.656]; best constant -8.965.

### Infeasible scenarios (reported separately)

| controller | n | return mean | median |
|---|---|---|---|
| tuned | 7 | -38.822 | -21.558 |
| legacy | 7 | -38.532 | -20.896 |
| best_constant | 7 | -38.281 | -20.851 |
| zn | 7 | -67.771 | -89.819 |
| bandit | 7 | -37.450 | -20.523 |
| bandit_retune | 7 | -37.450 | -20.523 |
| random_search | 7 | -37.369 | -20.523 |
| ppo | 7 | -38.284 | -21.057 |
| ppo_s0 | 7 | -38.295 | -21.366 |
| ppo_s1 | 7 | -38.255 | -20.981 |
| ppo_s2 | 7 | -38.284 | -21.057 |

Infeasible seeds (min margin): 70012 (0.69), 70013 (0.77), 70016 (0.98), 70022 (0.69), 70057 (0.79), 70065 (0.55), 70088 (0.43)

## Verdict

**Primary** (static, feasible, n=93): validation-selected PPO (`ppo_s2`) is BETTER than the best constant gains: paired median difference of return +0.352, 95 % CI [+0.343, +0.359] (Wilcoxon p = 5.57e-17, single primary test, unadjusted; analysis status: confirmatory).

Secondary comparisons against best_constant with Holm-adjusted p < 0.05: static/tuned (p=2e-12), static/legacy (p=4.3e-15), static/zn (p=1.2e-08), static/random_search (p=1.6e-15), static/ppo_s0 (p=1.9e-06), static/ppo_s1 (p=1.6e-15), static/ppo_s2 (p=1.6e-15), changes/tuned (p=2.4e-12), changes/legacy (p=2e-14), changes/zn (p=6.1e-05), changes/random_search (p=1.8e-14), changes/ppo_s0 (p=1.5e-10), ood/tuned (p=6.1e-07), ood/legacy (p=3.8e-15), ood/zn (p=4.9e-10), ood/random_search (p=1.6e-15), ood/ppo (p=2.5e-08), ood/ppo_s0 (p=5.8e-06), ood/ppo_s1 (p=2e-08), ood/ppo_s2 (p=2.5e-08). The sign of the median difference in the tables gives the direction.

Everything above is simulated on the preliminary twin and has not been validated on hardware.
