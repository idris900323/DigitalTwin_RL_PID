"""G5: the PyBullet URDF matches the Python joint model (inertia about the shaft, gravity moment). The PyBullet wrapper itself is skipped
unless ``pybullet`` is importable (PRE-VALIDATION)."""


import pytest

from models.joint import Joint, JointParams
from models.motors import load_base_config
from pybullet_sim import joint_urdf, urdf_axis_inertia


@pytest.mark.parametrize("m,L,arm_m", [(0.0, 0.0, 0.0), (1.0, 0.10, 0.0), (2.0, 0.15, 0.3)])
def test_urdf_matches_python_joint(m, L, arm_m):
    cfg = load_base_config()
    p = JointParams(payload_mass_kg=m, arm_length_m=L, arm_mass_kg=arm_m, gravity_on=True)
    got = urdf_axis_inertia(joint_urdf(cfg, p))
    ratio = cfg["gearbox"]["ratio"]
    j = Joint(p)
    want_J = cfg["base_motor"]["estimated"]["Jm_kgm2"] * ratio ** 2 + j.output_inertia()
    assert got["J_axis"] == pytest.approx(want_J, rel=1e-6, abs=1e-8)
    assert got["gravity_moment"] == pytest.approx(j.gravity_moment(), rel=1e-6, abs=1e-8)


def test_pybullet_free_pendulum_period_if_installed():
    pb = pytest.importorskip("pybullet")  # noqa: F841
    from pybullet_sim.sim import PyBulletJointSim, hanging_period_s

    cfg = load_base_config()
    p = JointParams(payload_mass_kg=1.0, arm_length_m=0.1, gravity_on=True)
    sim = PyBulletJointSim(cfg, p, dt=0.0005)
    sim.pb.resetJointState(sim.body, 0, 0.05, physicsClientId=sim.cid)
    j = Joint(p)
    T = hanging_period_s(cfg["base_motor"]["estimated"]["Jm_kgm2"] * cfg["gearbox"]["ratio"] ** 2 + j.output_inertia(), j.gravity_moment())
    crossings, prev, t = [], 0.05, 0.0
    for _ in range(int(3 * T / 0.0005)):
        th, _ = sim.step(0.0)
        t += 0.0005
        if prev > 0 >= th:
            crossings.append(t)
        prev = th
    sim.close()
    assert len(crossings) >= 2 and (crossings[1] - crossings[0]) == pytest.approx(T, rel=0.02)
