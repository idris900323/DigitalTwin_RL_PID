# Kd-bound check (POST HOC, simulation only): extended constants with the Kd bound raised from 2 to 4.0

Constants derived on validation seeds (40000..40039); evaluated once on fresh seeds 90000..90099 (feasible scenarios). The policy is evaluated in its own training environment (Kd bound 2). Paired differences A - B: median [95 % CI] / mean / IQR / Wilcoxon p (unadjusted).

## static (n feasible = 96)

Extended constant, Kd bound 2: [28.54, 0.0, 2.0] (val -7.614); Kd bound 4.0: [28.54, 0.0, 2.0] (val -7.614).

| A - B | A mean return | Δmedian [95 % CI] | Δmean | IQR of Δ | p |
|---|---|---|---|---|---|
| best_constant_ext − best_constant | -6.337 | +0.456 [+0.364, +0.693] | +0.704 | [+0.101, +0.967] | 1.56e-13 |
| best_constant_ext_kd4 − best_constant | -6.337 | +0.456 [+0.364, +0.693] | +0.704 | [+0.101, +0.967] | 1.56e-13 |
| best_constant_ext_kd4 − best_constant_ext | -6.337 | +0.000 [+0.000, +0.000] | +0.000 | [+0.000, +0.000] | nan |
| ppo − best_constant | -6.179 | +0.561 [+0.411, +0.848] | +0.862 | [+0.132, +1.277] | 1.25e-14 |
| ppo − best_constant_ext | -6.179 | +0.098 [+0.075, +0.141] | +0.158 | [+0.035, +0.227] | 7.29e-12 |
| ppo − best_constant_ext_kd4 | -6.179 | +0.098 [+0.075, +0.141] | +0.158 | [+0.035, +0.227] | 7.29e-12 |

## changes (n feasible = 93)

Extended constant, Kd bound 2: [41.82, 0.0, 2.0] (val -19.002); Kd bound 4.0: [44.51, 0.0, 2.16] (val -18.986).

| A - B | A mean return | Δmedian [95 % CI] | Δmean | IQR of Δ | p |
|---|---|---|---|---|---|
| best_constant_ext − best_constant | -19.894 | +0.897 [+0.692, +1.153] | +1.989 | [+0.037, +1.748] | 3.43e-11 |
| best_constant_ext_kd4 − best_constant | -19.645 | +0.947 [+0.695, +1.229] | +2.239 | [-0.005, +1.880] | 6.32e-10 |
| best_constant_ext_kd4 − best_constant_ext | -19.645 | +0.042 [-0.009, +0.088] | +0.249 | [-0.086, +0.142] | 0.0146 |
| ppo − best_constant | -19.594 | +0.705 [+0.431, +1.086] | +2.289 | [-0.238, +2.421] | 9.73e-08 |
| ppo − best_constant_ext | -19.594 | -0.093 [-0.304, +0.153] | +0.300 | [-0.626, +0.595] | 0.874 |
| ppo − best_constant_ext_kd4 | -19.594 | -0.122 [-0.282, +0.191] | +0.050 | [-0.581, +0.530] | 0.808 |

## ood (n feasible = 96)

Extended constant, Kd bound 2: [26.08, 0.0, 2.0] (val -9.767); Kd bound 4.0: [24.35, 0.0, 1.76] (val -9.754).

| A - B | A mean return | Δmedian [95 % CI] | Δmean | IQR of Δ | p |
|---|---|---|---|---|---|
| best_constant_ext − best_constant | -7.864 | +0.329 [+0.112, +0.905] | +1.026 | [+0.012, +1.525] | 3.59e-10 |
| best_constant_ext_kd4 − best_constant | -7.984 | +0.402 [+0.195, +0.841] | +0.906 | [+0.112, +1.271] | 3.89e-16 |
| best_constant_ext_kd4 − best_constant_ext | -7.984 | +0.035 [-0.094, +0.080] | -0.120 | [-0.262, +0.106] | 0.0405 |
| ppo − best_constant | -7.835 | +0.432 [+0.266, +0.990] | +1.055 | [+0.060, +1.562] | 2.29e-13 |
| ppo − best_constant_ext | -7.835 | +0.045 [+0.031, +0.078] | +0.029 | [-0.022, +0.147] | 0.00394 |
| ppo − best_constant_ext_kd4 | -7.835 | +0.077 [+0.003, +0.136] | +0.149 | [-0.089, +0.276] | 0.00018 |

