"""Compare PID-selection strategies on paired held-out scenarios (G4.3). PRE-VALIDATION: everything here is simulated on the
unvalidated, datasheet-derived twin; nothing is a hardware result.

Controllers (every one runs in the SAME RL_PID_Env scenario for a given seed: same plant, payload, target, delay, noise):

    tuned          fixed Tuned preset 15/0/0.3
    legacy         fixed legacy default 5/20/0.05
    zn             Ziegler-Nichols gains from the linear model of the nominal plant for that load (clipped to the env bounds)
    bandit         the one-shot context -> gains MLP (autotune_360/autotune_policy_360.json), gains fixed for the episode
    random_search  ORACLE UPPER BOUND: best of N random gain sets per scenario, chosen with knowledge of the outcome
    ppo            step-wise adaptation policy(ies) from rl/train_ppo.py (``--policy-dir``), one row per training seed

    python simulation/compare_controllers.py --policy-dir <models/rl/run> --out-dir results/controller_comparison

Regimes: ``static`` (no mid-episode changes), ``changes`` (payload and target change mid-episode: the case adaptation could help),
``ood`` (plant ranges widened x1.5 and twice the delay: outside the training distribution). Statistics: mean and std, 95 % bootstrap
CI of the paired difference to the Tuned preset, a paired Wilcoxon signed-rank test (normal approximation, tie-corrected), a
per-context breakdown and the worst scenarios for the best PPO seed. The report states plainly whether RL beat the baselines.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from environments.rl_pid_env import RL_PID_Env  # noqa: E402
from simulation import rawlog  # noqa: E402

EVAL_SEED0 = 50_000          # training uses seeds < 20_000 and 10_000 + seed for its evaluation; these are held out
BANDIT_JSON = ROOT / "autotune_360" / "autotune_policy_360.json"
REGIMES = {
    "static": dict(change_prob={"payload": 0.0, "target": 0.0}, widen=1.0, delay_mult=1),
    "changes": dict(change_prob={"payload": 1.0, "target": 1.0}, widen=1.0, delay_mult=1),
    "ood": dict(change_prob={"payload": 0.0, "target": 0.0}, widen=1.5, delay_mult=2),
}


def make_env(regime: str, **kw) -> RL_PID_Env:
    r = REGIMES[regime]
    env = RL_PID_Env(change_prob=r["change_prob"], **kw)
    if r["widen"] != 1.0:
        for v in env._ranges.values():
            if v["kind"] in ("uniform", "log"):
                v["lo"], v["hi"] = v["lo"] / r["widen"] if v["lo"] > 0 else v["lo"] * r["widen"], v["hi"] * r["widen"]
    if r["delay_mult"] != 1:
        d = env.e["randomize"]["delay_steps"]
        env.e["randomize"]["delay_steps"] = [d[0], d[1] * r["delay_mult"]]
    return env


# ------------------------------------------------------------------ controllers
class Bandit:
    def __init__(self, path=BANDIT_JSON):
        d = json.loads(pathlib.Path(path).read_text())
        self.d = {k: np.asarray(v, float) for k, v in d.items() if isinstance(v, list)}
        self.lo, self.hi = self.d["lo"], self.d["hi"]
        self.mass_max, self.len_min, self.len_max = d["mass_max"], d["len_min"], d["len_max"]

    def gains(self, ctx):
        m, L, g, v, R = ctx["mass"], ctx["length"], float(ctx["gravity"]), ctx["vpct"], ctx["target"]
        x = np.array([m / self.mass_max, (L - self.len_min) / (self.len_max - self.len_min), g, v / 100.0,
                      g * m * L / (self.mass_max * self.len_max), m * L ** 2 / (self.mass_max * self.len_max ** 2), R / 360.0,
                      g * m * L * math.sin(math.radians(R)) / (self.mass_max * self.len_max)])
        h = np.tanh(np.tanh(x @ self.d["W1"] + self.d["b1"]) @ self.d["W2"] + self.d["b2"])
        z = h @ self.d["W3"] + self.d["b3"]
        u = 1.0 / (1.0 + np.exp(-z))
        return self.lo * (self.hi / self.lo) ** u


def zn_gains(env: RL_PID_Env):
    from tuning.analytic import ziegler_nichols
    from tuning.linear import LinearPlant

    c = env.ctx
    plant = LinearPlant.from_cfg(env.cfg, payload_kg=c["mass"], arm_length_m=c["length"], gravity=c["gravity"], target_deg=c["target"])
    return np.array(ziegler_nichols(plant), float)


def run_episode(env: RL_PID_Env, seed: int, gains=None, policy=None) -> dict:
    """One paired episode: the same ``seed`` always yields the same scenario. ``gains`` fixes the gains for the whole episode,
    ``policy(obs)`` adapts them every decision."""
    obs, info = env.reset(seed=seed)
    ctx = dict(info["context"])
    if callable(gains):
        gains = gains(env)                                    # context-dependent gains are computed after the reset
    if gains is not None:
        g = np.clip(np.asarray(gains, float), [env.lo[0], 0.0, env.lo[2]], env.hi)
        env.gains = g
        env._apply_gains(g)
    ret, done, last = 0.0, False, {}
    while not done:
        a = np.zeros(3, np.float32) if policy is None else policy(obs)
        obs, r, term, trunc, last = env.step(a)
        ret += r
        done = term or trunc
    m = last.get("episode_metrics", {})
    th = np.degrees(np.array(env.theta_log))
    final_err = abs(env.target_now - th[-1]) / max(env.target_now, 1e-9) if len(th) and np.isfinite(th[-1]) else float("inf")
    diverged = bool(term)
    ok = (not diverged) and final_err < 0.02 and m.get("overshoot_pct", 100.0) <= 10.0
    return dict(ret=float(ret), iae=float(m.get("iae_deg_s", np.nan)), overshoot=float(m.get("overshoot_pct", np.nan)),
                settle=float(m.get("settle_s", np.nan)), peak_current=float(m.get("peak_current_A", np.nan)), final_err=float(final_err),
                diverged=diverged, success=bool(ok), gains=env.gains.copy(), ctx=ctx)


def regime_of(ctx: dict) -> str:
    if ctx["mass"] < 0.02:
        return "no payload"
    if not ctx["gravity"]:
        return "payload, no gravity"
    return "payload + gravity"


# ------------------------------------------------------------------ statistics
def bootstrap_ci(d: np.ndarray, n: int = 2000, seed: int = 0):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), (n, len(d)))
    means = d[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def wilcoxon_p(d: np.ndarray) -> float:
    """Two-sided paired Wilcoxon signed-rank p-value, normal approximation with tie correction (no scipy dependency)."""
    d = d[np.isfinite(d)]
    d = d[d != 0]
    n = len(d)
    if n < 10:
        return float("nan")
    order = np.argsort(np.abs(d))
    ranks = np.empty(n)
    a = np.abs(d)[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and a[j + 1] == a[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    w = float(ranks[d > 0].sum())
    mean = n * (n + 1) / 4.0
    _, counts = np.unique(a, return_counts=True)
    var = n * (n + 1) * (2 * n + 1) / 24.0 - float(np.sum(counts ** 3 - counts)) / 48.0
    if var <= 0:
        return float("nan")
    z = (w - mean) / math.sqrt(var)
    return float(math.erfc(abs(z) / math.sqrt(2.0)))


def finite_mean(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean()) if len(x) else float("nan")


# ------------------------------------------------------------------ main
def load_ppo(policy_dir: pathlib.Path, which: str):
    from stable_baselines3 import PPO, SAC, TD3

    out = {}
    for d in sorted(policy_dir.glob("seed_*")):
        meta = json.loads((d / "meta.json").read_text())
        cls = {"ppo": PPO, "sac": SAC, "td3": TD3}[meta["algo"]]
        f = d / ("best_model.zip" if which == "best" else "final_model.zip")
        model = cls.load(str(f), device="cpu")
        out[f"{meta['algo']}_s{meta['seed']}"] = (lambda obs, m=model: m.predict(obs, deterministic=True)[0])
        out[f"{meta['algo']}_s{meta['seed']}:n_stack"] = meta["common"]["env"]["n_stack"]
        out[f"{meta['algo']}_s{meta['seed']}:action_mode"] = meta["common"]["env"]["action_mode"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Paired comparison of PID strategies (pre-validation).")
    ap.add_argument("--policy-dir", default=None, help="run folder from rl/train_ppo.py (contains seed_*/)")
    ap.add_argument("--which", default="best", choices=["best", "final"])
    ap.add_argument("--n", type=int, default=150, help="held-out scenarios per regime")
    ap.add_argument("--oracle-candidates", type=int, default=24)
    ap.add_argument("--regimes", nargs="*", default=list(REGIMES))
    ap.add_argument("--out-dir", default=str(ROOT / "results" / "controller_comparison"))
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bandit = Bandit()
    ppo = load_ppo(pathlib.Path(a.policy_dir), a.which) if a.policy_dir else {}
    ppo_names = [k for k in ppo if ":" not in k]
    seeds = [EVAL_SEED0 + i for i in range(a.n)]
    rows, results = [], {}
    for reg in a.regimes:
        base = make_env(reg)
        lo, hi = base.lo, base.hi
        tuned = np.array([base.cfg["pid_presets"]["tuned"][k] for k in ("Kp", "Ki", "Kd")])
        legacy = np.array([base.cfg["pid_presets"]["legacy_default"][k] for k in ("Kp", "Ki", "Kd")])
        rng = np.random.default_rng(1234)
        cands = np.exp(rng.uniform(np.log(lo), np.log(hi), (a.oracle_candidates, 3)))
        penvs = {n: make_env(reg, action_mode=ppo[n + ":action_mode"], n_stack=ppo[n + ":n_stack"]) for n in ppo_names}
        res = {k: [] for k in ["tuned", "legacy", "zn", "bandit", "random_search"] + ppo_names}
        for i, s in enumerate(seeds):
            res["tuned"].append(run_episode(base, s, gains=tuned))
            res["legacy"].append(run_episode(base, s, gains=legacy))
            res["zn"].append(run_episode(base, s, gains=zn_gains))
            res["bandit"].append(run_episode(base, s, gains=lambda e: bandit.gains(e.ctx)))
            best = None
            for c in np.vstack([cands, tuned, bandit.gains(base.ctx)]):    # base.ctx is this seed's context after the runs above                # the oracle may also pick Tuned or the bandit's choice
                r = run_episode(base, s, gains=c)
                if best is None or r["ret"] > best["ret"]:
                    best = r
            res["random_search"].append(best)
            for n in ppo_names:
                res[n].append(run_episode(penvs[n], s, policy=ppo[n]))
            if (i + 1) % 25 == 0:
                print(f"  {reg}: {i + 1}/{a.n}", flush=True)
        results[reg] = res
        for name, lst in res.items():
            for s, r in zip(seeds, lst):
                rows.append(dict(regime=reg, controller=name, seed=s, context=regime_of(r["ctx"]), target=round(r["ctx"]["target"], 2),
                                 mass=round(r["ctx"]["mass"], 3), ret=r["ret"], iae=r["iae"], overshoot=r["overshoot"], settle=r["settle"],
                                 peak_current=r["peak_current"], final_err=r["final_err"], diverged=int(r["diverged"]), success=int(r["success"]),
                                 Kp=r["gains"][0], Ki=r["gains"][1], Kd=r["gains"][2]))
    with open(out / "per_episode.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})
    md = report(results, seeds, ppo_names, a)
    (out / "summary.md").write_text(md, encoding="utf-8", newline="\n")
    rawlog.write_manifest(out, script="simulation/compare_controllers.py", args=dict(n=a.n, which=a.which, oracle_candidates=a.oracle_candidates,
                          regimes=a.regimes, policy_dir=pathlib.Path(a.policy_dir).name if a.policy_dir else None), seeds=seeds[:1] + seeds[-1:],
                          files=[out / "per_episode.csv", out / "summary.md"], name="comparison_manifest.json")
    print(md.encode("ascii", "replace").decode())
    return 0


def report(results, seeds, ppo_names, a) -> str:
    L = ["# Controller comparison (PRE-VALIDATION, simulated on the unvalidated twin)", "",
         f"{len(seeds)} held-out paired scenarios per regime (seeds {seeds[0]}..{seeds[-1]}, never used in training). Every controller sees the same plant, "
         f"payload, target, delay and noise for a given seed. `return` is the environment reward (higher is better); IAE in deg*s (lower is better). "
         f"`random_search` is an oracle: best of {a.oracle_candidates} random gain sets + Tuned + bandit per scenario, chosen with hindsight, so it is an "
         "upper bound for any fixed-gain strategy, not a deployable controller.", ""]
    verdicts = []
    for reg, res in results.items():
        t = np.array([r["ret"] for r in res["tuned"]])
        L += [f"## Regime `{reg}`", "", "| controller | return mean ± std | Δreturn vs Tuned [95 % CI] | p (Wilcoxon) | IAE mean | overshoot % | settle s | success | diverged |",
              "|---|---|---|---|---|---|---|---|---|"]
        for name, lst in res.items():
            r = np.array([x["ret"] for x in lst])
            d = r - t
            lo, hi = bootstrap_ci(d)
            p = wilcoxon_p(d) if name != "tuned" else float("nan")
            L.append(f"| {name} | {r.mean():.3f} ± {r.std():.3f} | {d.mean():+.3f} [{lo:+.3f}, {hi:+.3f}] | {p:.3g} | "
                     f"{finite_mean([x['iae'] for x in lst]):.1f} | {finite_mean([x['overshoot'] for x in lst]):.1f} | "
                     f"{finite_mean([x['settle'] for x in lst]):.3f} | {100 * np.mean([x['success'] for x in lst]):.0f} % | "
                     f"{100 * np.mean([x['diverged'] for x in lst]):.0f} % |")
        L.append("")
        if ppo_names:
            best_ppo = max(ppo_names, key=lambda n: np.mean([x["ret"] for x in res[n]]))
            rb, rs = np.array([x["ret"] for x in res[best_ppo]]), np.array([x["ret"] for x in res["bandit"]])
            ro = np.array([x["ret"] for x in res["random_search"]])
            for other, ro_ in (("tuned", t), ("bandit", rs), ("random_search (oracle)", ro)):
                d = rb - ro_
                lo, hi = bootstrap_ci(d)
                verdicts.append((reg, best_ppo, other, float(d.mean()), lo, hi))
            L += [f"Per-context breakdown of mean return (best PPO seed `{best_ppo}` vs Tuned vs bandit):", "",
                  "| context | n | Tuned | bandit | " + best_ppo + " |", "|---|---|---|---|---|"]
            ctxs = np.array([regime_of(x["ctx"]) for x in res["tuned"]])
            for c in sorted(set(ctxs)):
                m = ctxs == c
                L.append(f"| {c} | {int(m.sum())} | {t[m].mean():.3f} | {rs[m].mean():.3f} | {rb[m].mean():.3f} |")
            worst = np.argsort(rb - t)[:5]
            L += ["", f"Worst five scenarios for `{best_ppo}` relative to Tuned (failure analysis):", "",
                  "| seed | context | target deg | mass kg | Δreturn | PPO overshoot % | PPO final gains | Tuned overshoot % |", "|---|---|---|---|---|---|---|---|"]
            for i in worst:
                x, y = res[best_ppo][i], res["tuned"][i]
                L.append(f"| {seeds[i]} | {regime_of(x['ctx'])} | {x['ctx']['target']:.0f} | {x['ctx']['mass']:.2f} | {rb[i] - t[i]:+.3f} | "
                         f"{x['overshoot']:.1f} | {x['gains'][0]:.1f}/{x['gains'][1]:.2f}/{x['gains'][2]:.2f} | {y['overshoot']:.1f} |")
            L.append("")
    L += ["## Verdict", ""]
    if verdicts:
        for reg, n, other, m, lo, hi in verdicts:
            word = "BETTER than" if lo > 0 else ("WORSE than" if hi < 0 else "statistically indistinguishable from")
            L.append(f"- `{reg}`: best PPO seed `{n}` is {word} {other} (Δreturn {m:+.3f}, 95 % CI [{lo:+.3f}, {hi:+.3f}]).")
        L += ["", "The best seed is picked on these same scenarios, which favours it (selection bias): treat its numbers as optimistic and compare the "
              "seed spread in the tables above. Return is the training objective; IAE, overshoot, settling time and success rate are controller-agnostic checks.", ""]
    else:
        L.append("No RL policy was supplied (`--policy-dir`), so only the baselines are compared.")
    L += ["", "Everything above is simulated on the preliminary twin and has not been validated on hardware."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
