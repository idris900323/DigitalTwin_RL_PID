# Parameter ranking

1. Jm (0.85): rotor inertia: free-run speed decay / mechanical time constant, ideally with a known added inertia
2. R (0.41): winding resistance: low-voltage locked-rotor test with a current limit (or 4-wire ohmmeter)
3. Kt (0.30): torque constant: measure stall/low-speed torque against current with a torque arm
4. Ke (0.25): back-EMF constant: speed-versus-voltage line at several voltages, or coast-down generator voltage
5. Bm (0.17): viscous friction: steady-state speed versus current at low speeds, both directions
6. V_supply (0.08): supply voltage under load: log the rail during a step with the real supply and wiring
7. L (0.07): armature inductance: LCR meter or a voltage-step current rise
8. delay_steps (0.03): loop dead time: timing audit of the real controller/driver (scope on command and PWM)
9. eta (0.00): gearbox efficiency: loaded versus no-load current at a known output torque
