"""Phase 6 (minimal, per current project scope): bare output shaft, no arm.

No arm/payload mass, length, or inertia is modeled -- that data has not been
provided yet. This build's joint carries only the motor+gearbox's own
reflected inertia/friction; external torque defaults to zero. This class
exists so the digital twin's data flow already has the right seam to add
joint-side inertia, friction, and disturbance torque later without a
redesign, once real arm/payload specs are available.
"""

from typing import Callable, Optional


class Joint:
    def __init__(self, external_torque_func: Optional[Callable[[float], float]] = None):
        self.external_torque_func = external_torque_func or (lambda t: 0.0)  # ASSUMED zero, this build

    def external_torque(self, t: float) -> float:
        return self.external_torque_func(t)
