# Glossary

**Anti-windup** Stopping the PID integrator from growing while the output is saturated. Here: conditional integration (the integral is not updated when the output is saturated and the error would push it further).

**Back-EMF (Ke)** Voltage a spinning motor generates, proportional to speed. Reduces armature current (and therefore available torque) as speed rises.

**Bandit (contextual bandit)** A one-step reinforcement-learning problem: observe a context (payload, target), choose an action (gains), receive a reward, done. The numpy auto-tuner is one.

**Bumpless transfer** Changing a controller parameter without a jump in its output. This PID is not bumpless for Ki changes (its integral state is the plain integral of error).

**CPR (counts per revolution)** Encoder resolution. 9360 at the output shaft = 13 Hall sensors x 4 (quadrature) x 180 (gear ratio).

**Domain randomisation** Training an RL agent on many randomly varied plants so it does not overfit one.

**Elementary effect / Morris screening** A cheap global sensitivity method: random one-factor-at-a-time steps along trajectories; mu* (mean absolute effect) ranks parameters.

**Feasibility margin** Available output stall torque divided by the peak gravity holding torque along the path. Below 1 the payload cannot be driven to the target. It is an upper bound (it ignores back-EMF).

**FIT %** 100 x (1 - ||y - yhat|| / ||y - mean(y)||): agreement of a simulated signal with a measured one.

**IAE / ISE / ITAE** Integral of absolute error / squared error / time-weighted absolute error of a step response.

**Identifiability** Whether the data determine a parameter. Checked here from the Jacobian null space; non-identifiable parameters get no value.

**Kt, Ke** Torque constant [N.m/A] and back-EMF constant [V.s/rad]. For an ideal motor in SI they are numerically equal.

**Ljung-Box test** Tests whether residuals are white noise; a small p-value means structured, unmodelled dynamics.

**Method A / B / C / D** Alternative sets of (R, Kt, Ke) derived from the datasheet; C is the active one, D-variants are inactive alternatives.

**NRMSE** RMSE divided by the peak-to-peak of the measured signal.

**Oracle (test)** The original code used as the reference the refactored code must reproduce.

**Pre-validation prototype** Label for everything learned on the unvalidated twin.

**PRBS** Pseudo-random binary sequence: a rich, bounded excitation used for identification.

**REINFORCE** The simplest policy-gradient algorithm; the auto-tuner uses it with a per-context baseline.

**RK4** Classic fourth-order Runge-Kutta integrator.

**Saturation-limited** A response whose speed is set by the voltage limit rather than by the gains.

**Tier (1/2/3)** Trust level of a tuning recommendation: datasheet estimate, bench-identified, refined on hardware.

**Twin, preliminary** A model that has not yet passed the validation thresholds against bench data.
