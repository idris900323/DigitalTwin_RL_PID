"""Raw-log schema and run manifests shared by every script that produces data.

The column set follows the paper-preparation plan (section 4.2): one row per control tick, one file per run (or
one file for several runs distinguished by ``run_id``). Simulation rows leave hardware-only fields out and fill
``temp_C`` with NaN. ``write_manifest`` records what produced a set of files (script, arguments, commit, config
hash, seeds, software versions, SHA-256 of every file) so any result can be traced and re-run.

Determinism: nothing here writes timestamps unless asked (``stamp=True``), so regenerating from the same inputs
gives identical files.
"""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import platform
import subprocess
import time
from typing import Iterable, Optional

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "motor_parameters.yaml"

RAW_COLUMNS = (
    "t_s", "step_idx", "target_deg", "theta_deg", "theta_counts", "omega_rad_s", "error_deg", "v_cmd_V",
    "v_applied_V", "i_A", "temp_C", "vsupply_V", "kp", "ki", "kd", "gain_update_flag", "payload_kg", "arm_len_m",
    "gravity_on", "run_id", "experiment_id", "seed", "session_id", "unit_id", "method", "true_params_hash",
)


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def config_sha256(path=CONFIG_PATH) -> str:
    """Hash of the YAML with line endings normalised (so CRLF checkouts hash like LF ones)."""
    return hashlib.sha256(pathlib.Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - git may be absent
        return "unknown"


def params_hash(params: dict) -> str:
    """Short stable hash of the true plant parameters used for a simulated run."""
    blob = json.dumps(params, sort_keys=True, default=float).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


def rows_from_twin_log(log: dict, *, target_deg: float, gains, cpr: int, v_supply: float, run_id: str,
                       experiment_id: str, seed: int, method: str, payload_kg: float = 0.0,
                       arm_len_m: float = 0.0, gravity_on: bool = False, true_params: Optional[dict] = None,
                       session_id: str = "sim", unit_id: str = "twin") -> dict:
    """Convert ``DigitalTwin.run`` output into the raw-log columns (dict of equal-length lists/arrays)."""
    n = len(log["t"])
    lsb = 2.0 * np.pi / cpr
    kp, ki, kd = gains
    col = {
        "t_s": np.asarray(log["t"]),
        "step_idx": np.arange(n),
        "target_deg": np.full(n, target_deg),
        "theta_deg": np.degrees(log["theta_out"]),
        "theta_counts": np.round(np.asarray(log["theta_out_meas"]) / lsb).astype(int),
        "omega_rad_s": np.asarray(log["omega_out"]),
        "error_deg": np.degrees(log["error"]),
        "v_cmd_V": np.asarray(log["V_cmd"]),
        "v_applied_V": np.asarray(log["V_applied"]),
        "i_A": np.asarray(log["i_motor"]),
        "temp_C": np.full(n, np.nan),
        "vsupply_V": np.full(n, v_supply),
        "kp": np.full(n, kp), "ki": np.full(n, ki), "kd": np.full(n, kd),
        "gain_update_flag": np.zeros(n, dtype=int),
        "payload_kg": np.full(n, payload_kg), "arm_len_m": np.full(n, arm_len_m),
        "gravity_on": np.full(n, int(gravity_on)),
        "run_id": [run_id] * n, "experiment_id": [experiment_id] * n, "seed": np.full(n, seed, dtype=int),
        "session_id": [session_id] * n, "unit_id": [unit_id] * n, "method": [method] * n,
        "true_params_hash": [params_hash(true_params or {})] * n,
    }
    assert tuple(col) == RAW_COLUMNS
    return col


def write_raw_csv(path, blocks: Iterable[dict], float_fmt: str = "{:.9g}") -> None:
    """Write one or more run blocks (from ``rows_from_twin_log``) to a single CSV with the schema header."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(RAW_COLUMNS)
        for b in blocks:
            n = len(b["t_s"])
            for k in range(n):
                row = []
                for c in RAW_COLUMNS:
                    v = b[c][k]
                    if isinstance(v, (float, np.floating)):
                        row.append("" if np.isnan(v) else float_fmt.format(v))
                    else:
                        row.append(v.item() if hasattr(v, "item") else v)
                w.writerow(row)


def write_manifest(out_dir, *, script: str, args: dict, seeds, files: Iterable, extra: Optional[dict] = None,
                   stamp: bool = False, name: str = "manifest.json") -> pathlib.Path:
    """Write ``manifest.json`` listing the produced ``files`` (paths) with checksums."""
    import numpy
    import scipy
    import yaml

    out_dir = pathlib.Path(out_dir)
    entries = {}
    for f in sorted(map(pathlib.Path, files), key=lambda p: p.name):
        entries[f.name] = sha256_file(f)
    m = {
        "script": script, "args": args, "seeds": list(seeds) if not isinstance(seeds, int) else [seeds],
        "commit": git_commit(), "config_sha256": config_sha256(),
        "software": {"python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__,
                     "pyyaml": yaml.__version__, "platform": platform.system() + " " + platform.machine()},
        "files_sha256": entries,
    }
    if stamp:
        m["written_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if extra:
        m.update(extra)
    path = out_dir / name
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path
