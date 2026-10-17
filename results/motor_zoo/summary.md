# Synthetic motor zoo (simulated, preliminary)

20 random but physically consistent motors; Tier 1 pipeline on the published-style datasheet text only; judged on the TRUE plant. Generation assumptions are in `tuning/zoo.py` (rotor inertia log-normal sigma 0.6 around the mass-based approximation, efficiency 0.45-0.9, ...); the calibration numbers depend on them.

| criterion | result |
|---|---|
| imported | 20 of 20 |
| Tier 1 gains stable on the true plant | 100 % |
| meet the overshoot, settling and accuracy spec on the true plant | 100 % |
| price of uncertainty: cost vs gains optimised with perfect knowledge (median / 90th percentile ratio) | 1.25 / 1.96 |
| true-plant metrics inside the predicted 5th-95th percentile band | overshoot [%] 85 %, settling time [s] 95 %, peak current [A] 85 % (mean 88 %; target about 90 %) |
| true parameter inside the derived interval | R 100 %, K 100 %, Jm 95 % |

## Per motor

| motor | V | N | stable | meets spec | cost ratio | overshoot % | settling s | datasheet conflicts |
|---|---|---|---|---|---|---|---|---|
| zoo_000 | 48 | 100 | True | True | 1.00 | 0.00 | 0.464 | - |
| zoo_001 | 12 | 50 | True | True | 1.15 | 0.00 | 0.294 | - |
| zoo_002 | 48 | 19 | True | True | 1.99 | 0.02 | 0.418 | - |
| zoo_003 | 48 | 10 | True | True | 9.93 | 0.08 | 0.855 | - |
| zoo_004 | 24 | 250 | True | True | 1.25 | 0.01 | 0.554 | - |
| zoo_005 | 24 | 150 | True | True | 1.13 | 0.02 | 0.461 | - |
| zoo_006 | 12 | 50 | True | True | 1.10 | 0.00 | 0.226 | - |
| zoo_007 | 48 | 100 | True | True | 1.66 | 0.03 | 0.597 | - |
| zoo_008 | 24 | 30 | True | True | 1.43 | 0.03 | 0.157 | - |
| zoo_009 | 12 | 250 | True | True | 1.07 | 0.01 | 0.626 | - |
| zoo_010 | 48 | 250 | True | True | 1.17 | 0.01 | 0.675 | - |
| zoo_011 | 6 | 10 | True | True | 1.95 | 0.04 | 0.407 | - |
| zoo_012 | 24 | 19 | True | True | 1.26 | 0.02 | 0.126 | - |
| zoo_013 | 48 | 250 | True | True | 1.66 | 3.71 | 0.889 | - |
| zoo_014 | 6 | 150 | True | True | 1.43 | 0.03 | 0.637 | - |
| zoo_015 | 48 | 100 | True | True | 1.01 | 0.00 | 0.292 | - |
| zoo_016 | 24 | 50 | True | True | 1.03 | 0.00 | 0.236 | - |
| zoo_017 | 24 | 150 | True | True | 1.24 | 0.02 | 0.504 | - |
| zoo_018 | 48 | 30 | True | True | 1.40 | 0.01 | 0.223 | - |
| zoo_019 | 24 | 30 | True | True | 1.06 | 0.00 | 0.129 | - |
