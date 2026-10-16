# Validation report: <experiment id> / unit <id> / session <id>

Status of the twin for this report: **preliminary** until every threshold below is met on the data described here.
Fill in after each test family; keep the raw files read-only and cite their SHA-256.

## 1. Context

| Item | Value |
|---|---|
| Date / operator | |
| Motor label (RMCS-3013 or RMCS-3070?) and serial | |
| Firmware hash / host-tool commit / config SHA-256 | |
| Supply voltage and current limit | |
| Ambient / housing temperature (start, end) | |
| Safety checklist completed (initials) | |
| Calibrations today (current, voltage, encoder, timing): pass / fail | |
| Raw data files and SHA-256 | |
| Anomalies and deviations from `docs/validation_plan.md` | |

## 2. Instrument check (T1)

| Quantity | Measured | Requirement | Pass |
|---|---|---|---|
| Counts per output turn | | 9360 +- 1 | |
| Loop-period jitter | | < 100 us | |
| Current sensor offset / gain error | | | |
| Repeatability (CV of 30 identical runs) | | noise floor for all later comparisons | |

## 3. Identified parameters (T2-T8)

| Parameter | Datasheet-derived (method_c) | Identified | 95 % CI | Method | Notes |
|---|---|---|---|---|---|
| R [ohm] | 1.6 | | | | |
| Ke [V.s/rad] | 6.366e-3 | | | | |
| Kt [N.m/A] | 1.974e-3 | | | | |
| Jm [kg.m^2] | 5e-7 | | | | |
| Bm [N.m.s/rad] | 1e-6 | | | | |
| tau_c [N.m] | 0 | | | | |
| eta | 0.80 | | | | |
| L [H] | 0 | | | | |

State which parameters `validation/identify.py` reported as **not identifiable** and which extra measurement resolved them.
Which datasheet interpretation do the data favour (method_a / c / d / d2 / d3)?

## 4. Open-loop comparison (T10)

`validation/compare.py` table for the held-out PRBS runs (paste):

## 5. Closed-loop step responses (T11)

One comparison table per gain set and target (paste from `validation/compare.py`), with the overlay plot of measured (mean and band over the repeats) versus simulated, and the residual diagnostics.

| Gain set | Target | Repeats | Thresholds met | Failing checks |
|---|---|---|---|---|
| | | | | |

## 6. Conclusion for this report

- Quantities and conditions that **meet** the thresholds (quote the numbers):
- Quantities that do **not**, with the suspected missing effect:
- Between-unit / between-session spread (if more than one unit or session):
- Changes to the model made as a result (through the identification path only; list each one):
- What the data do **not** support (no claims beyond the tested condition):
