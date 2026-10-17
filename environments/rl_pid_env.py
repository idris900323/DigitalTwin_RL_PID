"""Gymnasium environment for step-wise PID gain adaptation on the preliminary digital twin (G4.1).

PRE-VALIDATION PROTOTYPE: trained and evaluated on an unvalidated, datasheet-derived twin. Nothing here is validated on
hardware, and no result from this environment may be described as validated or hardware-ready.

One episode is a step response of the shared Python twin (``models/`` + ``controllers/``: the same physics as everywhere else,
no fourth copy). Every ``decision_interval_s`` (default 20 ms = 20 control steps) the agent adjusts the PID gains; the twin then
runs the next interval with the new gains.

Action (Box(-1, 1, (3,)))
    mode "multiplicative" (default): gain_i *= exp(a_i * ln(1 + action_step)), i.e. at most +-10 % per decision, then clipped to the
    configured bounds. Multiplicative changes are scale-free across the log-range of the gains and cannot flip a gain's sign, which
    is why they are the safer default; mode "direct" maps a_i in [-1, 1] straight onto the log-range of the bounds, for comparison with
    the one-shot bandit tuner.

Observation (float32, normalised, bounded; all of it is MEASURABLE on hardware except where marked ESTIMATED)
    [ error/step_size, error_rate, integral_error (clipped), log-normalised Kp, Ki, Kd, last voltage/Vmax, current/I_ref (ESTIMATED from
      the model on hardware without a current sensor), output velocity/omega_ref, target/360, time fraction,
      payload mass/mass_max, arm length (normalised), gravity flag, speed-cap fraction, clipped log10 torque-feasibility margin ]
    A short history can be stacked with ``n_stack``.

Reward (weights in the YAML ``rl_env.reward``; each term is reported in ``info["reward_breakdown"]``)
    r = - w_error * time-weighted squared error / step^2  - w_effort * mean(V^2)/Vmax^2  - w_chatter * mean|dV|/Vmax
        - w_gain_change * |d log gains|_1  - w_overshoot * overshoot fraction,  and -diverge_penalty on divergence.
    Reward-hacking guards: normalising the error by the step size (small targets cannot be exploited), the gain-change penalty
    (no thrashing), the effort and chatter terms (no bang-bang to win on error), time weighting (late error costs more) and episodes that
    always run to the horizon unless they diverge (finishing early cannot be rewarded).

Episode: random target in ``rl_env.target_deg``; payload and plant randomised (domain randomisation, ``reset(seed=...)`` is
reproducible); optional mid-episode payload and target changes (probabilities in the config, off by default).
"""

from __future__ import annotations

import copy
import math
from typing import Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from models.factory import build_twin_from_config
from models.feasibility import feasibility
from models.joint import Joint, JointParams
from simulation.sensitivity import from_unit, nominal, perturbed_cfg
from simulation.sensitivity import ranges as sens_ranges

LOG10_MARGIN_CLIP = (-1.0, 1.0)


class RL_PID_Env(gym.Env):
    """Step-wise PID gain adaptation (see module docstring). ``cfg`` is a config dict (default: the project YAML)."""

    metadata = {"render_modes": []}

    def __init__(self, cfg: Optional[dict] = None, *, action_mode: str = "multiplicative", n_stack: int = 1, randomize: Optional[bool] = None,
                 change_prob: Optional[Dict[str, float]] = None, fixed_context: Optional[dict] = None, horizon_s: Optional[float] = None):
        super().__init__()
        from models.motors import load_base_config
        self.cfg = cfg if cfg is not None else load_base_config()
        e = self.cfg["rl_env"]
        self.e = e
        self.action_mode = action_mode
        self.n_stack = n_stack
        self.randomize = e["randomize"]["plant"] if randomize is None else randomize
        self.change_prob = change_prob or e["change_prob"]
        self.fixed_context = fixed_context
        self.dt = self.cfg["simulation"]["control_loop_dt_s"]
        self.k = int(round(e["decision_interval_s"] / self.dt))
        self.horizon = horizon_s if horizon_s is not None else e["horizon_s"]
        self.n_decisions = int(round(self.horizon / e["decision_interval_s"]))
        self.V = self.cfg["supply"]["V_rated"]
        b = e["gain_bounds"]
        self.lo = np.array([b["Kp"][0], max(b["Ki"][0], 1e-3), b["Kd"][0]])
        self.hi = np.array([b["Kp"][1], b["Ki"][1], b["Kd"][1]])
        self.ki_seed = e.get("ki_seed", 0.5)
        self.n_obs = 16
        self.action_space = spaces.Box(-1.0, 1.0, (3,), np.float32)
        self.observation_space = spaces.Box(-5.0, 5.0, (self.n_obs * n_stack,), np.float32)
        nom = nominal(self.cfg)
        self.i_ref = nom["V_supply"] / nom["R"]
        self.omega_ref = 2.0 * math.pi
        self._ranges = sens_ranges(self.cfg)
        self.twin = None
        self._hist = []

    # ------------------------------------------------------------------ helpers
    def _log_norm(self, g):
        return (np.log(np.maximum(g, self.lo)) - np.log(self.lo)) / (np.log(self.hi) - np.log(self.lo)) * 2.0 - 1.0

    def _sample_context(self):
        p, t = self.e["payload"], self.e["target_deg"]
        rng = self.np_random
        ctx = dict(target=float(rng.uniform(t["min"], t["max"])), mass=float(rng.uniform(0, p["mass_max_kg"]) * (rng.random() > 0.15)),
                   length=float(rng.uniform(p["length_min_m"], p["length_max_m"])), gravity=bool(rng.random() < p["gravity_prob"]),
                   vpct=float(rng.uniform(p["vpct_min"], 100.0)))
        if self.fixed_context:
            ctx.update(self.fixed_context)
        return ctx

    def _sample_plant(self):
        if not self.randomize:
            return {}
        rng = self.np_random
        u = {p: 0.5 for p in self._ranges}                      # unit-cube coordinates: nominal for everything not randomised
        u.update({k: float(rng.random()) for k in ("R", "Kt", "Jm", "Bm", "eta")})
        full = from_unit(self._ranges, u)
        out = {k: full[k] for k in ("R", "Jm", "Bm", "eta")}
        out["Kt"] = out["Ke"] = full["Kt"]                      # one shared K sampled from the Kt range (an ideal motor has Ke = Kt)
        return out

    def _apply_gains(self, g):
        pid = self.twin.pid.p
        pid.Kp, pid.Ki, pid.Kd = float(g[0]), float(g[1]), float(g[2])

    def _set_payload(self, mass):
        ratio = self.cfg["gearbox"]["ratio"]
        old = self.twin.joint.reflected_inertia(ratio)
        self.twin.joint.p.payload_mass_kg = mass
        self.twin.motor.p.Jm += self.twin.joint.reflected_inertia(ratio) - old

    def _obs(self, err_deg, derr, ierr, volt, cur, omega, t_frac):
        c = self.ctx
        marg = feasibility(self.cfg, c["mass"], c["length"], c["target"], gravity=c["gravity"], v_pct=c["vpct"])["margin_path"]
        lm = LOG10_MARGIN_CLIP[1] if not math.isfinite(marg) else float(np.clip(math.log10(max(marg, 1e-3)), *LOG10_MARGIN_CLIP))
        step = max(self.step_deg, 30.0)
        p = self.e["payload"]
        o = np.array([err_deg / step, derr / step, np.clip(ierr, -3, 3), *self._log_norm(self.gains), volt / self.V, cur / self.i_ref, omega / self.omega_ref,
                      self.target_now / 360.0, t_frac, c["mass"] / p["mass_max_kg"], (c["length"] - p["length_min_m"]) / (p["length_max_m"] - p["length_min_m"]),
                      float(c["gravity"]), c["vpct"] / 100.0, lm], dtype=np.float32)
        return np.clip(o, -5.0, 5.0)

    def _stacked(self, o):
        self._hist.append(o)
        self._hist = self._hist[-self.n_stack:]
        pad = [self._hist[0]] * (self.n_stack - len(self._hist))
        return np.concatenate(pad + self._hist).astype(np.float32)

    # ------------------------------------------------------------------ gymnasium API
    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        rng = self.np_random
        self.ctx = self._sample_context()
        self.step_deg = self.ctx["target"]
        self.target_now = self.ctx["target"]
        plant = self._sample_plant()
        cfg = perturbed_cfg(self.cfg, plant) if plant else copy.deepcopy(self.cfg)
        noise = self.e["randomize"]["encoder_noise_counts"] if self.randomize else 0.0
        d_lo, d_hi = self.e["randomize"]["delay_steps"]
        delay = int(rng.integers(d_lo, d_hi + 1)) if self.randomize else 0
        init = self.e["initial_gains"]
        if init == "random":
            g0 = np.exp(rng.uniform(np.log(self.lo), np.log(self.hi)))
        else:
            t = self.cfg["pid_presets"][init]
            g0 = np.array([t["Kp"], t["Ki"], t["Kd"]])
        self.gains = np.clip(g0, self.lo, self.hi) if g0[1] > 0 else np.clip(g0, [self.lo[0], 0.0, self.lo[2]], self.hi)
        joint = Joint(JointParams(payload_mass_kg=self.ctx["mass"], arm_length_m=self.ctx["length"], gravity_on=self.ctx["gravity"]))
        self.twin = build_twin_from_config(cfg, *self.gains, joint=joint, v_pct=self.ctx["vpct"], noise_counts=noise,
                                           seed=int(rng.integers(0, 2 ** 31 - 1)), delay_steps=delay)
        self.i = 0
        self.integral = 0.0
        self.prev_err = math.radians(self.target_now)
        self.last_v = 0.0
        self.peak = 0.0
        self.settle_log, self.theta_log, self.t_log, self.v_log, self.i_log = [], [], [], [], []
        self.payload_change_at = int(rng.integers(self.n_decisions // 4, self.n_decisions // 2)) if rng.random() < self.change_prob["payload"] else -1
        self.target_change_at = int(rng.integers(self.n_decisions // 4, self.n_decisions // 2)) if rng.random() < self.change_prob["target"] else -1
        self._hist = []
        self.t = 0.0
        obs = self._obs(self.target_now, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return self._stacked(obs), {"context": dict(self.ctx), "gains": self.gains.copy()}

    def step(self, action):
        a = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        old = self.gains.copy()
        if self.action_mode == "multiplicative":
            new = self.gains * np.exp(a * math.log(1.0 + self.e["action_step"]))
        else:
            new = np.exp(np.log(self.lo) + (a + 1.0) / 2.0 * (np.log(self.hi) - np.log(self.lo)))
        if self.action_mode != "multiplicative":
            pass
        elif old[1] <= 0.0:                                     # multiplication cannot leave Ki = 0: a positive action seeds it
            new[1] = self.ki_seed * math.exp(max(a[1], 0.0) * math.log(1.0 + self.e["action_step"])) if a[1] > 0 else 0.0
        elif new[1] < self.ki_seed:                           # below the seed Ki snaps to 0 (the integrator can be switched off)
            new[1] = 0.0
        new = np.clip(new, [self.lo[0], 0.0, self.lo[2]], self.hi)
        self.gains = new
        self._apply_gains(self.gains)
        if self.i == self.payload_change_at:
            self._set_payload(float(self.np_random.uniform(0, self.e["payload"]["mass_max_kg"])))
            self.ctx["mass"] = self.twin.joint.p.payload_mass_kg
        if self.i == self.target_change_at:
            self.target_now = float(self.np_random.uniform(self.e["target_deg"]["min"], self.e["target_deg"]["max"]))
            self.step_deg = abs(self.target_now - math.degrees(self.twin.gearbox.output_position(self.twin.state.motor_state[2])))

        rew = self.e["reward"]
        errs, vs = [], []
        i_last = 0.0
        diverged = False
        for _ in range(self.k):
            row = self.twin.step(math.radians(self.target_now))
            errs.append(row["error"]); vs.append(row["V_cmd"]); i_last = row["i_motor"]
            self.theta_log.append(row["theta_out"]); self.t_log.append(row["t"]); self.v_log.append(row["V_cmd"]); self.i_log.append(row["i_motor"])
            if not math.isfinite(row["theta_out"]) or abs(math.degrees(row["error"])) > 8.0 * max(self.step_deg, 60.0):
                diverged = True
                break
        errs, vs = np.array(errs), np.array(vs)
        self.t = self.twin.state.t
        scale = math.radians(max(self.step_deg, 30.0))
        t_w = 0.5 + self.t / self.horizon
        e_term = rew["w_error"] * t_w * float(np.mean((errs / scale) ** 2))
        u_term = rew["w_effort"] * float(np.mean(vs ** 2)) / (self.ctx["vpct"] / 100.0 * self.V) ** 2
        ch_term = rew["w_chatter"] * (float(np.mean(np.abs(np.diff(np.concatenate([[self.last_v], vs]))))) / (self.V * self.ctx["vpct"] / 100.0))
        g_term = rew["w_gain_change"] * float(np.sum(np.abs(np.log(np.maximum(self.gains, 1e-9)) - np.log(np.maximum(old, 1e-9)))))
        theta_deg = math.degrees(self.theta_log[-1]) if self.theta_log else 0.0
        over = max(0.0, (theta_deg - self.target_now) / max(self.target_now, 30.0)) if self.target_now > 0 else 0.0
        o_term = rew["w_overshoot"] * over
        reward = -(e_term + u_term + ch_term + g_term + o_term)
        breakdown = {"error": -e_term, "effort": -u_term, "chatter": -ch_term, "gain_change": -g_term, "overshoot": -o_term, "divergence": 0.0}
        if diverged:
            reward -= rew["diverge_penalty"]
            breakdown["divergence"] = -rew["diverge_penalty"]
        self.last_v = float(vs[-1]) if len(vs) else self.last_v
        derr = float(errs[-1] - self.prev_err) / (self.k * self.dt) if len(errs) else 0.0
        self.prev_err = float(errs[-1]) if len(errs) else self.prev_err
        self.integral += float(np.sum(errs) * self.dt)
        self.i += 1
        truncated = self.i >= self.n_decisions
        terminated = diverged
        obs = self._obs(math.degrees(errs[-1]) if len(errs) else 0.0, math.degrees(derr), self.integral / max(scale, 1e-3) * 0.5, self.last_v, i_last,
                        self.twin.gearbox.output_speed(self.twin.state.motor_state[1]), self.t / self.horizon)
        info = {"reward_breakdown": breakdown, "gains": self.gains.copy(), "t": self.t}
        if truncated or terminated:
            info["episode_metrics"] = self.episode_metrics()
        return self._stacked(obs), float(reward), terminated, truncated, info

    def episode_metrics(self) -> Dict[str, float]:
        """Step-response metrics of the episode so far (uses the final target; meaningful when no target change happened)."""
        from simulation.metrics import all_metrics

        t = np.array(self.t_log)
        th = np.degrees(self.theta_log)
        if len(t) < 3:
            return {}
        return all_metrics(t, th, self.target_now, np.array(self.v_log), np.array(self.i_log))
