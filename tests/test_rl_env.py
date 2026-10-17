"""G4.1: RL_PID_Env (PRE-VALIDATION PROTOTYPE): Gymnasium contract, shared physics, reward, randomisation, mid-episode changes."""

import math
import os

import numpy as np
import pytest

pytest.importorskip("gymnasium")

from environments.rl_pid_env import RL_PID_Env  # noqa: E402
from models.factory import build_twin_from_config  # noqa: E402
from models.joint import Joint, JointParams  # noqa: E402

FIXED = dict(target=90.0, mass=0.0, length=0.05, gravity=False, vpct=100.0)


def env_fixed(**kw):
    return RL_PID_Env(randomize=False, fixed_context=FIXED, **kw)


def test_gymnasium_env_checker_passes():
    from gymnasium.utils.env_checker import check_env

    check_env(RL_PID_Env(), skip_render_check=True)
    check_env(RL_PID_Env(action_mode="direct", n_stack=3), skip_render_check=True)


def test_random_rollouts_stay_finite_and_in_bounds():
    n = 1000 if os.environ.get("DTRL_STRESS") == "1" else 40
    env = RL_PID_Env(change_prob={"payload": 0.5, "target": 0.5})
    rng = np.random.default_rng(0)
    steps = 0
    for ep in range(n):
        obs, _ = env.reset(seed=ep)
        done = False
        while not done:
            obs, r, term, trunc, info = env.step(rng.uniform(-1, 1, 3).astype(np.float32))
            assert np.all(np.isfinite(obs)) and np.isfinite(r) and np.all(np.abs(obs) <= 5.0)
            assert np.all(env.gains >= 0) and np.all(env.gains <= env.hi * (1 + 1e-9))
            done = term or trunc
            steps += 1
    assert steps >= n * 20


def test_zero_action_reproduces_the_fixed_gain_twin_exactly():
    env = env_fixed()
    env.reset(seed=0)
    done = False
    while not done:
        _, _, term, trunc, info = env.step(np.zeros(3, np.float32))
        done = term or trunc
    cfg = env.cfg
    t = cfg["pid_presets"]["tuned"]
    tw = build_twin_from_config(cfg, t["Kp"], t["Ki"], t["Kd"], joint=Joint(JointParams(payload_mass_kg=0.0, arm_length_m=0.05)))
    ref = tw.run(math.radians(90), 2000)
    assert np.array_equal(np.array(env.theta_log), ref["theta_out"])                    # same physics, same numbers
    m = info["episode_metrics"]
    assert m["overshoot_pct"] == pytest.approx(1.73, abs=0.1) and m["settle_s"] == pytest.approx(0.292, abs=0.005)   # the G3.1 Tuned row


def test_reset_seed_reproducible():
    a, b, c = RL_PID_Env(), RL_PID_Env(), RL_PID_Env()
    oa, ia = a.reset(seed=5)
    ob, ib = b.reset(seed=5)
    oc, ic = c.reset(seed=6)
    assert np.array_equal(oa, ob) and ia["context"] == ib["context"] and ia["context"] != ic["context"]
    for _ in range(5):
        ra = a.step(np.array([0.3, -0.2, 0.5], np.float32))
        rb = b.step(np.array([0.3, -0.2, 0.5], np.float32))
        assert np.array_equal(ra[0], rb[0]) and ra[1] == rb[1]


def test_multiplicative_actions_are_bounded_and_scale_free():
    env = env_fixed()
    env.reset(seed=0)
    g0 = env.gains.copy()
    env.step(np.ones(3, np.float32))
    assert env.gains[0] == pytest.approx(g0[0] * 1.10) and env.gains[2] == pytest.approx(g0[2] * 1.10)      # +10 % per decision
    for _ in range(80):
        env.step(np.ones(3, np.float32))
        if env.i >= env.n_decisions - 1:
            break
    assert np.all(env.gains <= env.hi * (1 + 1e-9))                                                              # clipped at the bounds
    env.reset(seed=0)
    for _ in range(80):
        _, _, term, trunc, _ = env.step(-np.ones(3, np.float32))
        if term or trunc:
            break
    assert env.gains[0] >= env.lo[0] * (1 - 1e-9) and env.gains[2] >= env.lo[2] * (1 - 1e-9)


def test_ki_can_rise_from_zero_and_snap_back_to_zero():
    env = env_fixed()
    env.reset(seed=0)
    assert env.gains[1] == 0.0                                                      # the Tuned preset has no integral action
    env.step(np.array([0.0, 1.0, 0.0], np.float32))
    seed_ki = env.e["ki_seed"]
    assert env.gains[1] == pytest.approx(seed_ki * 1.10)                              # it rose
    for _ in range(5):
        env.step(np.array([0.0, 1.0, 0.0], np.float32))
    assert env.gains[1] > seed_ki * 1.5
    for _ in range(80):
        env.step(np.array([0.0, -1.0, 0.0], np.float32))
        if env.gains[1] == 0.0 or env.i >= env.n_decisions - 1:
            break
    assert env.gains[1] == 0.0                                                      # and the integrator can be switched off again
    e2 = env_fixed()
    e2.reset(seed=0)
    e2.step(np.array([0.0, -1.0, 0.0], np.float32))
    assert e2.gains[1] == 0.0                                                      # a negative action on Ki = 0 keeps it at 0


def test_trained_style_random_actions_reach_nonzero_ki():
    env = env_fixed()
    env.reset(seed=1)
    rng = np.random.default_rng(0)
    seen = 0.0
    for _ in range(env.n_decisions - 1):
        env.step(rng.uniform(-1, 1, 3).astype(np.float32))
        seen = max(seen, env.gains[1])
    assert seen > 0.0


def test_direct_mode_maps_actions_onto_the_log_range():
    env = RL_PID_Env(randomize=False, fixed_context=FIXED, action_mode="direct")
    env.reset(seed=0)
    env.step(-np.ones(3, np.float32))
    assert env.gains[0] == pytest.approx(env.lo[0]) and env.gains[2] == pytest.approx(env.lo[2])
    env.reset(seed=0)
    env.step(np.ones(3, np.float32))
    assert env.gains[0] == pytest.approx(env.hi[0]) and env.gains[2] == pytest.approx(env.hi[2])
    env.reset(seed=0)
    env.step(np.zeros(3, np.float32))
    assert env.gains[0] == pytest.approx(math.sqrt(env.lo[0] * env.hi[0]))                                     # log-midpoint


def test_reward_breakdown_adds_up_and_penalises_thrashing():
    env = env_fixed()
    env.reset(seed=0)
    _, r, _, _, info = env.step(np.zeros(3, np.float32))
    bd = info["reward_breakdown"]
    assert set(bd) == {"error", "effort", "chatter", "gain_change", "overshoot", "divergence"}
    assert r == pytest.approx(sum(bd.values()), abs=1e-12) and all(v <= 0 for v in bd.values())
    assert bd["gain_change"] == 0.0
    env.reset(seed=0)
    _, r2, _, _, info2 = env.step(np.ones(3, np.float32))
    assert info2["reward_breakdown"]["gain_change"] < 0                                                          # changing gains costs reward


def test_divergence_terminates_with_the_penalty(monkeypatch):
    env = env_fixed()
    env.reset(seed=0)
    real = env.twin.step

    def bad(theta_ref):
        row = real(theta_ref)
        row["theta_out"] = float("nan")
        return row

    monkeypatch.setattr(env.twin, "step", bad)
    _, r, term, trunc, info = env.step(np.zeros(3, np.float32))
    assert term and not trunc and info["reward_breakdown"]["divergence"] == -env.e["reward"]["diverge_penalty"] and r <= -env.e["reward"]["diverge_penalty"]


def test_episode_always_runs_to_the_horizon_unless_it_diverges():
    env = env_fixed()
    env.reset(seed=0)
    n, trunc = 0, False
    while not trunc:
        _, _, term, trunc, _ = env.step(np.zeros(3, np.float32))
        assert not term
        n += 1
    assert n == int(round(env.horizon / env.e["decision_interval_s"])) == 100


def test_observation_layout_and_stacking():
    env = RL_PID_Env(n_stack=3, randomize=False, fixed_context=FIXED)
    obs, _ = env.reset(seed=0)
    assert obs.shape == (16 * 3,) and np.array_equal(obs[:16], obs[16:32]) and np.array_equal(obs[16:32], obs[32:])     # padded with the first frame
    obs2, *_ = env.step(np.zeros(3, np.float32))
    assert np.array_equal(obs2[:16], obs[:16]) and not np.array_equal(obs2[32:], obs[32:])
    assert RL_PID_Env().observation_space.shape == (16,)
    o, _ = env_fixed().reset(seed=0)
    assert o[0] == pytest.approx(1.0) and o[9] == pytest.approx(0.25)                                              # error/step = 1; target/360 = 0.25


def test_feasibility_margin_is_part_of_the_observation():
    env = RL_PID_Env(randomize=False, fixed_context=dict(target=90.0, mass=2.0, length=0.15, gravity=True, vpct=100.0))
    o, _ = env.reset(seed=0)
    assert o[-1] == pytest.approx(math.log10(0.724), abs=0.01)                                                           # the infeasible 2 kg x 15 cm case
    env2 = env_fixed()
    assert env2.reset(seed=0)[0][-1] == pytest.approx(1.0)                                                               # no gravity: margin clipped at +1


def test_mid_episode_payload_change_updates_the_inertia_consistently():
    env = RL_PID_Env(randomize=False, fixed_context=dict(FIXED, mass=0.5, length=0.1), change_prob={"payload": 1.0, "target": 0.0})
    env.reset(seed=3)
    j0 = env.twin.motor.p.Jm
    seen = False
    for _ in range(env.n_decisions):
        _, _, term, trunc, _ = env.step(np.zeros(3, np.float32))
        if not seen and env.i > env.payload_change_at >= 0:
            seen = True
            ratio = env.cfg["gearbox"]["ratio"]
            base = env.cfg["base_motor"]["estimated"]["Jm_kgm2"]
            assert env.twin.motor.p.Jm == pytest.approx(base + env.twin.joint.reflected_inertia(ratio), rel=1e-12)
            assert env.ctx["mass"] != 0.5 or j0 == env.twin.motor.p.Jm
        if term or trunc:
            break
    assert seen


def test_mid_episode_target_change_moves_the_reference():
    env = RL_PID_Env(randomize=False, fixed_context=FIXED, change_prob={"payload": 0.0, "target": 1.0})
    env.reset(seed=2)
    first = env.target_now
    changed = False
    for _ in range(env.n_decisions):
        _, _, term, trunc, _ = env.step(np.zeros(3, np.float32))
        changed |= env.target_now != first
        if term or trunc:
            break
    assert changed and 30.0 <= env.target_now <= 180.0


def test_domain_randomisation_stays_inside_the_documented_ranges():
    env = RL_PID_Env()
    from simulation.sensitivity import ranges
    spec = ranges(env.cfg)
    Rs, Js, ks = [], [], []
    for s in range(60):
        env.reset(seed=s)
        d = env.twin.motor.p
        Rs.append(d.R); Js.append(d.Jm); ks.append((d.Kt, d.Ke))
        assert spec["R"]["lo"] * 0.999 <= d.R <= spec["R"]["hi"] * 1.001
        assert d.Kt == d.Ke                                                                                         # one shared K
        assert env.ctx["vpct"] >= env.e["payload"]["vpct_min"] and 30.0 <= env.ctx["target"] <= 180.0
    assert np.std(Rs) > 0 and np.std(Js) > 0                                                                        # it actually varies
    fixed = RL_PID_Env(randomize=False)
    fixed.reset(seed=0)
    assert fixed.twin.motor.p.R == fixed.cfg["base_motor"]["derived"]["method_c"]["R_ohm"]
