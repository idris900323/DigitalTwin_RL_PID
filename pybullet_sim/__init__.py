"""PyBullet interface for the joint (G5, optional, PRE-VALIDATION). The URDF generator is pure Python and tested; the simulation
wrapper needs ``pybullet`` and is UNTESTED on this machine (no wheel for Python 3.12 on Windows, no compiler; see
docs/pybullet_install_windows.md). The folder is not named ``pybullet`` so it cannot shadow the real package."""

from .urdf import joint_urdf, urdf_axis_inertia  # noqa: F401
