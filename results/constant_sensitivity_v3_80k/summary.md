# Constant-gain and scenario-conditioned sensitivity (POST HOC, simulation only)

Added after the confirmatory runs because the learned policies end at nearly constant gains. Every new baseline is derived on validation seeds (40000..40039); the test seeds (80000..80099) are used once for evaluation. Differences are paired on feasible scenarios: median [95 % bootstrap CI] / mean / IQR / Wilcoxon p (unadjusted).

## static (n feasible = 92)

Constants: original [18.94, 0.01, 1.32] (val -8.099); extended [28.54, 0.0, 2.0] (val -7.614); distilled from `ppo_s1` [26.09, 0.0, 1.8]; scenario fit (val -7.279); PPO val -7.489.

| comparison (A minus B) | A mean return | Δmedian [95 % CI] | Δmean | IQR of Δ | p |
|---|---|---|---|---|---|
| best_constant_ext − best_constant | -5.865 | +0.387 [+0.271, +0.607] | +0.668 | [+0.052, +1.010] | 2.86e-13 |
| ppo_distilled − best_constant | -5.907 | +0.401 [+0.324, +0.562] | +0.627 | [+0.134, +0.877] | 8.7e-17 |
| scenario_fit − best_constant | -5.832 | +0.396 [+0.264, +0.546] | +0.702 | [+0.166, +0.948] | 1e-11 |
| ppo − best_constant | -5.715 | +0.485 [+0.303, +0.792] | +0.818 | [+0.059, +1.284] | 4.89e-14 |
| ppo − best_constant_ext | -5.715 | +0.103 [+0.058, +0.152] | +0.150 | [+0.016, +0.240] | 5.2e-11 |
| ppo − ppo_distilled | -5.715 | +0.096 [-0.009, +0.206] | +0.192 | [-0.077, +0.371] | 2.04e-05 |
| ppo − scenario_fit | -5.715 | -0.042 [-0.146, +0.064] | +0.117 | [-0.224, +0.372] | 0.536 |

## changes (n feasible = 89)

Constants: original [29.59, 0.01, 1.32] (val -19.770); extended [41.82, 0.0, 2.0] (val -19.002); distilled from `ppo_s1` [27.06, 0.0, 1.81]; scenario fit (val -18.809); PPO val -19.216.

| comparison (A minus B) | A mean return | Δmedian [95 % CI] | Δmean | IQR of Δ | p |
|---|---|---|---|---|---|
| best_constant_ext − best_constant | -22.502 | +0.667 [+0.477, +0.939] | +0.280 | [+0.202, +1.712] | 4.55e-11 |
| ppo_distilled − best_constant | -22.060 | +0.538 [+0.201, +0.864] | +0.722 | [-0.322, +1.773] | 0.000584 |
| scenario_fit − best_constant | -22.602 | +0.617 [+0.488, +0.940] | +0.179 | [+0.208, +1.834] | 1.15e-10 |
| ppo − best_constant | -21.647 | +0.602 [+0.303, +1.092] | +1.134 | [-0.185, +2.393] | 5.43e-06 |
| ppo − best_constant_ext | -21.647 | -0.107 [-0.268, +0.210] | +0.855 | [-0.541, +0.804] | 0.66 |
| ppo − ppo_distilled | -21.647 | +0.138 [+0.054, +0.355] | +0.413 | [-0.104, +0.601] | 0.000444 |
| ppo − scenario_fit | -21.647 | -0.098 [-0.261, +0.067] | +0.955 | [-0.541, +0.439] | 0.639 |

## ood (n feasible = 92)

Constants: original [23.67, 0.01, 1.32] (val -10.173); extended [26.08, 0.0, 2.0] (val -9.767); distilled from `ppo_s1` [26.16, 0.0, 1.79]; scenario fit (val -9.333); PPO val -9.707.

| comparison (A minus B) | A mean return | Δmedian [95 % CI] | Δmean | IQR of Δ | p |
|---|---|---|---|---|---|
| best_constant_ext − best_constant | -7.558 | +0.326 [+0.103, +0.544] | +0.954 | [-0.002, +1.295] | 6.12e-10 |
| ppo_distilled − best_constant | -7.699 | +0.403 [+0.215, +0.605] | +0.813 | [+0.114, +1.063] | 2.24e-16 |
| scenario_fit − best_constant | -8.018 | +0.335 [+0.267, +0.471] | +0.494 | [+0.126, +0.618] | 4.06e-07 |
| ppo − best_constant | -7.526 | +0.458 [+0.232, +0.747] | +0.986 | [+0.039, +1.402] | 8.98e-13 |
| ppo − best_constant_ext | -7.526 | +0.048 [+0.028, +0.066] | +0.031 | [-0.007, +0.127] | 4.93e-06 |
| ppo − ppo_distilled | -7.526 | +0.019 [-0.047, +0.122] | +0.173 | [-0.080, +0.332] | 0.00308 |
| ppo − scenario_fit | -7.526 | -0.040 [-0.202, +0.223] | +0.491 | [-0.337, +0.839] | 0.0437 |

