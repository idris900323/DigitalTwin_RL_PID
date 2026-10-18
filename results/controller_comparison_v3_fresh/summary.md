# Controller comparison (PRE-VALIDATION, simulated on the unvalidated twin)

100 held-out paired TEST scenarios per regime (seeds 60000..60099); 40 VALIDATION scenarios (seeds 40000..40039) were used to choose `best_constant` and the reported PPO seed; neither set was used in training. Every controller sees the same plant, payload, target, delay and noise for a given seed. `return` is the environment reward (higher is better).
`random_search` is an ORACLE (best of 48 random sets + a 20-point Ki = 0 grid + Tuned + bandit + best_constant per scenario, chosen with hindsight): an upper bound for any adaptive tuner of this kind, not a deployable controller. Primary metric: episode return (success rate is descriptive).

**Analysis status: confirmatory.** These seeds were not used to train, select or tune anything; they confirm (or not) a design fixed earlier. Nothing may be re-tuned on them. One primary comparison: validation-selected PPO minus `best_constant`, `static` regime, feasible scenarios, paired median difference of return with a 95 % bootstrap CI. All other comparisons are secondary: paired Wilcoxon p-values, Holm-adjusted across the whole secondary family (feasible scenarios, all regimes). Infeasible scenarios (torque margin < 1.0 at any point, including after a payload change) are reported separately.

## Regime `static`

Best constant gains (chosen on validation): Kp 18.94, Ki 0.01, Kd 1.317 (validation return -8.099).
PPO seeds, validation mean return: ppo_s0 -7.671, ppo_s1 -7.489, ppo_s2 -7.671. Selected on validation: `ppo_s1`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 91 feasible scenarios of 100, the 9 infeasible ones are tabulated separately below.

Feasible scenarios: 91 of 100; infeasible: 9.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -10.291 ± 6.552 | -8.164 | -2.106 [-2.804, -1.105] | -3.100 [-3.960, -2.292] | [-4.120, -0.357] | 2.02e-12 | 4.24e-11 | 33.0 | 15.7 | 0.878 | 15 % | 0 % | 0 % |
| legacy | -48.328 ± 54.758 | -29.155 | -24.300 [-28.538, -13.970] | -41.138 [-51.718, -30.938] | [-59.442, -6.361] | 7.18e-15 | 1.65e-13 | 63.3 | 51.6 | 1.465 | 5 % | 0 % | 0 % |
| best_constant | -7.191 ± 3.519 | -6.533 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 28.7 | 3.5 | 0.612 | 49 % | 0 % | 0 % |
| zn | -18.904 ± 26.418 | -6.233 | -0.966 [-1.255, -0.871] | -11.713 [-17.112, -6.733] | [-2.116, -0.582] | 9.03e-07 | 1.08e-05 | 59.1 | 8.1 | 0.630 | 56 % | 100 % | 0 % |
| bandit | -6.498 ± 3.308 | -5.418 | -0.088 [-0.162, +0.016] | +0.692 [+0.178, +1.284] | [-0.358, +0.783] | 0.856 | 1 | 22.2 | 6.2 | 0.565 | 77 % | 33 % | 0 % |
| bandit_retune | -6.498 ± 3.308 | -5.418 | -0.088 [-0.162, +0.016] | +0.692 [+0.178, +1.284] | [-0.358, +0.783] | 0.856 | 1 | 22.2 | 6.2 | 0.565 | 77 % | 33 % | 0 % |
| random_search | -5.287 ± 2.040 | -4.690 | +0.842 [+0.652, +1.109] | +1.904 [+1.430, +2.453] | [+0.513, +2.364] | 1.19e-16 | 3.46e-15 | 24.6 | 1.4 | 0.619 | 79 % | 32 % | 0 % |
| ppo (selected) **(primary)** | -6.053 ± 2.482 | -5.597 | +0.610 [+0.286, +0.752] | +1.138 [+0.828, +1.499] | [+0.076, +1.689] | 5.15e-14 | nan | 25.7 | 1.9 | 0.523 | 58 % | 0 % | 0 % |
| ppo_s0 | -6.398 ± 3.050 | -5.589 | +0.226 [+0.193, +0.318] | +0.792 [+0.378, +1.257] | [+0.125, +0.839] | 1.11e-07 | 1.44e-06 | 24.8 | 4.2 | 0.605 | 58 % | 0 % | 0 % |
| ppo_s1 | -6.053 ± 2.482 | -5.597 | +0.610 [+0.286, +0.752] | +1.138 [+0.828, +1.499] | [+0.076, +1.689] | 5.15e-14 | 1.13e-12 | 25.7 | 1.9 | 0.523 | 58 % | 0 % | 0 % |
| ppo_s2 | -6.638 ± 3.258 | -5.948 | +0.405 [+0.360, +0.474] | +0.553 [+0.478, +0.635] | [+0.332, +0.566] | 1.19e-16 | 3.46e-15 | 28.0 | 3.4 | 0.591 | 51 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +1.904 (26.5 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected 60 %; per seed ppo_s0 42 %, ppo_s1 60 %, ppo_s2 29 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.088 [-0.162, +0.016].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -6.398, ppo_s1 -6.053, ppo_s2 -6.638. Seed mean -6.363, std 0.240, range [-6.638, -6.053]; best constant -7.191.

### Infeasible scenarios (reported separately)

| controller | n | return mean | median |
|---|---|---|---|
| tuned | 9 | -40.377 | -52.552 |
| legacy | 9 | -39.800 | -52.552 |
| best_constant | 9 | -39.471 | -52.877 |
| zn | 9 | -75.149 | -92.263 |
| bandit | 9 | -38.194 | -52.552 |
| bandit_retune | 9 | -38.194 | -52.552 |
| random_search | 9 | -37.658 | -52.552 |
| ppo (selected) | 9 | -38.480 | -52.578 |
| ppo_s0 | 9 | -38.500 | -53.057 |
| ppo_s1 | 9 | -38.480 | -52.578 |
| ppo_s2 | 9 | -38.871 | -52.558 |

Infeasible seeds (min margin): 60004 (0.80), 60013 (0.48), 60022 (0.69), 60059 (0.98), 60061 (0.57), 60062 (0.91), 60078 (0.93), 60086 (0.64), 60094 (0.97)

## Regime `changes`

Best constant gains (chosen on validation): Kp 29.59, Ki 0.01, Kd 1.317 (validation return -19.770).
PPO seeds, validation mean return: ppo_s0 -19.516, ppo_s1 -19.216, ppo_s2 -19.949. Selected on validation: `ppo_s1`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 83 feasible scenarios of 100, the 17 infeasible ones are tabulated separately below.

Note: in this regime the target and payload change mid-episode, so overshoot, settling and success refer to the final target only; the return is the headline.

Feasible scenarios: 83 of 100; infeasible: 17.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -26.357 ± 23.085 | -19.264 | -3.812 [-4.803, -2.535] | -7.422 [-10.001, -5.251] | [-9.179, -0.982] | 9.44e-12 | 1.7e-10 | 64.6 | 57.6 | 1.379 | 14 % | 0 % | 0 % |
| legacy | -98.830 ± 94.034 | -58.885 | -41.396 [-54.421, -30.323] | -79.894 [-100.886, -61.421] | [-112.561, -21.542] | 3.47e-15 | 8.34e-14 | 91.7 | 101.2 | 1.728 | 2 % | 0 % | 0 % |
| best_constant | -18.935 ± 17.465 | -13.116 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 57.9 | 47.7 | 1.144 | 27 % | 0 % | 0 % |
| zn | -27.570 ± 29.876 | -13.284 | -0.797 [-1.249, -0.575] | -8.634 [-14.462, -3.837] | [-2.521, -0.278] | 5.05e-06 | 4.54e-05 | 71.8 | 32.3 | 1.181 | 41 % | 100 % | 0 % |
| bandit | -17.749 ± 17.177 | -11.505 | +0.172 [+0.002, +0.599] | +1.186 [+0.532, +1.959] | [-0.262, +1.284] | 0.00326 | 0.0228 | 55.3 | 48.6 | 1.165 | 48 % | 34 % | 0 % |
| bandit_retune | -17.901 ± 17.262 | -12.035 | -0.005 [-0.403, +0.123] | +1.034 [+0.252, +1.992] | [-0.793, +1.138] | 0.448 | 1 | 54.9 | 48.7 | 1.141 | 53 % | 29 % | 0 % |
| random_search | -12.455 ± 7.956 | -10.144 | +2.266 [+1.500, +3.624] | +6.480 [+4.156, +9.600] | [+0.925, +5.971] | 2.5e-15 | 6.26e-14 | 50.6 | 16.4 | 1.034 | 55 % | 45 % | 0 % |
| ppo (selected) | -17.402 ± 16.967 | -11.519 | +0.579 [+0.244, +1.227] | +1.533 [+1.036, +2.146] | [-0.152, +2.693] | 1.75e-06 | 1.92e-05 | 56.9 | 43.2 | 1.093 | 37 % | 0 % | 0 % |
| ppo_s0 | -18.242 ± 16.990 | -11.813 | +0.535 [+0.298, +0.666] | +0.693 [+0.264, +1.193] | [-0.068, +1.367] | 0.000719 | 0.00575 | 57.0 | 46.2 | 1.153 | 40 % | 0 % | 0 % |
| ppo_s1 | -17.402 ± 16.967 | -11.519 | +0.579 [+0.244, +1.227] | +1.533 [+1.036, +2.146] | [-0.152, +2.693] | 1.75e-06 | 1.92e-05 | 56.9 | 43.2 | 1.093 | 37 % | 0 % | 0 % |
| ppo_s2 | -19.197 ± 17.323 | -12.877 | +0.321 [+0.070, +0.619] | -0.262 [-0.984, +0.383] | [-0.606, +1.026] | 0.191 | 1 | 59.3 | 44.4 | 1.155 | 33 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +6.480 (34.2 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected 24 %; per seed ppo_s0 11 %, ppo_s1 24 %, ppo_s2 -4 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): +0.172 [+0.002, +0.599].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -18.242, ppo_s1 -17.402, ppo_s2 -19.197. Seed mean -18.281, std 0.734, range [-19.197, -17.402]; best constant -18.935.

### Infeasible scenarios (reported separately)

| controller | n | return mean | median |
|---|---|---|---|
| tuned | 17 | -92.682 | -48.728 |
| legacy | 17 | -138.147 | -81.790 |
| best_constant | 17 | -85.493 | -46.687 |
| zn | 17 | -120.454 | -96.041 |
| bandit | 17 | -84.216 | -38.123 |
| bandit_retune | 17 | -85.066 | -37.943 |
| random_search | 17 | -42.603 | -35.385 |
| ppo (selected) | 17 | -85.156 | -44.177 |
| ppo_s0 | 17 | -85.533 | -44.312 |
| ppo_s1 | 17 | -85.156 | -44.177 |
| ppo_s2 | 17 | -87.271 | -50.290 |

Infeasible seeds (min margin): 60003 (0.82), 60004 (0.80), 60008 (0.60), 60013 (0.48), 60014 (0.96), 60022 (0.69), 60052 (0.43), 60059 (0.98), 60061 (0.57), 60062 (0.91), 60075 (0.83), 60078 (0.93)...

## Regime `ood`

Best constant gains (chosen on validation): Kp 23.67, Ki 0.01, Kd 1.317 (validation return -10.173).
PPO seeds, validation mean return: ppo_s0 -9.933, ppo_s1 -9.707, ppo_s2 -9.799. Selected on validation: `ppo_s1`.

Filter: a scenario is *feasible* when the torque-feasibility margin stays >= 1.0 for the whole episode (initial context and after any payload change); the headline tables use the 91 feasible scenarios of 100, the 9 infeasible ones are tabulated separately below.

Feasible scenarios: 91 of 100; infeasible: 9.

### Feasible scenarios (headline)

| controller | return mean ± std | median | Δmedian vs best_constant [95 % CI] | Δmean [95 % CI] | IQR of Δ | p (Wilcoxon) | p Holm | IAE | overshoot % | settle s | success | at a gain bound | diverged |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tuned | -11.759 ± 10.680 | -8.068 | -1.402 [-2.086, -0.956] | -3.023 [-3.966, -2.117] | [-4.587, +0.053] | 3.82e-10 | 5.72e-09 | 36.5 | 14.0 | 0.782 | 22 % | 0 % | 0 % |
| legacy | -49.148 ± 60.716 | -24.981 | -18.160 [-24.855, -12.014] | -40.412 [-51.974, -29.403] | [-51.199, -4.463] | 1.97e-15 | 5.11e-14 | 63.9 | 48.2 | 1.343 | 7 % | 0 % | 0 % |
| best_constant | -8.736 ± 7.787 | -6.193 | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | [+0.000, +0.000] | nan | nan | 31.5 | 5.3 | 0.647 | 47 % | 0 % | 0 % |
| zn | -19.604 ± 25.494 | -6.989 | -1.010 [-1.368, -0.831] | -10.868 [-15.697, -6.359] | [-3.254, -0.435] | 6.86e-09 | 9.6e-08 | 60.4 | 8.8 | 0.604 | 53 % | 100 % | 0 % |
| bandit | -8.281 ± 7.824 | -5.828 | -0.049 [-0.134, +0.031] | +0.455 [+0.066, +0.927] | [-0.319, +0.822] | 0.436 | 1 | 27.2 | 6.7 | 0.594 | 76 % | 33 % | 0 % |
| bandit_retune | -8.281 ± 7.824 | -5.828 | -0.049 [-0.134, +0.031] | +0.455 [+0.066, +0.927] | [-0.319, +0.822] | 0.436 | 1 | 27.2 | 6.7 | 0.594 | 76 % | 33 % | 0 % |
| random_search | -6.465 ± 6.441 | -4.815 | +1.048 [+0.865, +1.306] | +2.271 [+1.638, +2.977] | [+0.639, +2.137] | 1.19e-16 | 3.46e-15 | 29.1 | 1.2 | 0.687 | 80 % | 27 % | 0 % |
| ppo (selected) | -7.684 ± 7.078 | -5.665 | +0.452 [+0.236, +0.737] | +1.051 [+0.744, +1.381] | [+0.019, +1.515] | 3.65e-12 | 7.3e-11 | 30.1 | 2.9 | 0.627 | 56 % | 0 % | 0 % |
| ppo_s0 | -8.120 ± 7.646 | -5.849 | +0.297 [+0.202, +0.429] | +0.616 [+0.335, +0.938] | [+0.164, +0.683] | 2.88e-10 | 4.61e-09 | 29.6 | 5.0 | 0.716 | 59 % | 0 % | 0 % |
| ppo_s1 | -7.684 ± 7.078 | -5.665 | +0.452 [+0.236, +0.737] | +1.051 [+0.744, +1.381] | [+0.019, +1.515] | 3.65e-12 | 7.3e-11 | 30.1 | 2.9 | 0.627 | 56 % | 0 % | 0 % |
| ppo_s2 | -8.270 ± 7.509 | -5.734 | +0.317 [+0.292, +0.425] | +0.466 [+0.330, +0.629] | [+0.195, +0.662] | 2.19e-11 | 3.72e-10 | 32.3 | 4.2 | 0.671 | 48 % | 0 % | 0 % |

Oracle headroom over best_constant (feasible): mean return +2.271 (26.0 % of |best_constant return|); this is the ceiling for any adaptive tuner on this scenario set.
Headroom captured (mean gain of the learned policy over best_constant divided by the oracle headroom): selected 46 %; per seed ppo_s0 27 %, ppo_s1 46 %, ppo_s2 21 %. Success rate is descriptive only; return is the headline.
Bandit vs best_constant (return, median difference): -0.049 [-0.134, +0.031].

PPO across training seeds (feasible test scenarios, mean return): ppo_s0 -8.120, ppo_s1 -7.684, ppo_s2 -8.270. Seed mean -8.025, std 0.248, range [-8.270, -7.684]; best constant -8.736.

### Infeasible scenarios (reported separately)

| controller | n | return mean | median |
|---|---|---|---|
| tuned | 9 | -35.815 | -31.529 |
| legacy | 9 | -37.407 | -31.542 |
| best_constant | 9 | -35.465 | -31.853 |
| zn | 9 | -74.343 | -90.011 |
| bandit | 9 | -34.932 | -31.529 |
| bandit_retune | 9 | -34.932 | -31.529 |
| random_search | 9 | -34.685 | -31.529 |
| ppo (selected) | 9 | -35.009 | -31.555 |
| ppo_s0 | 9 | -35.121 | -31.552 |
| ppo_s1 | 9 | -35.009 | -31.555 |
| ppo_s2 | 9 | -35.199 | -31.535 |

Infeasible seeds (min margin): 60004 (0.80), 60013 (0.48), 60022 (0.69), 60059 (0.98), 60061 (0.57), 60062 (0.91), 60078 (0.93), 60086 (0.64), 60094 (0.97)

## Verdict

**Primary** (static, feasible, n=91): validation-selected PPO (`ppo_s1`) is BETTER than the best constant gains: paired median difference of return +0.610, 95 % CI [+0.286, +0.752] (Wilcoxon p = 5.15e-14, single primary test, unadjusted; analysis status: confirmatory).

Secondary comparisons against best_constant with Holm-adjusted p < 0.05: static/tuned (p=4.2e-11), static/legacy (p=1.7e-13), static/zn (p=1.1e-05), static/random_search (p=3.5e-15), static/ppo_s0 (p=1.4e-06), static/ppo_s1 (p=1.1e-12), static/ppo_s2 (p=3.5e-15), changes/tuned (p=1.7e-10), changes/legacy (p=8.3e-14), changes/zn (p=4.5e-05), changes/bandit (p=0.023), changes/random_search (p=6.3e-14), changes/ppo (p=1.9e-05), changes/ppo_s0 (p=0.0057), changes/ppo_s1 (p=1.9e-05), ood/tuned (p=5.7e-09), ood/legacy (p=5.1e-14), ood/zn (p=9.6e-08), ood/random_search (p=3.5e-15), ood/ppo (p=7.3e-11), ood/ppo_s0 (p=4.6e-09), ood/ppo_s1 (p=7.3e-11), ood/ppo_s2 (p=3.7e-10). The sign of the median difference in the tables gives the direction.

Everything above is simulated on the preliminary twin and has not been validated on hardware.
