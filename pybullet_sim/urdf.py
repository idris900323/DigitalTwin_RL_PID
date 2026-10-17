"""URDF of the geared joint: rotor + gearbox as a hub with the reflected rotor inertia, a thin-rod arm and a payload point mass.

Convention matches ``models/joint.py``: rotation about +y, theta = 0 is hanging (arm along -z), so gravity torque is m*g*cg*sin(theta).
Electrics stay in the Python twin; PyBullet would only receive the output torque (see ``sim.py``).
"""

from __future__ import annotations

from typing import Dict

from models.joint import Joint, JointParams


def _inertia_xml(ixx: float, iyy: float, izz: float) -> str:
    return f'<inertia ixx="{ixx:.9g}" ixy="0" ixz="0" iyy="{iyy:.9g}" iyz="0" izz="{izz:.9g}"/>'


def joint_urdf(cfg: dict, params: JointParams | None = None, name: str = "dtrl_joint") -> str:
    """URDF string. The hub carries the rotor inertia reflected to the output shaft (Jm * N^2); the arm is a thin rod of length L
    (COM at L/2 or ``arm_cg_m``) and the payload a point mass at the tip."""
    p = params or JointParams.from_config(cfg)
    ratio = cfg["gearbox"]["ratio"]
    jm = cfg["base_motor"]["estimated"]["Jm_kgm2"]
    hub = jm * ratio ** 2
    cg = Joint(p).arm_cg
    L, ma, mp = p.arm_length_m, p.arm_mass_kg, p.payload_mass_kg
    tiny = 1e-9                                                          # URDF needs positive masses; this is negligible
    # hub: inertia-only link carrying the reflected rotor inertia about the shaft axis (y). A flat disc about y has ixx = izz = iyy/2, which
    # is the physically valid (triangle-inequality) tensor with that iyy; ixx = izz = tiny would make PyBullet warn "Bad inertia".
    h = max(hub, tiny)
    links = [f'  <link name="hub"><inertial><mass value="{tiny:.9g}"/><origin xyz="0 0 0"/>'
             f'{_inertia_xml(h / 2.0, h, h / 2.0)}</inertial></link>']
    arm_i = max(ma * L ** 2 / 3.0 - ma * cg ** 2, tiny)      # so that I_axis = m*L^2/3 as in models/joint.py
    links.append(f'  <link name="arm"><inertial><mass value="{max(ma, tiny):.9g}"/><origin xyz="0 0 {-cg:.9g}"/>'
                 f'{_inertia_xml(arm_i, arm_i, arm_i * 1e-3)}</inertial></link>')            # thin rod along z: ixx = iyy, izz ~ 0
    links.append(f'  <link name="payload"><inertial><mass value="{max(mp, tiny):.9g}"/><origin xyz="0 0 {-L:.9g}"/>'
                 f'{_inertia_xml(tiny, tiny, tiny)}</inertial></link>')                   # point mass: any valid tensor, here isotropic
    joints = ['  <joint name="shaft" type="revolute"><parent link="world"/><child link="hub"/><origin xyz="0 0 0"/><axis xyz="0 1 0"/>'
              '<limit lower="-12.566" upper="12.566" effort="1000" velocity="100"/></joint>',
              '  <joint name="arm_fixed" type="fixed"><parent link="hub"/><child link="arm"/></joint>',
              '  <joint name="payload_fixed" type="fixed"><parent link="arm"/><child link="payload"/></joint>']
    return "\n".join(['<?xml version="1.0"?>', f'<robot name="{name}">', '  <link name="world"/>', *links, *joints, '</robot>', ''])


def tensors_are_valid(urdf: str, rel_tol: float = 1e-9) -> bool:
    """Every link inertia tensor is positive and satisfies the triangle inequalities (ixx + iyy >= izz and permutations), the condition
    PyBullet checks when it warns "Bad inertia"."""
    import xml.etree.ElementTree as ET

    for link in ET.fromstring(urdf).findall("link"):
        inert = link.find("inertial")
        if inert is None:
            continue
        t = inert.find("inertia")
        ix, iy, iz = (float(t.get(k)) for k in ("ixx", "iyy", "izz"))
        if min(ix, iy, iz) <= 0 or ix + iy < iz * (1 - rel_tol) or ix + iz < iy * (1 - rel_tol) or iy + iz < ix * (1 - rel_tol):
            return False
    return True


def urdf_axis_inertia(urdf: str) -> Dict[str, float]:
    """Inertia about the shaft axis and gravity moment implied by a URDF made by ``joint_urdf`` (for tests and for cross-checking
    a PyBullet model against ``models/joint.py``)."""
    import xml.etree.ElementTree as ET

    root = ET.fromstring(urdf)
    J, moment = 0.0, 0.0
    for link in root.findall("link"):
        inert = link.find("inertial")
        if inert is None:
            continue
        m = float(inert.find("mass").get("value"))
        z = float(inert.find("origin").get("xyz").split()[2])
        J += float(inert.find("inertia").get("iyy")) + m * z * z
        moment += m * (-z)
    return {"J_axis": J, "gravity_moment": moment}
