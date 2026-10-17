# PyBullet on Windows (Group 5, optional)

**Status on the development machine (Windows 11, Python 3.12.10 and 3.11 Store build): PyBullet could not be installed, so nothing here has run against PyBullet.** The geometry/inertia side is tested without it.

## What was tried (and the exact result)

| Route | Command | Result |
|---|---|---|
| Prebuilt wheel, Python 3.12 | `pip install --only-binary=:all: pybullet` | `No matching distribution found` (PyPI has pybullet 3.2.7 as an sdist; no Windows wheel for CPython 3.11+) |
| Prebuilt wheel, Python 3.11 | `py -3.11 -m pip download pybullet --only-binary=:all: --no-deps` | `No matching distribution found` |
| Wheel for an older tag | `pip download pybullet --only-binary=:all: --python-version 3.10 --platform win_amd64` | `No matching distribution found` |
| Build from source | needs MSVC Build Tools (C++); `cl` is not on this machine (no Visual Studio folder) | not attempted |
| conda-forge | `conda install -c conda-forge pybullet` | `conda` not installed |
| WSL2 | `wsl -l -v` | WSL has no installed distribution |

## Routes that should work (untested here)

1. **Visual Studio Build Tools**: install "Desktop development with C++" (MSVC + Windows SDK), then `pip install pybullet` builds it from source (several minutes).
2. **conda-forge**: install Miniforge, `conda create -n dtrl python=3.12 && conda activate dtrl && conda install -c conda-forge pybullet`.
3. **WSL2**: `wsl --install -d Ubuntu`, then `pip install pybullet` inside (Linux wheels or a quick source build).

After installing, record the commands that worked here and run `pytest tests/test_pybullet_sim.py`; the free-pendulum period test (`PyBulletJointSim` against the analytic period) is skipped until `pybullet` imports.

## What exists

- `pybullet_sim/urdf.py`: URDF generator for the joint from the YAML and `JointParams` (hub with the reflected rotor inertia, thin-rod arm, point-mass payload; 0 deg = hanging). `tests/test_pybullet_sim.py` checks that the URDF's inertia about the shaft and gravity moment equal `models/joint.py`.
- `pybullet_sim/sim.py`: `PyBulletJointSim` applies an output torque from the Python twin to a PyBullet joint (the motor electrics stay in Python). **Untested.**
- The folder is `pybullet_sim/`, not `pybullet/`, so it cannot shadow the real package.

PyBullet's value here is rigid-body and visual fidelity, not motor electrics. Nothing in this folder is validated.
