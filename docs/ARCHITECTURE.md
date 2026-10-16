# Architecture

The project is a **preliminary** physics-based digital twin of one geared DC-motor joint plus tuning, sensitivity and validation tooling. This page shows how the pieces connect and where the Python/JavaScript contract lives.

## Data flow

```mermaid
flowchart LR
    YAML[config/motor_parameters.yaml<br/>single source of truth] --> FACT[models/factory.py]
    YAML --> GEN[tools/generate_js_config.py]
    GEN --> JSCFG[autotune_360/config.generated.js]
    GEN --> HTML[servo_pid_visualizer_360.html<br/>inlined config + physics.js + CAD mesh]
    PHYS[autotune_360/physics.js] --> HTML
    GLB[cad/JGB37-520_converted.glb] --> HTML
    FACT --> TWIN[models/digital_twin.py<br/>motor + gearbox + joint + encoder + PID]
    TWIN --> MET[simulation/metrics.py]
    TWIN --> SEQ[simulation/simulate_pid.py]
    TWIN --> SENS[simulation/sensitivity.py]
    TWIN --> QT[simulation/cad_pid_visualizer.py]
    YAML --> TRAIN[autotune_360/train_autotune_360.py<br/>numpy batch simulator]
    TRAIN --> POL[autotune_policy_360.json]
    POL --> HTML
    TWIN --> VAL[validation/*<br/>identify, compare]
    BENCH[(bench CSV)] -.-> VAL
    SEQ --> RES[results/ + manifests]
    SENS --> RES
```

## One control step (models/digital_twin.py)

```mermaid
flowchart LR
    R[target angle] --> E[error = ref - encoder reading]
    E --> PID[PID<br/>saturation, anti-windup, filtered D]
    PID --> DLY[optional command delay]
    DLY --> LIM[optional driver current limit]
    LIM --> MOT[DC motor ODE<br/>RK4, sub-stepped if L > 0]
    JNT[joint: gravity + friction + disturbance<br/>reflected by 1/N*eta] --> MOT
    MOT --> GB[gearbox 180:1] --> OUT[true output angle]
    OUT --> ENC[encoder: 9360 counts/rev] --> E
    OUT --> JNT
```

## The implementations of the plant and how they are kept honest

| Implementation | File | Scope |
|---|---|---|
| Python twin (reference) | `models/`, `controllers/` | everything |
| Trainer batch simulator | `autotune_360/train_autotune_360.py` | payload point mass, gravity, speed cap, current limit, encoder noise; refuses L > 0 |
| Browser physics | `autotune_360/physics.js` | same subset, no noise; refuses L > 0 |
| Qt demo compute path | `simulation/cad_pid_visualizer.py::compute_run` | payload + gravity |

`tests/test_cross_implementation.py` runs the canonical scenarios (`tests/scenarios.json`) through all of them (agreement about 1e-11 deg), `tests/test_base_code_oracle.py` runs the ORIGINAL code from git history as an oracle, and `tests/test_config_sync.py` fails if any motor constant is hard-coded or if the generated JavaScript config, the inlined physics or the embedded mesh is stale.

## Python / JavaScript contract

- Constants: YAML -> `config.generated.js` (regenerate with `python tools/generate_js_config.py`).
- Policy inputs: the 8 features of `features()` in the trainer (`FEATURE_VERSION = 1`) equal `rlFeatures()` in the page (`tests/fixtures/feature_vectors.json`).
- Torque feasibility: `models/feasibility.py` equals `feasibilityJS()` in `physics.js`.
- Policy weights: `autotune_policy_360.json` equals `RL_POLICY` embedded in the page.

## Outputs and provenance

Every script that produces data writes a manifest (`simulation/rawlog.py`): arguments, seeds, commit, config SHA-256, numpy/scipy/python versions, platform and the SHA-256 of each file; raw per-tick logs use one schema (`RAW_COLUMNS`) shared with the bench-data loader (`validation/load_bench_csv.py`). Figures use one fixed colour and line style per method (`simulation/plotstyle.py`).
