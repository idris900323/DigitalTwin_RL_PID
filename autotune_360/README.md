# autotune_360 — browser servo twin + numpy RL auto-tuner

PRE-VALIDATION PROTOTYPE. Everything here runs on the preliminary, datasheet-derived twin (`method_c`); none of it has been validated against real hardware.

| File | What it is |
|---|---|
| `servo_pid_visualizer_360.html` | Self-contained browser page (about 15 MB because the CAD and policy are embedded). Serve it over HTTP, e.g. `python -m http.server` in this folder, then open `http://127.0.0.1:8000/servo_pid_visualizer_360.html`. |
| `train_autotune_360.py` | numpy-only REINFORCE trainer (contextual bandit: context -> Kp, Ki, Kd). |
| `autotune_policy_360.json` | Trained MLP weights (8 -> 32 -> 32 -> 3), embedded in the HTML as `RL_POLICY`. |
| `autotune_policy_360.meta.json` | Seed, hyperparameters, config hash, git commit, runtime, versions and the held-out table for the committed weights. |

## Regenerate the weights

From the repository root, in an environment with the pinned `numpy`:

```
python autotune_360/train_autotune_360.py --seed 0
```

This takes about 4 minutes and rewrites `autotune_policy_360.json` and `autotune_policy_360.meta.json`.

### Reproducibility and toolchain

The committed weights were produced with **Python 3.12.10, numpy 2.4.2** (recorded in `autotune_policy_360.meta.json`, together with the seed, hyperparameters, config hash and git commit).

- **Same toolchain:** running the command twice with the same seed gives **byte-identical** policy files, and it reproduces the committed file exactly.
- **Different toolchain (other numpy/Python, other OS or BLAS):** byte-identical files are **not** guaranteed, because floating-point summation order differs between builds. Measured between numpy 2.5.4 / Python 3.13 and numpy 2.4.2 / Python 3.12 with the same seed: **maximum absolute weight difference 7.3e-4**, with the same held-out metrics. Treat 1e-3 as the cross-platform tolerance for weights, and compare policies by their held-out table rather than by file hash.
Useful flags: `--iters`, `--contexts`, `--samples`, `--lr`, `--out PATH`, `--include-infeasible`.

After retraining, the policy embedded in the HTML must be updated to match (`const RL_POLICY = {...};`), and `tests/fixtures/feature_vectors.json` regenerated if the weights changed.
`pytest tests/browser` fails if the embedded policy differs from `autotune_policy_360.json`.

## Python <-> JavaScript contract

The page computes the same 8 input features as `features()` in the trainer (`FEATURE_VERSION = 1`) and the same torque-feasibility margin as `models/feasibility.py`. Both are checked by the Playwright tests against fixed Python-generated values.

## Feasibility

Contexts whose gravity holding torque exceeds the motor's available torque (margin below 1.2) cannot be tracked. Training samples only feasible contexts by default; the held-out report shows both a feasible-only set and the full set with its infeasible fraction. The page shows a warning banner and disables Auto-tune for infeasible payloads.
