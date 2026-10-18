# Constant-gain and scenario-conditioned sensitivity (POST HOC, simulation only)

Added after the confirmatory runs because the learned policies end at nearly constant gains. Every new baseline is derived on validation seeds (40000..40039); the test seeds (80000..80099) are used once for evaluation. Differences are paired on feasible scenarios: median [95 % bootstrap CI] / mean / IQR / Wilcoxon p (unadjusted).

## static (n feasible = 92)

Constants: original [18.94, 0.01, 1.32] (val -8.099); extended [28.54, 0.0, 2.0] (val -7.614); distilled from `ppo_s2` [19.55, 0.0, 1.23]; scenario fit (val -7.279); PPO val -7.725.

| comparison (A minus B) | A mean return | Δmedian [95 % CI] | Δmean | IQR of Δ | p |
|---|---|---|---|---|---|
| best_constant_ext − best_constant | -5.865 | +0.387 [+0.271, +0.607] | +0.668 | [+0.052, +1.010] | 2.86e-13 |
| ppo_distilled − best_constant | -6.316 | +0.221 [+0.157, +0.318] | +0.218 | [+0.076, +0.376] | 5.35e-12 |
| scenario_fit − best_constant | -5.832 | +0.396 [+0.264, +0.546] | +0.702 | [+0.166, +0.948] | 1e-11 |
| ppo − best_constant | -6.143 | +0.375 [+0.358, +0.401] | +0.390 | [+0.346, +0.424] | 8.15e-17 |
| ppo − best_constant_ext | -6.143 | -0.000 [-0.233, +0.109] | -0.278 | [-0.626, +0.293] | 0.0284 |
| ppo − ppo_distilled | -6.143 | +0.130 [+0.026, +0.225] | +0.173 | [-0.029, +0.319] | 3.24e-07 |
| ppo − scenario_fit | -6.143 | -0.050 [-0.179, +0.090] | -0.311 | [-0.518, +0.188] | 0.0421 |
| ppo_distilled_pooled − best_constant | -6.317 | +0.222 [+0.158, +0.318] | +0.217 | [+0.079, +0.374] | 5.35e-12 |
| ppo − ppo_distilled_pooled | -6.143 | +0.130 [+0.026, +0.225] | +0.173 | [-0.028, +0.320] | 2.53e-07 |

## changes (n feasible = 89)

Constants: original [29.59, 0.01, 1.32] (val -19.770); extended [41.82, 0.0, 2.0] (val -19.002); distilled from `ppo_s2` [19.52, 0.0, 1.23]; scenario fit (val -18.809); PPO val -20.291.

| comparison (A minus B) | A mean return | Δmedian [95 % CI] | Δmean | IQR of Δ | p |
|---|---|---|---|---|---|
| best_constant_ext − best_constant | -22.502 | +0.667 [+0.477, +0.939] | +0.280 | [+0.202, +1.712] | 4.55e-11 |
| ppo_distilled − best_constant | -22.568 | +0.201 [-0.024, +0.465] | +0.214 | [-0.580, +0.583] | 0.493 |
| scenario_fit − best_constant | -22.602 | +0.617 [+0.488, +0.940] | +0.179 | [+0.208, +1.834] | 1.15e-10 |
| ppo − best_constant | -22.367 | +0.329 [-0.090, +0.558] | +0.415 | [-0.525, +0.992] | 0.0761 |
| ppo − best_constant_ext | -22.367 | -0.266 [-0.439, -0.016] | +0.136 | [-1.071, +0.155] | 0.000689 |
| ppo − ppo_distilled | -22.367 | +0.180 [+0.069, +0.272] | +0.201 | [-0.048, +0.440] | 4.4e-05 |
| ppo − scenario_fit | -22.367 | -0.220 [-0.584, -0.009] | +0.236 | [-1.108, +0.141] | 0.000437 |
| ppo_distilled_pooled − best_constant | -22.563 | +0.204 [-0.010, +0.459] | +0.219 | [-0.584, +0.584] | 0.458 |
| ppo − ppo_distilled_pooled | -22.367 | +0.182 [+0.044, +0.268] | +0.196 | [-0.059, +0.441] | 7.05e-05 |

## ood (n feasible = 92)

Constants: original [23.67, 0.01, 1.32] (val -10.173); extended [26.08, 0.0, 2.0] (val -9.767); distilled from `ppo_s2` [19.55, 0.0, 1.23]; scenario fit (val -9.333); PPO val -9.856.

| comparison (A minus B) | A mean return | Δmedian [95 % CI] | Δmean | IQR of Δ | p |
|---|---|---|---|---|---|
| best_constant_ext − best_constant | -7.558 | +0.326 [+0.103, +0.544] | +0.954 | [-0.002, +1.295] | 6.12e-10 |
| ppo_distilled − best_constant | -8.171 | +0.360 [+0.342, +0.381] | +0.341 | [+0.290, +0.415] | 1.27e-11 |
| scenario_fit − best_constant | -8.018 | +0.335 [+0.267, +0.471] | +0.494 | [+0.126, +0.618] | 4.06e-07 |
| ppo − best_constant | -7.954 | +0.446 [+0.359, +0.561] | +0.558 | [+0.301, +0.654] | 3.74e-14 |
| ppo − best_constant_ext | -7.954 | +0.082 [-0.237, +0.230] | -0.396 | [-0.705, +0.322] | 0.0413 |
| ppo − ppo_distilled | -7.954 | +0.043 [-0.012, +0.151] | +0.218 | [-0.030, +0.339] | 4.34e-05 |
| ppo − scenario_fit | -7.954 | +0.008 [-0.038, +0.053] | +0.064 | [-0.122, +0.321] | 0.443 |
| ppo_distilled_pooled − best_constant | -8.171 | +0.357 [+0.339, +0.382] | +0.341 | [+0.291, +0.414] | 1.31e-11 |
| ppo − ppo_distilled_pooled | -7.954 | +0.044 [-0.012, +0.150] | +0.218 | [-0.031, +0.339] | 4.27e-05 |

