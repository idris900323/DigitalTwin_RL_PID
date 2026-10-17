"""Linearised plant, PID loop, stability margins and noise amplification.

Plant (armature inductance neglected, motor-side inertia J = Jm + J_out/N^2):

    theta_out(s) / V(s) = (b / N) / (s^2 + a s + c),   b = Kt/(R J),  a = (Kt Ke/R + Bm)/J,  c = k_g/(N^2 eta J)

``k_g = (m L + m_arm L_cg) g cos(theta_target)`` is the gravity stiffness linearised at the target (it can be negative above
90 deg: the arm then wants to fall away). Joint viscous friction adds B_j/(N^2 eta J) to ``a``.

Controller: C(s) = Kp + Ki/s + Kd s/(tau_f s + 1). The digital loop adds a delay of (1.5 + d) samples: one sample for the
state-to-command latency, half a sample for the zero-order hold, d extra samples of command latency.

All results are PRELIMINARY (datasheet-derived plant).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

import numpy as np

G = 9.81


@dataclass
class LinearPlant:
    b: float
    a: float
    c: float
    N: float
    tau_f: float
    dt: float
    delay_steps: float
    V_max: float
    lsb_rad: float

    @classmethod
    def from_cfg(cls, cfg: dict, *, payload_kg: float = 0.0, arm_length_m: float = 0.0, arm_mass_kg: float = 0.0, gravity: bool = False,
                 target_deg: float = 90.0, viscous: float = 0.0, scenario: str | None = None, overrides: Dict[str, float] | None = None) -> "LinearPlant":
        sc = scenario or cfg["simulation"]["active_electrical_scenario"]
        d, e = cfg["base_motor"]["derived"][sc], cfg["base_motor"]["estimated"]
        o = overrides or {}
        R, Kt, Ke = o.get("R", d["R_ohm"]), o.get("Kt", d["Kt_Nm_per_A"]), o.get("Ke", d["Ke_V_s_per_rad"])
        Jm, Bm = o.get("Jm", e["Jm_kgm2"]), o.get("Bm", d.get("Bm_Nms_per_rad", e["Bm_Nms_per_rad"]))
        eta = o.get("eta", d.get("gearbox_efficiency", cfg["gearbox"]["efficiency"]))
        N = cfg["gearbox"]["ratio"]
        J_out = payload_kg * arm_length_m ** 2 + arm_mass_kg * arm_length_m ** 2 / 3.0
        J = Jm + J_out / N ** 2
        moment = (payload_kg * arm_length_m + arm_mass_kg * arm_length_m / 2.0) if gravity else 0.0
        k_g = moment * G * math.cos(math.radians(target_deg))
        a = (Kt * Ke / R + Bm) / J + viscous / (N ** 2 * eta * J)
        return cls(b=Kt / (R * J), a=a, c=k_g / (N ** 2 * eta * J), N=N, tau_f=cfg.get("controller", {}).get("derivative_filter_tau_s", 0.01),
                   dt=cfg["simulation"]["control_loop_dt_s"], delay_steps=1.5 + cfg.get("driver", {}).get("delay_steps", 0),
                   V_max=cfg["supply"]["V_rated"], lsb_rad=2 * math.pi / cfg["encoder"]["output_cpr"])

    @property
    def delay_s(self) -> float:
        return self.delay_steps * self.dt

    def frequency_response(self, kp, ki, kd, w):
        s = 1j * w
        P = (self.b / self.N) / (s ** 2 + self.a * s + self.c)
        C = kp + ki / s + kd * s / (self.tau_f * s + 1.0)
        return C * P * np.exp(-s * self.delay_s), C, P

    def margins(self, kp, ki, kd, n: int = 40000) -> Dict[str, float]:
        """Gain margin [dB], phase margin [deg], delay margin [s], crossover [rad/s] and closed-loop stability of the loop."""
        w = np.logspace(-1.5, math.log10(0.8 * math.pi / self.dt), n)
        L, _, _ = self.frequency_response(kp, ki, kd, w)
        mag, ph = np.abs(L), np.unwrap(np.angle(L))
        out = {"gain_margin_db": math.inf, "phase_margin_deg": math.inf, "delay_margin_s": math.inf, "crossover_rad_s": float("nan")}
        cross = np.where((mag[:-1] >= 1.0) & (mag[1:] < 1.0))[0]
        if len(cross):
            i = cross[-1]                                               # highest-frequency gain crossover
            t = (1.0 - mag[i]) / (mag[i + 1] - mag[i])
            wc, phc = w[i] + t * (w[i + 1] - w[i]), ph[i] + t * (ph[i + 1] - ph[i])
            pm = 180.0 + math.degrees(phc)
            pm = (pm + 180.0) % 360.0 - 180.0
            out.update(phase_margin_deg=pm, crossover_rad_s=float(wc), delay_margin_s=(math.radians(pm) / wc) if pm > 0 else 0.0)
        pc = np.where((ph[:-1] > -math.pi) & (ph[1:] <= -math.pi))[0]
        pc = np.concatenate([pc, np.where((ph[:-1] > -3 * math.pi) & (ph[1:] <= -3 * math.pi))[0]]) if len(pc) == 0 else pc
        gms = [abs(20.0 * math.log10(max(mag[i], 1e-12))) for i in pc]
        if gms:
            out["gain_margin_db"] = min(gms)
        out["stable"] = self.is_stable(kp, ki, kd)
        return out

    def is_stable(self, kp, ki, kd) -> bool:
        """Closed-loop poles of the linear loop with a first-order Pade approximation of the delay."""
        T = self.delay_s
        # open loop numerator/denominator polynomials in s (highest power first)
        pn = np.array([self.b / self.N])
        pd = np.array([1.0, self.a, self.c])
        if ki == 0.0:                                     # no integrator: cancel the common factor s explicitly
            cn = np.array([kp * self.tau_f + kd, kp])
            cd = np.array([self.tau_f, 1.0])
        else:
            cn = np.polyadd(np.polymul([kp, ki], [self.tau_f, 1.0]), np.polymul([kd, 0.0], [1.0, 0.0]))     # (Kp s + Ki)(tau s+1) + Kd s^2
            cd = np.polymul([1.0, 0.0], [self.tau_f, 1.0])                                                   # s (tau s + 1)
        dn, dd = np.array([-T / 2.0, 1.0]), np.array([T / 2.0, 1.0])                                     # Pade(1)
        num = np.polymul(np.polymul(pn, cn), dn)
        den = np.polymul(np.polymul(pd, cd), dd)
        poly = np.polyadd(den, num)
        return bool(np.all(np.roots(poly).real < -1e-9))


def noise_voltage_rms(kp: float, kd: float, plant: LinearPlant, counts_rms: float = 0.29) -> float:
    """RMS voltage noise from encoder quantisation (white, sigma = counts_rms LSB) through P and the filtered D term.

    The PID output for white error noise has variance sigma^2 * sum(g_k^2), g = impulse response of
    Kp + Kd * H(z), H(z) = alpha (1 - z^-1) / (dt (1 - (1 - alpha) z^-1)) (the filtered derivative used by controllers/pid.py)."""
    sigma = counts_rms * plant.lsb_rad
    alpha = plant.dt / (plant.tau_f + plant.dt)
    n = 4000
    h = np.zeros(n)
    prev = 0.0
    for k in range(n):                                           # impulse response of the filtered derivative
        raw = ((1.0 if k == 0 else 0.0) - (1.0 if k == 1 else 0.0)) / plant.dt
        prev = prev + alpha * (raw - prev)
        h[k] = prev
    g = kd * h
    g[0] += kp
    return float(sigma * math.sqrt(np.sum(g ** 2)))
