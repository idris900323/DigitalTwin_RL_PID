"""G5: the PyBullet URDF matches the Python joint model (inertia about the shaft, gravity moment). The PyBullet wrapper itself is skipped
unless ``pybullet`` is importable (PRE-VALIDATION)."""


import math

import pytest

from models.joint import Joint, JointParams
from models.motors import load_base_config
from pybullet_sim import joint_urdf, urdf_axis_inertia
from pybullet_sim.urdf import tensors_are_valid


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


@pytest.mark.parametrize("m,L,arm_m", [(0.0, 0.0, 0.0), (1.0, 0.10, 0.0), (2.0, 0.15, 0.3)])
def test_urdf_inertia_tensors_are_physically_valid(m, L, arm_m):
    cfg = load_base_config()
    urdf = joint_urdf(cfg, JointParams(payload_mass_kg=m, arm_length_m=L, arm_mass_kg=arm_m, gravity_on=True))
    assert tensors_are_valid(urdf)
    assert "ixx=\"1e-09\"" not in urdf.split("name=\"hub\"")[1].split("</link>")[0]               # the hub is not the degenerate tiny/huge/tiny tensor


def test_hanging_period_includes_gravity():
    from pybullet_sim.sim import hanging_period_s
    assert hanging_period_s(0.1, 0.2, g=9.81) == pytest.approx(2 * math.pi * math.sqrt(0.1 / (9.81 * 0.2)))
    assert hanging_period_s(0.1, 0.2, g=9.81) < hanging_period_s(0.1, 0.2, g=1.62)             # weaker gravity, slower swing


def test_pybullet_loads_urdf_without_inertia_warning(capfd):
    pytest.importorskip("pybullet")
    from pybullet_sim.sim import PyBulletJointSim

    cfg = load_base_config()
    sim = PyBulletJointSim(cfg, JointParams(payload_mass_kg=1.0, arm_length_m=0.1, arm_mass_kg=0.1, gravity_on=True))
    sim.close()
    cap = capfd.readouterr()
    assert "Bad inertia" not in cap.out + cap.err, cap.out + cap.err


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
