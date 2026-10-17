"""Optional PyBullet wrapper: the motor stays in the Python twin and only the output torque is applied to the PyBullet joint.

UNTESTED on this machine: ``pybullet`` has no wheel for Python 3.12 on Windows and there is no C++ compiler here (see
docs/pybullet_install_windows.md). The interface is here so the route is clear once it is installed; the URDF generator in
``urdf.py`` is tested without PyBullet. PRE-VALIDATION: no result from this module is validated.
"""

from __future__ import annotations

import math
import tempfile

from .urdf import joint_urdf


class PyBulletJointSim:
    """Torque-driven revolute joint in PyBullet with the geometry/inertia from the YAML and the joint parameters."""

    def __init__(self, cfg: dict, params=None, dt: float = 0.001, gravity: bool = True):
        try:
            import pybullet as pb
        except ImportError as e:          # pragma: no cover - depends on the environment
            raise ImportError("pybullet is not installed; see docs/pybullet_install_windows.md") from e
        self.pb = pb
        self.cid = pb.connect(pb.DIRECT)
        pb.setGravity(0, 0, -9.81 if gravity else 0.0, physicsClientId=self.cid)
        pb.setTimeStep(dt, physicsClientId=self.cid)
        with tempfile.NamedTemporaryFile("w", suffix=".urdf", delete=False) as fh:
            fh.write(joint_urdf(cfg, params))
        self.body = pb.loadURDF(fh.name, useFixedBase=True, physicsClientId=self.cid)
        pb.setJointMotorControl2(self.body, 0, pb.VELOCITY_CONTROL, force=0.0, physicsClientId=self.cid)   # free joint: torque mode
        self.dt = dt

    def step(self, torque_out_nm: float):
        """Apply the output-shaft torque [N*m], advance one step; returns (theta_rad, omega_rad_s)."""
        pb = self.pb
        pb.setJointMotorControl2(self.body, 0, pb.TORQUE_CONTROL, force=float(torque_out_nm), physicsClientId=self.cid)
        pb.stepSimulation(physicsClientId=self.cid)
        th, om, *_ = pb.getJointState(self.body, 0, physicsClientId=self.cid)
        return th, om

    def close(self):
        self.pb.disconnect(physicsClientId=self.cid)


def hanging_period_s(joint_inertia: float, gravity_moment: float) -> float:
    """Small-oscillation period of the free (undamped) pendulum, the analytic check for a PyBullet gravity test."""
    return 2.0 * math.pi * math.sqrt(joint_inertia / gravity_moment)
