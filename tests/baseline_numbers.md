# Baseline numbers (Task 0.2)

Reproduced from the repo's own classes on a clean checkout, **before any fix**.
Bare shaft, method_c, 90 deg step, 2 s, dt = 1 ms. Enforced by `tests/test_baseline.py`
(tolerances: rise/settle +/-0.005 s, overshoot +/-0.1 pp, SSE +/-0.01 deg).

| Case | Kp / Ki / Kd | Rise (s) | Overshoot | Settle (s) | SSE (deg) |
|---|---|---|---|---|---|
| Low P | 1.5 / 0 / 0 | 1.765 | 0 % | never | -7.99 |
| Mid P | 15 / 0 / 0 | 0.171 | 6.65 % | 0.467 | -0.003 |
| High P | 45 / 0 / 0 | 0.157 | 11.2 % | 0.459 | 0.012 |
| P+D (Tuned) | 15 / 0 / 0.3 | 0.190 | 1.73 % | 0.292 | -0.011 |
| P+I | 15 / 20 / 0 | 0.169 | 9.72 % | 0.531 | 0.145 |
| PID (legacy default) | 5 / 20 / 0.05 | 0.223 | 42.2 % | 1.826 | 1.351 |
| PID | 15 / 5 / 0.3 | 0.188 | 3.04 % | 0.514 | 0.690 |

Also pinned: open-loop no-load speed (A +121.3 %, B 18,000.6 RPM, C -11.3 %), mechanical
time constants (56 ms method_c, 146 ms method_a), unit helpers, timestep convergence
(0.5 / 1 / 2 ms -> 89.989 / 89.989 / 89.990 deg), method_a vs method_c on legacy gains.

Result on the day this was written: `pytest tests/test_baseline.py` -> 13 passed.
Every number in the overview reproduced; nothing was stale.
