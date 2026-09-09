# RMCS-3013 / RMCS-3070 Johnson Quad-Encoder Geared DC Motor — Parameter Table

Source document: `RMCS-3013_RMCS-3070_datasheet.pdf` (title block reads "RMCS-3013"; project
brief specifies "RMCS-3070" — specs match exactly, model-number mismatch flagged,
not resolved as of this writing; see note at bottom).

Provenance categories per master prompt §3/§11: DATASHEET, CALCULATED, ESTIMATED,
ASSUMED, CAD, EXPERIMENTAL (not used this phase).

## Directly stated (DATASHEET)

| Parameter | Value | Unit | Confidence |
|---|---|---|---|
| Operating voltage V | 12 | V | High |
| Output speed | 100 | RPM | High |
| Gear ratio N | 180:1 | — | High |
| Stall torque (output) | 27.18 | kg·cm | High |
| Rated torque (output) | 12.5 | kg·cm | High |
| Weight | 180 | g | High |
| Hall sensors | 13 | — | High |
| Quadrature multiplier | 4 | — | High |
| Base motor CPR | 52 (=13×4) | counts/rev | High |
| Output CPR | 9360 (=52×180) | counts/rev | High — arithmetic confirmed exact |
| Base motor nominal voltage | 12 | V | High |
| Base motor no-load speed | 18,000 | RPM | High |
| Base motor no-load current | 0.8 | A | High |
| Base motor "rated torque" | 151 | g·cm | High as printed, **low as a physically independent quantity — see flag below** |
| Load current | up to 7.5 (Max) | A | High as printed; ambiguous whether this is locked-rotor stall current or a different operating-current ceiling |
| Flange diameter | 31 | mm | High |
| Bolt circle diameter | 26.85 | mm | High |
| Mounting holes | 4× M2.5×6 | — | High |
| Output shaft diameter | 6 | mm | High |
| Output shaft length (100 RPM variant) | 26.5 | mm | High |
| Gearbox body diameter | 36 | mm | High |
| Motor body diameter | 30 | mm | High |
| Total length | 55.50 | mm | High |
| Encoder supply | 5 | V | High |

## Unit conversions (shown explicitly, never silent)

- RPM → rad/s: ×2π/60
- kg·cm → N·m: ×0.0980665
- g·cm → N·m: ×9.80665×10⁻⁵

| Quantity | Raw | SI | Tag |
|---|---|---|---|
| ω_nl,base | 18,000 RPM | 1884.96 rad/s | CALCULATED |
| τ_stall,out | 27.18 kg·cm | 2.6652 N·m | CALCULATED |
| τ_rated,out | 12.5 kg·cm | 1.2258 N·m | CALCULATED |
| τ_"rated",base | 151 g·cm | 0.014808 N·m | CALCULATED |

## Derived electrical parameters — two independent, disagreeing methods (both retained)

**Method A** (assumes 7.5 A = locked-rotor stall current at 12 V, gearbox η=1 for
reflecting output stall torque to the base motor shaft):

| Parameter | Value | Method | Confidence |
|---|---|---|---|
| R | 1.6 Ω | V / i_stall | Low — depends on unverified stall-current assumption |
| Kt | 1.974×10⁻³ N·m/A | (τ_stall,out / N) / i_stall, η=1 assumed | Low |
| Ke | 1.974×10⁻³ V·s/rad | Ke ≈ Kt (ideal SI identity) | Low |

**Method B** (no-load speed based, neglects R·i_nl drop):

| Parameter | Value | Method | Confidence |
|---|---|---|---|
| Ke | 6.366×10⁻³ V·s/rad | V / ω_nl,base | Low |

The two Ke estimates disagree by ~3.2×. Both are carried forward in
`config/motor_parameters.yaml` as labeled scenarios (`method_a`, `method_b`) rather
than collapsed into one number. Resolving this requires either a confirmed stall-current
figure or an experimental measurement (explicitly deferred, per project scope).

## Not derivable from this datasheet (ESTIMATED / ASSUMED placeholders)

| Parameter | Placeholder | Tag | Notes |
|---|---|---|---|
| Armature inductance L | 0 H (neglected) | ASSUMED | Typical small brushed DC motors: tens of µH–low mH; electrical time constant ≪ mechanical time constant, so neglecting is a standard simplification, not fabrication. Revisit in sensitivity analysis. |
| Rotor inertia Jm | 5×10⁻⁷ kg·m² | ESTIMATED | Order-of-magnitude only, comparable small (~180 g) brushed DC motors. Wide uncertainty. |
| Viscous friction Bm | 1×10⁻⁶ N·m·s/rad | ESTIMATED | Order-of-magnitude only. Wide uncertainty. |
| Gearbox efficiency η_gb | 0.80 | ESTIMATED | Typical small spur/planetary gearbox range 0.70–0.85. |

## Flags / open items

1. **Model number mismatch**: datasheet title block says "RMCS-3013"; project brief
   says "RMCS-3070." All numeric specs match exactly. Treated as the same
   product line / naming inconsistency, not re-verified against a second source.
2. **"151 g·cm base motor rated torque" is numerically identical to
   `τ_stall,out / N` at η=1** (27.18 kg·cm / 180 = 0.151 kg·cm exactly). This is very
   likely a reflected/derived value rather than an independently measured
   motor-side rated-torque point. Not used as an independent data point in any
   derivation above.
3. **Base motor characteristic graph** (E/P/I/N vs. torque, torque axis to 1400 g·cm)
   visually suggests true base-motor stall torque is far higher than 151 g·cm — the
   speed curve does not appear to reach zero until well up the torque axis. This
   graph was **not digitized** (resolution/watermarking make a precise numeric read
   unreliable) and no values were taken from it. Flagged as a possible future
   refinement source only.
4. **"Load current up to 7.5A (Max)"** is not explicitly labeled "stall current" —
   Method A's use of it as such is an assumption, not a confirmed fact.
5. Manufacturer-rated "stall torque" for geared motors is often a practical/current-
   limited rating rather than the base motor's theoretical zero-speed stall torque —
   worth remembering when interpreting Method A results.
