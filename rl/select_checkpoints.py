"""Select a checkpoint per training seed on VALIDATION seeds (40000+, never the test seeds 50000+) and report training instability.

Every ``checkpoints/ckpt_<step>_steps.zip`` is scored with the comparison's default reward on validation scenarios of the ``static`` and
``changes`` regimes (mean of the two); the best one is copied to ``selected_model.zip``. ``val_curve.json`` keeps the whole curve, so the
peak-versus-final degradation is on record.

    python rl/select_checkpoints.py <run_dir> [--seeds 0 1 2] [--n-val 30]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from simulation.compare_controllers import VAL_SEED0, make_env, run_episode  # noqa: E402


def main(argv=None) -> int:
    from stable_baselines3 import PPO, SAC, TD3

    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--n-val", type=int, default=30)
    a = ap.parse_args(argv)
    run = pathlib.Path(a.run_dir)
    dirs = [run / f"seed_{s}" for s in a.seeds] if a.seeds else sorted(run.glob("seed_*"))
    vseeds = [VAL_SEED0 + i for i in range(a.n_val)]
    for d in dirs:
        meta = json.loads((d / "meta.json").read_text())
        cls = {"ppo": PPO, "sac": SAC, "td3": TD3}[meta["algo"]]
        env_cfg = meta["common"]["env"]
        envs = {reg: make_env(reg, action_mode=env_cfg["action_mode"], n_stack=env_cfg["n_stack"]) for reg in ("static", "changes")}
        ckpts = sorted(d.glob("checkpoints/ckpt_*_steps.zip"), key=lambda p: int(re.search(r"ckpt_(\d+)_steps", p.name).group(1)))
        curve = []
        for f in ckpts:
            model = cls.load(str(f), device="cpu")
            score = {reg: float(np.mean([run_episode(env, s, policy=lambda o, m=model: m.predict(o, deterministic=True)[0])["ret"] for s in vseeds]))
                     for reg, env in envs.items()}
            step = int(re.search(r"ckpt_(\d+)_steps", f.name).group(1))
            curve.append(dict(step=step, static=score["static"], changes=score["changes"], mean=0.5 * (score["static"] + score["changes"])))
            print(d.name, step, round(curve[-1]["mean"], 3), flush=True)
        best = max(curve, key=lambda c: c["mean"])
        sel = d / "selected_model.zip"
        shutil.copy(d / "checkpoints" / f"ckpt_{best['step']}_steps.zip", sel)
        final = curve[-1]
        out = dict(validation_seeds=[vseeds[0], vseeds[-1]], curve=curve, selected_step=best["step"], selected_val_mean=best["mean"],
                   final_val_mean=final["mean"], degradation_peak_to_final=best["mean"] - final["mean"],
                   selected_sha256=hashlib.sha256(sel.read_bytes()).hexdigest())
        (d / "val_curve.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
        meta["selected_checkpoint"] = dict(step=best["step"], sha256=out["selected_sha256"], val_mean=best["mean"])
        meta.setdefault("policy_files_sha256", {})["selected_model.zip"] = out["selected_sha256"]
        (d / "meta.json").write_text(json.dumps(meta, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
        print(f"{d.name}: selected step {best['step']} val {best['mean']:.3f}, final {final['mean']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
