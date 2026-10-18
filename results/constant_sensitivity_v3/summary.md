# Constant-gain sensitivity (POST HOC, simulation only)

Added after the confirmatory runs because the learned policies end at nearly constant gains. Both new constants are derived on validation seeds (40000..40039); the test seeds (60000..60099) are used once for evaluation. Paired differences are to the ORIGINAL best constant (feasible scenarios; median [95 % bootstrap CI] / mean / Wilcoxon p, unadjusted).

## static

Constants: original [18.94, 0.01, 1.32] (val -8.099), extended [28.54, 0.0, 2.0] (val -7.614), distilled from `ppo_s1` [26.09, 0.0, 1.8].

| controller | return mean | Δmedian [95 % CI] | Δmean | p |
|---|---|---|---|---|
| best_constant | -7.191 | +0.000 [+0.000, +0.000] | +0.000 | -- |
| best_constant_ext | -6.314 | +0.479 [+0.238, +0.635] | +0.877 | 1.11e-12 |
| ppo_distilled | -6.388 | +0.503 [+0.310, +0.599] | +0.803 | 2.55e-16 |
| ppo | -6.053 | +0.610 [+0.286, +0.752] | +1.138 | 5.15e-14 |

## changes

Constants: original [29.59, 0.01, 1.32] (val -19.770), extended [41.82, 0.0, 2.0] (val -19.002), distilled from `ppo_s1` [27.06, 0.0, 1.81].

| controller | return mean | Δmedian [95 % CI] | Δmean | p |
|---|---|---|---|---|
| best_constant | -18.935 | +0.000 [+0.000, +0.000] | +0.000 | -- |
| best_constant_ext | -17.533 | +0.601 [+0.424, +1.225] | +1.402 | 4.69e-10 |
| ppo_distilled | -18.164 | +0.075 [-0.150, +0.626] | +0.771 | 0.0261 |
| ppo | -17.402 | +0.579 [+0.244, +1.227] | +1.533 | 1.75e-06 |

## ood

Constants: original [23.67, 0.01, 1.32] (val -10.173), extended [26.08, 0.0, 2.0] (val -9.767), distilled from `ppo_s1` [26.16, 0.0, 1.79].

| controller | return mean | Δmedian [95 % CI] | Δmean | p |
|---|---|---|---|---|
| best_constant | -8.736 | +0.000 [+0.000, +0.000] | +0.000 | -- |
| best_constant_ext | -7.891 | +0.211 [+0.072, +0.468] | +0.845 | 4.31e-08 |
| ppo_distilled | -7.993 | +0.285 [+0.168, +0.519] | +0.742 | 7.02e-16 |
| ppo | -7.684 | +0.452 [+0.236, +0.737] | +1.051 | 3.65e-12 |

