# Parameter ranking

1. eta (0.60): gearbox efficiency: loaded versus no-load current at a known output torque
2. R (0.39): winding resistance: low-voltage locked-rotor test with a current limit (or 4-wire ohmmeter)
3. Ke (0.21): back-EMF constant: speed-versus-voltage line at several voltages, or coast-down generator voltage
4. Kt (0.21): torque constant: measure stall/low-speed torque against current with a torque arm
5. Bm (0.11): viscous friction: steady-state speed versus current at low speeds, both directions
6. Jm (0.10): rotor inertia: free-run speed decay / mechanical time constant, ideally with a known added inertia
7. V_supply (0.06): supply voltage under load: log the rail during a step with the real supply and wiring
8. L (0.05): armature inductance: LCR meter or a voltage-step current rise
9. delay_steps (0.01): loop dead time: timing audit of the real controller/driver (scope on command and PWM)
