# Closed-loop behaviour by parameter set (preliminary twin, simulated)

Fixed-PID test sequence, 90 deg step, bare shaft, 2 s. Alternative sets (method_d*) are inactive.

| set | case | rise [s] | overshoot [%] | settle [s] | SSE [deg] | IAE [deg s] | peak I [A] |
|---|---|---|---|---|---|---|---|
| method_a | 1 low P | 0.509 | 2.64 | 1.253 | -0.051 | 32.50 | 1.47 |
| method_a | 2a higher P | 0.110 | 39.01 | 1.022 | 0.033 | 18.80 | 7.50 |
| method_a | 2b highest P | 0.108 | 36.35 | 1.061 | 0.008 | 17.35 | 10.01 |
| method_a | 3 P+D (Tuned) | 0.117 | 23.70 | 0.602 | 0.005 | 13.79 | 7.50 |
| method_a | 4 P+I | 0.110 | 40.65 | 1.462 | -0.161 | 21.51 | 7.50 |
| method_a | 5 full PID | 0.116 | 24.53 | 0.607 | -0.019 | 14.02 | 7.50 |
| method_a | legacy default | 0.143 | 66.82 | never | 3.913 | 44.94 | 7.50 |
| method_c | 1 low P | 1.765 | 0.00 | never | -7.992 | 71.11 | 1.47 |
| method_c | 2a higher P | 0.171 | 6.65 | 0.467 | -0.003 | 13.25 | 7.50 |
| method_c | 2b highest P | 0.157 | 11.22 | 0.459 | 0.012 | 13.14 | 7.50 |
| method_c | 3 P+D (Tuned) | 0.190 | 1.73 | 0.292 | -0.011 | 13.00 | 7.50 |
| method_c | 4 P+I | 0.169 | 9.72 | 0.531 | 0.145 | 14.46 | 7.50 |
| method_c | 5 full PID | 0.188 | 3.04 | 0.514 | 0.690 | 14.50 | 7.50 |
| method_c | legacy default | 0.223 | 42.18 | 1.826 | 1.351 | 38.53 | 7.50 |
| method_d | 1 low P | 1.628 | 0.00 | never | -6.239 | 64.13 | 1.47 |
| method_d | 2a higher P | 0.152 | 0.03 | 0.247 | 0.009 | 9.36 | 7.50 |
| method_d | 2b highest P | 0.126 | 4.24 | 0.239 | -0.018 | 8.88 | 7.50 |
| method_d | 3 P+D (Tuned) | 0.192 | 0.00 | 0.348 | -0.018 | 10.51 | 7.50 |
| method_d | 4 P+I | 0.147 | 3.22 | 0.709 | 0.262 | 11.28 | 7.50 |
| method_d | 5 full PID | 0.186 | 1.48 | 0.310 | 0.872 | 11.98 | 7.50 |
| method_d | legacy default | 0.216 | 31.49 | 1.772 | 0.191 | 28.98 | 7.50 |
| method_d2 | 1 low P | 1.628 | 0.00 | never | -6.239 | 64.13 | 1.47 |
| method_d2 | 2a higher P | 0.152 | 0.03 | 0.247 | 0.009 | 9.36 | 7.50 |
| method_d2 | 2b highest P | 0.126 | 4.24 | 0.239 | -0.018 | 8.88 | 7.50 |
| method_d2 | 3 P+D (Tuned) | 0.192 | 0.00 | 0.348 | -0.018 | 10.51 | 7.50 |
| method_d2 | 4 P+I | 0.147 | 3.22 | 0.709 | 0.262 | 11.28 | 7.50 |
| method_d2 | 5 full PID | 0.186 | 1.48 | 0.310 | 0.872 | 11.98 | 7.50 |
| method_d2 | legacy default | 0.216 | 31.49 | 1.772 | 0.191 | 28.98 | 7.50 |
| method_d3 | 1 low P | 1.628 | 0.00 | never | -6.239 | 64.13 | 1.47 |
| method_d3 | 2a higher P | 0.152 | 0.03 | 0.247 | 0.009 | 9.36 | 7.50 |
| method_d3 | 2b highest P | 0.126 | 4.24 | 0.239 | -0.018 | 8.88 | 7.50 |
| method_d3 | 3 P+D (Tuned) | 0.192 | 0.00 | 0.348 | -0.018 | 10.51 | 7.50 |
| method_d3 | 4 P+I | 0.147 | 3.22 | 0.709 | 0.262 | 11.28 | 7.50 |
| method_d3 | 5 full PID | 0.186 | 1.48 | 0.310 | 0.872 | 11.98 | 7.50 |
| method_d3 | legacy default | 0.216 | 31.49 | 1.772 | 0.191 | 28.98 | 7.50 |

## Gravity-loaded arm (1 kg x 10 cm, Tuned gains): the gearbox efficiency matters here

| set | overshoot [%] | settle [s] | SSE [deg] | peak I [A] | torque margin | status |
|---|---|---|---|---|---|---|
| method_a | 6.20 | never | -19.776 | 7.50 | 2.17 | ok |
| method_c | 0.00 | never | -19.827 | 7.50 | 2.17 | ok |
| method_d | 0.00 | never | -16.212 | 7.50 | 2.72 | ok |
| method_d2 | 0.00 | never | -7.250 | 7.50 | 6.26 | ok |
| method_d3 | 0.00 | never | -17.481 | 7.50 | 2.50 | ok |

## Spread across sets for the Tuned gains (bare shaft)

- overshoot_pct: 0 to 23.7
- settle_s: 0.292 to 0.602
- rise_s: 0.117 to 0.192
- iae_deg_s: 10.5 to 13.8
