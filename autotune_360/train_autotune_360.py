"""RL auto-tuner for the servo PID twin (numpy only -- no PyTorch / Stable-Baselines needed).

PRE-VALIDATION PROTOTYPE: trained on the unvalidated, datasheet-derived twin (method_c). Its gains are only
as good as that model; nothing here has been validated against real hardware.

What it learns
--------------
A policy  pi(payload, target) -> (Kp, Ki, Kd).  Each "episode" is one step response from 0 deg to a target
angle in 5-360 deg (a *position target* range; the joint is not a continuous-rotation servo):
  1. sample a context (arm length, payload mass, gravity on/off, motor speed limit, target angle)
  2. the policy proposes gains (Gaussian exploration around its mean)
  3. simulate the step with those gains (same physics as the browser twin)
  4. reward = -cost(step response)      (one-step MDP == contextual bandit)
Trained with REINFORCE (policy gradient) + a per-context baseline, MLP 8 -> 32 -> 32 -> 3.

Feasibility: contexts whose gravity holding torque exceeds what the motor can deliver
(margin = available / peak hold < 1.2, see models/feasibility.py) cannot be tracked, so by default
training samples only feasible contexts (rejection sampling) and evaluation reports both the
feasible-only and the full (unfiltered) held-out set, with the infeasible fraction.

Output: autotune_policy_360.json (tiny MLP weights, evaluated in plain JS by the browser page) and
autotune_policy_360.meta.json (seeds, hyperparameters, config hash, git commit, held-out table, ...).

Reproduce the committed weights (same machine, same numpy):
    python autotune_360/train_autotune_360.py --seed 0          (about 3-4 minutes on a laptop)
"""
import argparse, hashlib, json, pathlib, platform, subprocess, sys, time
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from models.feasibility import available_torque, feasibility_arrays   # noqa: E402

FEATURE_VERSION = 1      # bump if features() changes: the browser page must be updated to match
MARGINAL_MARGIN = 1.2    # keep equal to config/motor_parameters.yaml feasibility.marginal_margin (checked by a test)

# ------------------------------------------------------------------ plant (mirrors the JS / Python twin, method_c)
CFG = dict(V_rated=12.0, ratio=180.0, eff=0.80, cpr=9360,
           R=1.6, Kt=1.974e-3, Ke=6.366e-3, Jm=5.0e-7, Bm=1.0e-6,
           dt=0.001, duration=2.0, ref_deg=90.0, tau_f=0.01)

NOISE_COUNTS = 1.0   # RMS encoder jitter in counts (0 = ideal encoder)

def simulate_batch(Kp, Ki, Kd, mass, length, gravity, vpct, ref_deg=None, cfg=CFG, noise=None, nrng=None):
    """Vectorised closed loop (encoder quantisation, filtered D, anti-windup, +-V saturation, RK4).
    Arguments are arrays of shape (B,). Returns true output angle [rad] (N,B) and voltage (N,B)."""
    Kp, Ki, Kd, mass, length, gravity, vpct = (np.asarray(x, float) for x in (Kp, Ki, Kd, mass, length, gravity, vpct))
    B = Kp.shape[0]
    dt = cfg['dt']; N = int(round(cfg['duration'] / dt))
    ref = np.radians(np.full(B, cfg['ref_deg']) if ref_deg is None else np.asarray(ref_deg, float))   # (B,) target angle
    ratio, eff, rpc = cfg['ratio'], cfg['eff'], 2 * np.pi / cfg['cpr']
    R, Kt, Ke, Bm = cfg['R'], cfg['Kt'], cfg['Ke'], cfg['Bm']
    Jm = cfg['Jm'] + mass * length ** 2 / ratio ** 2          # payload inertia reflected to the motor shaft
    vmax = cfg['V_rated'] * vpct / 100.0                        # "motor speed limit" = voltage cap
    alpha = dt / (cfg['tau_f'] + dt)
    w = np.zeros(B); th = np.zeros(B)
    integ = np.zeros(B); prev = np.zeros(B); fd = np.zeros(B)
    th_log = np.empty((N, B)); v_log = np.empty((N, B))
    noise = NOISE_COUNTS if noise is None else noise
    nrng = nrng if nrng is not None else np.random.default_rng(0)
    for n in range(N):
        th_true = th / ratio
        th_meas = th_true + noise * rpc * nrng.standard_normal(B)
        err = ref - np.round(th_meas / rpc) * rpc
        fd += alpha * ((err - prev) / dt - fd)
        tent = integ + err * dt
        u = Kp * err + Ki * tent + Kd * fd
        hi, lo = u > vmax, u < -vmax
        V = np.clip(u, -vmax, vmax)
        integ = np.where((hi & (err > 0)) | (lo & (err < 0)), integ, tent)   # conditional anti-windup
        prev = err
        tau = gravity * mass * 9.81 * length * np.sin(th_true) / (ratio * eff)  # arm gravity, 0 deg = hanging
        f = lambda ww: (Kt * (V - Ke * ww) / R - Bm * ww - tau) / Jm
        k1w = f(w);             k1t = w
        k2w = f(w + .5*dt*k1w); k2t = w + .5*dt*k1w
        k3w = f(w + .5*dt*k2w); k3t = w + .5*dt*k2w
        k4w = f(w + dt*k3w);    k4t = w + dt*k3w
        w = w + dt/6 * (k1w + 2*k2w + 2*k3w + k4w)
        th = th + dt/6 * (k1t + 2*k2t + 2*k3t + k4t)
        th_log[n] = th / ratio; v_log[n] = V
    return th_log, v_log

def step_cost(th_log, v_log, vpct, ref_deg, cfg=CFG):
    """Lower is better. Tracking (time-weighted) + overshoot + steady-state error + voltage chatter."""
    N = th_log.shape[0]; ref = np.radians(np.asarray(ref_deg, float)); refn = np.maximum(ref, np.radians(30.0))
    t = (np.arange(1, N + 1) / N)[:, None]
    e = (ref - th_log) / refn
    track = np.mean(np.abs(e) * (0.2 + t), axis=0)
    overshoot = np.maximum(0.0, th_log.max(axis=0) - ref) / refn
    sse = np.mean(np.abs(e[-N // 10:]), axis=0)
    chatter = np.mean(np.abs(np.diff(v_log, axis=0)), axis=0) / (cfg['V_rated'] * np.asarray(vpct) / 100.0)
    return np.minimum(4 * track + 3 * overshoot + 10 * sse + 1.5 * chatter, 6.0)

# ------------------------------------------------------------------ payload ranges = the sliders in the browser page
MASS_MAX, LEN_MIN, LEN_MAX, V_MIN = 2.0, 0.02, 0.15, 10.0
REF_MIN, REF_MAX = 5.0, 360.0
LO = np.array([0.5, 0.1, 0.005]); HI = np.array([50.0, 200.0, 5.0])       # Kp, Ki, Kd search range (log scale)

def _raw_context(n, rng):
    mass = rng.uniform(0, MASS_MAX, n) * (rng.random(n) > 0.15)            # some no-payload cases
    length = rng.uniform(LEN_MIN, LEN_MAX, n)
    gravity = (rng.random(n) < 0.5).astype(float)
    vpct = rng.uniform(V_MIN, 100.0, n)
    ref = np.where(rng.random(n) < 0.25, 90.0, rng.uniform(REF_MIN, REF_MAX, n))   # target angle [deg]; 25% at the 90 deg default
    return mass, length, gravity, vpct, ref

def context_margin(mass, length, gravity, vpct, ref, cfg=CFG):
    """Feasibility margin (available stall torque / peak gravity holding torque on the path)."""
    ta = available_torque(cfg['Kt'], cfg['R'], cfg['ratio'], cfg['eff'], cfg['V_rated'], vpct)
    return feasibility_arrays(ta, mass, length, ref, gravity, marginal_margin=MARGINAL_MARGIN)['margin_path']

def sample_context(n, rng, feasible_only=True, stats=None):
    """Draw n contexts. feasible_only=True rejection-samples until all n have margin >= MARGINAL_MARGIN.
    ``stats`` (dict) accumulates 'drawn' and 'infeasible' counts so the infeasible fraction can be reported."""
    if not feasible_only:
        ctx = _raw_context(n, rng)
        if stats is not None:
            stats['drawn'] = stats.get('drawn', 0) + n
            stats['infeasible'] = stats.get('infeasible', 0) + int(np.sum(context_margin(*ctx) < MARGINAL_MARGIN))
        return ctx
    parts = []; have = 0
    while have < n:
        ctx = _raw_context(max(n, 64), rng)
        ok = context_margin(*ctx) >= MARGINAL_MARGIN
        if stats is not None:
            stats['drawn'] = stats.get('drawn', 0) + len(ok)
            stats['infeasible'] = stats.get('infeasible', 0) + int(np.sum(~ok))
        parts.append(tuple(a[ok] for a in ctx)); have += int(ok.sum())
    return tuple(np.concatenate([p[i] for p in parts])[:n] for i in range(5))

def features(mass, length, gravity, vpct, ref_deg):
    """Policy input. MUST match the JS in the browser page."""
    return np.stack([mass / MASS_MAX,
                     (length - LEN_MIN) / (LEN_MAX - LEN_MIN),
                     gravity,
                     vpct / 100.0,
                     gravity * mass * length / (MASS_MAX * LEN_MAX),       # gravity torque on the arm
                     mass * length ** 2 / (MASS_MAX * LEN_MAX ** 2),            # payload inertia
                     ref_deg / 360.0,                                           # target angle
                     gravity * mass * length * np.sin(np.radians(ref_deg)) / (MASS_MAX * LEN_MAX)], axis=1)  # holding torque at target

def gains_from_z(z):
    u = 1.0 / (1.0 + np.exp(-z))
    return LO * (HI / LO) ** u

# ------------------------------------------------------------------ tiny MLP policy (8 -> 32 -> 32 -> 3) with manual backprop
class Policy:
    def __init__(self, rng, hidden=32):   # inputs: the 8 features() entries
        s = lambda a, b: rng.normal(0, np.sqrt(1.0 / a), (a, b))
        self.p = dict(W1=s(8, hidden), b1=np.zeros(hidden), W2=s(hidden, hidden), b2=np.zeros(hidden),
                      W3=s(hidden, 3) * 0.1,
                      b3=np.array([0.0, 0.83, -0.69]),                     # start near the legacy default gains (5, 20, 0.05)
                      logstd=np.full(3, np.log(0.5)))
        self.m = {k: np.zeros_like(v) for k, v in self.p.items()}; self.v = {k: np.zeros_like(v) for k, v in self.p.items()}; self.t = 0

    def forward(self, X):
        p = self.p
        h1 = np.tanh(X @ p['W1'] + p['b1']); h2 = np.tanh(h1 @ p['W2'] + p['b2'])
        return h2 @ p['W3'] + p['b3'], (X, h1, h2)

    def adam_ascent(self, g, lr):
        self.t += 1
        for k in self.p:
            self.m[k] = 0.9 * self.m[k] + 0.1 * g[k]; self.v[k] = 0.999 * self.v[k] + 0.001 * g[k] ** 2
            mh = self.m[k] / (1 - 0.9 ** self.t); vh = self.v[k] / (1 - 0.999 ** self.t)
            self.p[k] += lr * mh / (np.sqrt(vh) + 1e-8)

    def grads(self, cache, dmu, dlogstd):
        X, h1, h2 = cache; p = self.p
        g = dict(W3=h2.T @ dmu, b3=dmu.sum(0), logstd=dlogstd)
        d2 = (dmu @ p['W3'].T) * (1 - h2 ** 2)
        g['W2'] = h1.T @ d2; g['b2'] = d2.sum(0)
        d1 = (d2 @ p['W2'].T) * (1 - h1 ** 2)
        g['W1'] = X.T @ d1; g['b1'] = d1.sum(0)
        return g

# ------------------------------------------------------------------ training
ADAM = dict(beta1=0.9, beta2=0.999, eps=1e-8)   # as hard-coded in Policy.adam_ascent

def child_rngs(seed, names=("init", "context", "action", "noise")):
    """One independent Generator per purpose, derived from a single seed (results don't depend on call order)."""
    kids = np.random.SeedSequence(seed).spawn(len(names))
    return {n: np.random.default_rng(k) for n, k in zip(names, kids)}

def train(iters=300, contexts=128, samples=8, lr=3e-3, seed=0, feasible_only=True):
    rngs = child_rngs(seed)
    pol = Policy(rngs["init"])
    stats = {}
    t0 = time.time()
    for it in range(iters):
        m, L, g, v, R = sample_context(contexts, rngs["context"], feasible_only, stats)
        X = features(m, L, g, v, R)
        mu, cache = pol.forward(X)                                            # (C,3)
        std = np.exp(pol.p['logstd'])
        eps = rngs["action"].normal(size=(contexts, samples, 3))
        z = mu[:, None, :] + std * eps                                        # (C,K,3) sampled actions
        gains = gains_from_z(z.reshape(-1, 3))
        rep = lambda a: np.repeat(a, samples)
        th, V = simulate_batch(gains[:, 0], gains[:, 1], gains[:, 2], rep(m), rep(L), rep(g), rep(v), rep(R), nrng=rngs["noise"])
        cost = step_cost(th, V, rep(v), rep(R)).reshape(contexts, samples)
        adv = -(cost - cost.mean(1, keepdims=True))                           # per-context baseline
        adv /= adv.std() + 1e-8
        n = contexts * samples
        dmu = (adv[:, :, None] * eps / std).sum(1) / n                        # d logpi / d mu = eps/std
        dlogstd = (adv[:, :, None] * (eps ** 2 - 1)).sum((0, 1)) / n
        pol.adam_ascent(pol.grads(cache, dmu, dlogstd), lr)
        pol.p['logstd'] = np.clip(pol.p['logstd'], np.log(0.03), np.log(1.0))
        if it % 20 == 0 or it == iters - 1:
            print(f"iter {it:4d}  mean cost {cost.mean():.3f}  best-of-{samples} {cost.min(1).mean():.3f}  "
                  f"std {np.round(np.exp(pol.p['logstd']), 2)}  ({time.time() - t0:.0f}s)", flush=True)
    frac = stats.get('infeasible', 0) / max(stats.get('drawn', 1), 1)
    print(f"\ntraining contexts: feasible_only={feasible_only}; {100 * frac:.1f}% of {stats.get('drawn', 0)} raw draws were "
          f"infeasible/marginal (margin < {MARGINAL_MARGIN})" + (" and were rejected" if feasible_only else " and were kept"))
    return pol, dict(feasible_only=feasible_only, raw_draws=stats.get('drawn', 0), raw_infeasible_fraction=frac)

def policy_gains(pol, m, L, g, v, R):
    mu, _ = pol.forward(features(m, L, g, v, R))
    return gains_from_z(mu)

def _score(G, ctx, nrng):
    m, L, g, v, R = ctx
    th, V = simulate_batch(G[:, 0], G[:, 1], G[:, 2], m, L, g, v, R, nrng=nrng)
    c = step_cost(th, V, v, R)
    return c, np.mean(np.abs(np.degrees(th[-1]) - R) < 0.02 * R)

def evaluate(pol, n=1000, seed=123):
    """Held-out evaluation on a feasible-only set and on the full (unfiltered) set. Returns a dict of results."""
    out = {}
    for label, feas in (("feasible-only", True), ("full (incl. infeasible)", False)):
        stats = {}
        ctx = sample_context(n, np.random.default_rng(seed), feasible_only=feas, stats=stats)
        infeas = float(np.mean(context_margin(*ctx) < MARGINAL_MARGIN))
        m, L, g, v, R = ctx
        rows = {"RL auto-tune": policy_gains(pol, m, L, g, v, R),
                "Legacy default 5/20/0.05": np.tile([5, 20, 0.05], (n, 1)),
                "'Tuned' preset 15/0/0.3": np.tile([15, 0, 0.3], (n, 1))}
        print(f"\nHeld-out contexts, {label} (n={n}, targets 5-360 deg, infeasible/marginal fraction of this set "
              f"{100 * infeas:.1f}%):  mean cost | share within 2% of target at the end")
        out[label] = dict(n=n, infeasible_fraction=infeas, rows={})
        for name, G in rows.items():
            c, ok = _score(G, ctx, np.random.default_rng(seed + 1))
            print(f"  {name:26s} {c.mean():6.3f} | {100 * ok:5.1f}%")
            out[label]["rows"][name] = dict(mean_cost=float(c.mean()), within_2pct=float(ok))
    # brute-force sanity on a few feasible payload+target cases
    rs = np.random.default_rng(7); k = 12; m2, L2, g2, v2, R2 = sample_context(k, rs); cand = 400
    G = np.exp(rs.uniform(np.log(LO), np.log(HI), (cand, 3)))
    best = []
    for i in range(k):
        rp = lambda a: np.full(cand, a)
        th, V = simulate_batch(G[:, 0], G[:, 1], G[:, 2], rp(m2[i]), rp(L2[i]), rp(g2[i]), rp(v2[i]), rp(R2[i]),
                               nrng=np.random.default_rng(seed + 2))
        best.append(step_cost(th, V, rp(v2[i]), rp(R2[i])).min())
    Gp = policy_gains(pol, m2, L2, g2, v2, R2)
    th, V = simulate_batch(Gp[:, 0], Gp[:, 1], Gp[:, 2], m2, L2, g2, v2, R2, nrng=np.random.default_rng(seed + 2))
    pc = float(step_cost(th, V, v2, R2).mean())
    print(f"\nvs brute-force search ({cand} random gain sets per case, {k} feasible cases): "
          f"brute-force best {np.mean(best):.3f}  |  RL policy {pc:.3f}")
    out["brute_force"] = dict(cases=k, candidates=cand, best_of_n=float(np.mean(best)), policy=pc)
    return out


def export(pol, path):
    d = {k: np.asarray(v).tolist() for k, v in pol.p.items() if k != 'logstd'}
    d.update(lo=LO.tolist(), hi=HI.tolist(), mass_max=MASS_MAX, len_min=LEN_MIN, len_max=LEN_MAX)
    with open(path, "w") as f: json.dump(d, f)
    print("saved", path)

def _git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"

def _sha256(path):
    try:
        return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
    except Exception:
        return "unknown"

def main(argv=None):
    ap = argparse.ArgumentParser(description="Train the numpy REINFORCE PID auto-tuner (pre-validation prototype).")
    ap.add_argument("--seed", type=int, default=0, help="master seed; child generators are derived from it (default 0)")
    ap.add_argument("--iters", type=int, default=300)
    ap.add_argument("--contexts", type=int, default=128, help="contexts per iteration")
    ap.add_argument("--samples", type=int, default=8, help="gain samples per context")
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--include-infeasible", action="store_true", help="also train on torque-infeasible contexts (not recommended)")
    ap.add_argument("--out", default=str(HERE / "autotune_policy_360.json"), help="policy JSON path (meta goes next to it)")
    a = ap.parse_args(argv)
    t0 = time.time()
    print(f"seed={a.seed} iters={a.iters} contexts={a.contexts} samples={a.samples} lr={a.lr} "
          f"feasible_only={not a.include_infeasible}")
    policy, train_info = train(a.iters, a.contexts, a.samples, a.lr, a.seed, feasible_only=not a.include_infeasible)
    table = evaluate(policy)
    export(policy, a.out)
    meta = dict(
        script="autotune_360/train_autotune_360.py", pre_validation_prototype=True,
        seed=a.seed, child_generators=["init", "context", "action", "noise"], eval_seed=123,
        iterations=a.iters, contexts_per_iteration=a.contexts, samples_per_context=a.samples, learning_rate=a.lr,
        adam=ADAM, gain_bounds=dict(lo=LO.tolist(), hi=HI.tolist(), scale="log"),
        payload_ranges=dict(mass_max_kg=MASS_MAX, len_min_m=LEN_MIN, len_max_m=LEN_MAX, v_min_pct=V_MIN,
                            ref_min_deg=REF_MIN, ref_max_deg=REF_MAX),
        feature_function_version=FEATURE_VERSION, marginal_margin=MARGINAL_MARGIN, training=train_info,
        config_sha256=_sha256(ROOT / "config" / "motor_parameters.yaml"), git_commit=_git_commit(),
        date_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), runtime_s=round(time.time() - t0, 1),
        numpy=np.__version__, python=platform.python_version(), policy_sha256=_sha256(a.out), held_out=table)
    meta_path = str(pathlib.Path(a.out).with_suffix("")) + ".meta.json"
    with open(meta_path, "w") as f: json.dump(meta, f, indent=2)
    print("saved", meta_path)

if __name__ == "__main__":
    main()
