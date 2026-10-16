"""Output-side disturbance torque generators (callables t -> N*m) for Joint(disturbance=...).

Sign: positive torque opposes positive rotation (a load). All amplitudes in N*m, times in s.
"""

import math


def step(t0: float, amplitude: float):
    """0 before t0, ``amplitude`` from t0 on."""
    return lambda t: amplitude if t >= t0 else 0.0


def ramp(t0: float, slope: float):
    """0 before t0, then slope*(t - t0) [N*m/s]."""
    return lambda t: slope * (t - t0) if t >= t0 else 0.0


def pulse(t0: float, duration: float, amplitude: float):
    """``amplitude`` on [t0, t0 + duration), otherwise 0."""
    return lambda t: amplitude if t0 <= t < t0 + duration else 0.0


def sinusoid(amplitude: float, freq_hz: float, phase: float = 0.0):
    """amplitude * sin(2*pi*f*t + phase)."""
    return lambda t: amplitude * math.sin(2.0 * math.pi * freq_hz * t + phase)


def combine(*funcs):
    """Sum of several disturbances."""
    return lambda t: sum(f(t) for f in funcs)
