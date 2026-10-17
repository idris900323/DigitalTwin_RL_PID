"""Train PPO (or SAC / TD3) on RL_PID_Env with Stable-Baselines3 (G4.2). PRE-VALIDATION PROTOTYPE.

    python rl/train_ppo.py --smoke                      # about a minute: pipeline check for CI
    python rl/train_ppo.py --algo ppo --run-id ppo_v1   # 3 seeds x 150k decisions (see rl/ppo.yaml)
    python rl/train_ppo.py --algo sac --run-id sac_v1   # same interface

Each seed gets its own folder ``models/rl/<run_id>/seed_<k>/`` with the best and final policy, ``progress.csv`` (learning curve),
``evaluations.npz`` (held-out evaluation returns), ``config.yaml`` and ``meta.json`` (git commit, versions, seed). The run folder is
git-ignored. Evaluation uses a separate environment whose reset sequence is seeded, so curves are comparable across seeds.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import platform
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from environments.rl_pid_env import RL_PID_Env  # noqa: E402
from simulation import rawlog  # noqa: E402

CONFIG = ROOT / "rl" / "ppo.yaml"
OUT_ROOT = ROOT / "models" / "rl"


def make_env(env_cfg: dict, seed: int | None = None):
    from stable_baselines3.common.monitor import Monitor

    env = RL_PID_Env(action_mode=env_cfg["action_mode"], n_stack=env_cfg["n_stack"], change_prob=env_cfg["change_prob"])
    return Monitor(env)


def train_one(algo: str, seed: int, hp: dict, common: dict, out: pathlib.Path, n_steps_override: int | None = None) -> dict:
    import stable_baselines3 as sb3
    import torch
    from stable_baselines3.common.callbacks import EvalCallback
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.utils import set_random_seed

    out.mkdir(parents=True, exist_ok=True)
    set_random_seed(seed)
    env = make_env(common["env"])
    env.reset(seed=seed)
    eval_env = make_env(common["env"])
    eval_env.reset(seed=10_000 + seed)                            # held-out, seeded reset sequence
    policy_kwargs = dict(net_arch=list(hp["net_arch"]))
    kw = {k: v for k, v in hp.items() if k not in ("policy", "net_arch")}
    if algo == "ppo":
        if n_steps_override:
            kw["n_steps"] = n_steps_override
            kw["batch_size"] = min(kw["batch_size"], n_steps_override)
        model = sb3.PPO(hp["policy"], env, seed=seed, policy_kwargs=policy_kwargs, verbose=0, device="cpu", **kw)
    elif algo == "sac":
        model = sb3.SAC(hp["policy"], env, seed=seed, policy_kwargs=policy_kwargs, verbose=0, device="cpu", learning_starts=1000, **kw)
    elif algo == "td3":
        model = sb3.TD3(hp["policy"], env, seed=seed, policy_kwargs=policy_kwargs, verbose=0, device="cpu", learning_starts=1000, **kw)
    else:
        raise ValueError(f"unknown algorithm {algo!r}")
    model.set_logger(configure(str(out), ["csv"]))
    cb = EvalCallback(eval_env, best_model_save_path=str(out), log_path=str(out), eval_freq=common["eval_freq"], n_eval_episodes=common["n_eval_episodes"],
                      deterministic=True, verbose=0)
    t0 = time.time()
    model.learn(total_timesteps=common["total_timesteps"], callback=cb)
    model.save(str(out / "final_model"))
    meta = {"algo": algo, "seed": seed, "pre_validation_prototype": True, "hyperparameters": hp, "common": common,
            "total_timesteps": common["total_timesteps"], "runtime_s": round(time.time() - t0, 1), "commit": rawlog.git_commit(),
            "config_sha256": rawlog.config_sha256(), "software": {"python": platform.python_version(), "numpy": np.__version__,
                                                                   "torch": torch.__version__, "stable_baselines3": sb3.__version__,
                                                                   "platform": platform.system() + " " + platform.machine()}}
    (out / "meta.json").write_text(json.dumps(meta, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    (out / "config.yaml").write_text(yaml.safe_dump({"algo": algo, "hyperparameters": hp, "common": common}, sort_keys=False), encoding="utf-8", newline="\n")
    return meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Train a step-wise PID-adaptation policy (pre-validation prototype).")
    ap.add_argument("--algo", default="ppo", choices=["ppo", "sac", "td3"])
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--timesteps", type=int, default=None)
    ap.add_argument("--smoke", action="store_true", help="a minute-long run to check the pipeline (CI)")
    ap.add_argument("--out-root", default=str(OUT_ROOT))
    ap.add_argument("--config", default=str(CONFIG))
    a = ap.parse_args(argv)
    cfg = yaml.safe_load(pathlib.Path(a.config).read_text(encoding="utf-8"))
    common, hp = dict(cfg["common"]), dict(cfg[a.algo])
    n_steps = None
    if a.smoke:
        sm = cfg["smoke"]
        common.update(seeds=sm["seeds"], total_timesteps=sm["total_timesteps"], eval_freq=sm["eval_freq"], n_eval_episodes=sm["n_eval_episodes"])
        n_steps = sm["ppo_n_steps"]
    if a.timesteps:
        common["total_timesteps"] = a.timesteps
    seeds = a.seeds if a.seeds else common["seeds"]
    run_id = a.run_id or f"{a.algo}_{'smoke' if a.smoke else time.strftime('%Y%m%d_%H%M%S')}"
    root = pathlib.Path(a.out_root) / run_id
    for s in seeds:
        meta = train_one(a.algo, s, hp, common, root / f"seed_{s}", n_steps)
        print(f"{a.algo} seed {s}: {meta['total_timesteps']} decisions in {meta['runtime_s']} s -> {root / f'seed_{s}'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
