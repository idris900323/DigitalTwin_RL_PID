"""SI unit conversion helpers. All internal simulation state is SI; datasheet
values arrive in RPM / kg-cm / g-cm and must pass through these explicitly."""

import math

RPM_TO_RAD_S = 2.0 * math.pi / 60.0
KGCM_TO_NM = 0.0980665
GCM_TO_NM = KGCM_TO_NM * 1.0e-3


def rpm_to_rad_s(rpm: float) -> float:
    """Convert RPM to rad/s."""
    return rpm * RPM_TO_RAD_S


def rad_s_to_rpm(rad_s: float) -> float:
    """Convert rad/s to RPM."""
    return rad_s / RPM_TO_RAD_S


def kgcm_to_Nm(kgcm: float) -> float:
    """Convert kg*cm to N*m."""
    return kgcm * KGCM_TO_NM


def gcm_to_Nm(gcm: float) -> float:
    """Convert g*cm to N*m."""
    return gcm * GCM_TO_NM
