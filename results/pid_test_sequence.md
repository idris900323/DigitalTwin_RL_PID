# Fixed-PID test sequence (preliminary twin)

Parameter set `method_c`, target 90 deg, 2 s, dt 1 ms, arm 0 kg x 0 m, gravity off, encoder noise 0 counts RMS (seed 0). Datasheet-derived parameters, not validated on hardware.

| case | Kp | Ki | Kd | rise_s [s] | overshoot_pct [%] | settle_s [s] | time_to_2pct_s [s] | sse_deg [deg] | rmse_deg [deg] | mae_deg [deg] | iae_deg_s [deg s] | ise_deg2_s [deg^2 s] | itae_deg_s2 [deg s^2] | effort_abs_Vs [V s] | effort_sq_V2s [V^2 s] | peak_current_A [A] | energy_J [J] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 low P | 1.5 | 0 | 0 | 1.7650 | 0.0000 | never | never | -7.9922 | 42.9245 | 35.5549 | 71.1098 | 3693.1140 | 44.4564 | 1.8616 | 2.5312 | 1.4726 | 0.2672 |
| 2a higher P | 15 | 0 | 0 | 0.1710 | 6.6499 | 0.4670 | 0.2510 | -0.0025 | 20.0932 | 6.6271 | 13.2542 | 815.6046 | 1.4113 | 2.5143 | 24.4817 | 7.5000 | 5.8281 |
| 2b highest P | 45 | 0 | 0 | 0.1570 | 11.2157 | 0.4590 | 0.2230 | 0.0117 | 20.0636 | 6.5696 | 13.1393 | 813.2164 | 1.3659 | 3.4818 | 34.0914 | 7.5000 | 9.2445 |
| 3 P+D (Tuned) | 15 | 0 | 0.3 | 0.1900 | 1.7275 | 0.2920 | 0.2920 | -0.0106 | 20.1694 | 6.5008 | 13.0016 | 821.7193 | 1.2428 | 2.1807 | 21.7983 | 7.5000 | 5.3560 |
| 4 P+I | 15 | 20 | 0 | 0.1690 | 9.7212 | 0.5310 | 0.2450 | 0.1448 | 20.1681 | 7.2290 | 14.4580 | 821.6242 | 2.3280 | 2.6250 | 25.0608 | 7.5000 | 5.8607 |
| 5 full PID | 15 | 5 | 0.3 | 0.1880 | 3.0382 | 0.5140 | 0.2850 | 0.6897 | 20.1845 | 7.2510 | 14.5021 | 822.9467 | 2.9116 | 2.2142 | 21.9756 | 7.5000 | 5.3604 |
| legacy default | 5 | 20 | 0.05 | 0.2230 | 42.1802 | 1.8260 | 0.3060 | 1.3514 | 27.9194 | 19.2652 | 38.5304 | 1567.0902 | 21.0075 | 4.3052 | 22.4246 | 7.5000 | 3.6158 |

## What the sequence shows

Low P (Kp = 1.5) is too slow: after 2 s the joint is still 7.99 deg from the 90 deg target and the command only reaches 0.9 V on average, far below the 12 V limit. Raising Kp to 15 and 45 cuts the rise time to 0.171 s and 0.157 s but overshoot grows to 6.65 % and 11.22 %; the voltage saturates at the supply limit, so the rise time is saturation-limited and tripling Kp buys little (0.171 s to 0.157 s). Adding D (Kd = 0.3) damps the response: overshoot falls from 6.65 % to 1.73 % and the settling time from 0.467 s to 0.292 s. Adding I (Ki = 20) does not help on the bare shaft: there is no load torque to remove (P-only steady-state error -0.003 deg), so the integral only adds overshoot (9.72 %) and a slower settle (0.531 s); its steady-state error after 2 s is +0.145 deg because it is still unwinding. The full PID (15 / 5 / 0.3) gives 3.04 % overshoot, 0.514 s settling and +0.690 deg error at 2 s. The legacy default gains give 42.2 % overshoot for comparison.
