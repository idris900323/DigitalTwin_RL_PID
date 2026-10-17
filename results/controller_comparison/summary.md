# Controller comparison (PRE-VALIDATION, simulated on the unvalidated twin)

100 held-out paired scenarios per regime (seeds 50000..50099, never used in training). Every controller sees the same plant, payload, target, delay and noise for a given seed. `return` is the environment reward (higher is better); IAE in deg*s (lower is better). `random_search` is an oracle: best of 16 random gain sets + Tuned + bandit per scenario, chosen with hindsight, so it is an upper bound for any fixed-gain strategy, not a deployable controller.

## Regime `static`

| controller | return mean ± std | Δreturn vs Tuned [95 % CI] | p (Wilcoxon) | IAE mean | overshoot % | settle s | success | diverged |
|---|---|---|---|---|---|---|---|---|
| tuned | -14.157 ± 14.626 | +0.000 [+0.000, +0.000] | nan | 44.6 | 18.3 | 1.026 | 12 % | 0 % |
| legacy | -54.705 ± 50.186 | -40.548 [-50.232, -31.961] | 6.61e-17 | 83.5 | 54.9 | 1.384 | 2 % | 0 % |
| zn | -20.491 ± 28.714 | -6.334 [-11.336, -2.079] | 0.421 | 63.9 | 7.4 | 0.815 | 55 % | 0 % |
| bandit | -9.689 ± 14.971 | +4.468 [+3.677, +5.334] | 5.07e-17 | 36.6 | 4.9 | 0.501 | 69 % | 0 % |
| random_search | -8.882 ± 15.029 | +5.275 [+4.332, +6.311] | 5.57e-17 | 36.8 | 0.4 | 0.440 | 86 % | 0 % |
| ppo_s0 | -10.597 ± 14.936 | +3.560 [+2.911, +4.265] | 4.12e-16 | 37.7 | 9.4 | 0.492 | 41 % | 0 % |
| ppo_s1 | -10.771 ± 14.635 | +3.386 [+2.734, +4.096] | 6.54e-17 | 37.9 | 10.6 | 0.543 | 36 % | 0 % |
| ppo_s2 | -9.870 ± 14.799 | +4.287 [+3.489, +5.143] | 4.88e-17 | 37.8 | 4.5 | 0.528 | 62 % | 0 % |

Per-context breakdown of mean return (best PPO seed `ppo_s2` vs Tuned vs bandit):

| context | n | Tuned | bandit | ppo_s2 |
|---|---|---|---|---|
| no payload | 19 | -7.492 | -5.035 | -4.830 |
| payload + gravity | 33 | -20.795 | -18.223 | -18.421 |
| payload, no gravity | 48 | -12.232 | -5.663 | -5.987 |

Worst five scenarios for `ppo_s2` relative to Tuned (failure analysis):

| seed | context | target deg | mass kg | Δreturn | PPO overshoot % | PPO final gains | Tuned overshoot % |
|---|---|---|---|---|---|---|---|
| 50036 | no payload | 71 | 0.00 | -0.347 | 0.1 | 50.0/0.00/5.00 | 0.2 |
| 50043 | no payload | 71 | 0.00 | -0.266 | 0.0 | 50.0/0.00/5.00 | 0.2 |
| 50086 | no payload | 93 | 0.00 | -0.227 | 0.0 | 50.0/0.00/5.00 | 1.0 |
| 50084 | payload + gravity | 174 | 1.76 | -0.136 | 0.0 | 50.0/0.00/5.00 | 0.0 |
| 50027 | payload + gravity | 166 | 1.76 | -0.080 | 0.0 | 50.0/0.00/5.00 | 0.0 |

## Regime `changes`

| controller | return mean ± std | Δreturn vs Tuned [95 % CI] | p (Wilcoxon) | IAE mean | overshoot % | settle s | success | diverged |
|---|---|---|---|---|---|---|---|---|
| tuned | -34.248 ± 44.284 | +0.000 [+0.000, +0.000] | nan | 69.4 | 67.2 | 1.337 | 14 % | 0 % |
| legacy | -105.105 ± 148.061 | -70.856 [-96.788, -51.491] | 7.1e-17 | 98.8 | 113.0 | 1.640 | 0 % | 0 % |
| zn | -37.091 ± 48.658 | -2.842 [-12.723, +6.383] | 0.17 | 75.5 | 45.3 | 1.315 | 43 % | 0 % |
| bandit | -29.460 ± 82.864 | +4.789 [-5.485, +10.681] | 1.87e-14 | 60.6 | 52.3 | 1.103 | 43 % | 0 % |
| random_search | -17.271 ± 18.497 | +16.978 [+11.396, +24.092] | 3.9e-18 | 56.6 | 23.7 | 1.029 | 49 % | 0 % |
| ppo_s0 | -34.435 ± 99.080 | -0.186 [-14.118, +7.831] | 3.4e-06 | 62.1 | 53.5 | 1.081 | 34 % | 0 % |
| ppo_s1 | -34.288 ± 87.737 | -0.040 [-11.775, +6.911] | 0.000186 | 62.8 | 54.5 | 1.168 | 35 % | 0 % |
| ppo_s2 | -30.540 ± 86.990 | +3.709 [-7.863, +10.727] | 1.96e-10 | 61.1 | 47.5 | 1.093 | 40 % | 0 % |

Per-context breakdown of mean return (best PPO seed `ppo_s2` vs Tuned vs bandit):

| context | n | Tuned | bandit | ppo_s2 |
|---|---|---|---|---|
| no payload | 19 | -35.378 | -28.001 | -25.783 |
| payload + gravity | 33 | -45.703 | -49.037 | -51.156 |
| payload, no gravity | 48 | -25.926 | -16.578 | -18.249 |

Worst five scenarios for `ppo_s2` relative to Tuned (failure analysis):

| seed | context | target deg | mass kg | Δreturn | PPO overshoot % | PPO final gains | Tuned overshoot % |
|---|---|---|---|---|---|---|---|
| 50046 | payload + gravity | 134 | 0.84 | -480.450 | 0.0 | 37.8/0.00/5.00 | 0.0 |
| 50031 | no payload | 137 | 0.00 | -28.975 | 46.7 | 50.0/0.00/5.00 | 70.8 |
| 50066 | payload + gravity | 160 | 1.71 | -9.752 | 279.3 | 50.0/0.00/5.00 | 272.6 |
| 50091 | payload, no gravity | 159 | 0.43 | -9.242 | 294.8 | 50.0/0.00/5.00 | 331.2 |
| 50050 | no payload | 123 | 0.00 | -8.633 | 198.4 | 50.0/0.00/5.00 | 244.1 |

## Regime `ood`

| controller | return mean ± std | Δreturn vs Tuned [95 % CI] | p (Wilcoxon) | IAE mean | overshoot % | settle s | success | diverged |
|---|---|---|---|---|---|---|---|---|
| tuned | -16.460 ± 18.252 | +0.000 [+0.000, +0.000] | nan | 49.7 | 16.5 | 0.872 | 22 % | 0 % |
| legacy | -55.571 ± 54.165 | -39.111 [-48.872, -29.835] | 5.2e-17 | 84.8 | 51.8 | 1.372 | 1 % | 0 % |
| zn | -21.277 ± 28.552 | -4.817 [-9.375, -0.703] | 0.878 | 65.7 | 8.1 | 0.871 | 48 % | 0 % |
| bandit | -11.966 ± 17.984 | +4.494 [+3.492, +5.603] | 2.46e-15 | 42.2 | 5.8 | 0.593 | 67 % | 0 % |
| random_search | -10.599 ± 17.889 | +5.861 [+4.454, +7.458] | 7.99e-16 | 41.5 | 0.5 | 0.478 | 84 % | 0 % |
| ppo_s0 | -12.398 ± 17.802 | +4.061 [+3.046, +5.217] | 3.04e-13 | 42.6 | 8.4 | 0.537 | 46 % | 0 % |
| ppo_s1 | -12.516 ± 17.549 | +3.944 [+2.924, +5.115] | 7.71e-14 | 42.8 | 9.1 | 0.584 | 43 % | 0 % |
| ppo_s2 | -11.516 ± 17.672 | +4.944 [+3.689, +6.399] | 5.64e-14 | 43.0 | 3.8 | 0.608 | 65 % | 0 % |

Per-context breakdown of mean return (best PPO seed `ppo_s2` vs Tuned vs bandit):

| context | n | Tuned | bandit | ppo_s2 |
|---|---|---|---|---|
| no payload | 19 | -8.413 | -5.844 | -5.481 |
| payload + gravity | 33 | -25.040 | -22.472 | -22.576 |
| payload, no gravity | 48 | -13.746 | -7.166 | -6.302 |

Worst five scenarios for `ppo_s2` relative to Tuned (failure analysis):

| seed | context | target deg | mass kg | Δreturn | PPO overshoot % | PPO final gains | Tuned overshoot % |
|---|---|---|---|---|---|---|---|
| 50036 | no payload | 71 | 0.00 | -2.151 | 2.0 | 50.0/0.00/5.00 | 0.0 |
| 50043 | no payload | 71 | 0.00 | -0.346 | 0.1 | 50.0/0.00/5.00 | 0.0 |
| 50039 | payload, no gravity | 93 | 0.44 | -0.340 | 0.0 | 50.0/0.00/5.00 | 0.0 |
| 50086 | no payload | 93 | 0.00 | -0.337 | 0.1 | 50.0/0.00/5.00 | 0.0 |
| 50088 | no payload | 91 | 0.00 | -0.303 | 0.1 | 50.0/0.00/5.00 | 0.0 |

## Verdict

- `static`: best PPO seed `ppo_s2` is BETTER than tuned (Δreturn +4.287, 95 % CI [+3.489, +5.143]).
- `static`: best PPO seed `ppo_s2` is statistically indistinguishable from bandit (Δreturn -0.182, 95 % CI [-0.510, +0.154]).
- `static`: best PPO seed `ppo_s2` is WORSE than random_search (oracle) (Δreturn -0.988, 95 % CI [-1.245, -0.760]).
- `changes`: best PPO seed `ppo_s2` is statistically indistinguishable from tuned (Δreturn +3.709, 95 % CI [-7.863, +10.727]).
- `changes`: best PPO seed `ppo_s2` is statistically indistinguishable from bandit (Δreturn -1.080, 95 % CI [-2.887, +1.225]).
- `changes`: best PPO seed `ppo_s2` is WORSE than random_search (oracle) (Δreturn -13.269, 95 % CI [-30.114, -3.749]).
- `ood`: best PPO seed `ppo_s2` is BETTER than tuned (Δreturn +4.944, 95 % CI [+3.689, +6.399]).
- `ood`: best PPO seed `ppo_s2` is statistically indistinguishable from bandit (Δreturn +0.450, 95 % CI [-0.088, +1.109]).
- `ood`: best PPO seed `ppo_s2` is WORSE than random_search (oracle) (Δreturn -0.917, 95 % CI [-1.200, -0.649]).

The best seed is picked on these same scenarios, which favours it (selection bias): treat its numbers as optimistic and compare the seed spread in the tables above. Return is the training objective; IAE, overshoot, settling time and success rate are controller-agnostic checks.


Everything above is simulated on the preliminary twin and has not been validated on hardware.
