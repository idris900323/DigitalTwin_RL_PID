"""Export a recommendation as ready-to-use controller code (Python, C, Arduino-style sketch).

The exported controller implements EXACTLY the PID of ``controllers/pid.py`` (same derivative filter, conditional-integration
anti-windup and saturation), so what was simulated is what runs. Every file starts with a header carrying the tier, the date,
the motor profile hash and the words "re-tune after validation". ``tests/test_tuning.py`` runs the exported Python in the twin
and requires the response to be identical to the simulated one.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from tuning.recommend import Recommendation


def _header(rec: Recommendation, comment: str, date: Optional[str]) -> str:
    kp, ki, kd = rec.gains
    when = date or _dt.date.today().isoformat()
    lines = [rec.tier.label, f"motor {rec.motor_id} (profile hash {rec.profile_hash}), load {rec.load_id}, generated {when}",
             f"gains Kp {kp:.9g}  Ki {ki:.9g}  Kd {kd:.9g}  (method: {rec.winner}); PRELIMINARY - RE-TUNE AFTER VALIDATION",
             "Not validated on hardware: check the sign conventions, units and limits against your rig before enabling the motor."]
    return "\n".join(f"{comment} {x}" for x in lines)


def to_python(rec: Recommendation, date: Optional[str] = None) -> str:
    kp, ki, kd = rec.gains
    dt = rec.cfg["simulation"]["control_loop_dt_s"]
    tau = rec.cfg.get("controller", {}).get("derivative_filter_tau_s", 0.01)
    vmax = rec.cfg["supply"]["V_rated"]
    return f'''{_header(rec, "#", date)}
KP, KI, KD = {kp!r}, {ki!r}, {kd!r}
DT = {dt!r}            # control period [s]
TAU_F = {tau!r}        # derivative filter time constant [s]
V_MAX = {vmax!r}       # output saturation [V]


class Controller:
    """Fixed-gain PID with filtered derivative and conditional-integration anti-windup (same as controllers/pid.py)."""

    def __init__(self, kp=KP, ki=KI, kd=KD, dt=DT, tau_f=TAU_F, v_max=V_MAX):
        self.kp, self.ki, self.kd, self.dt, self.tau_f = kp, ki, kd, dt, tau_f
        self.v_min, self.v_max = -v_max, v_max
        self.reset()

    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0
        self.filtered_derivative = 0.0

    def step(self, error):
        raw = (error - self.prev_error) / self.dt
        alpha = self.dt / (self.tau_f + self.dt)
        self.filtered_derivative += alpha * (raw - self.filtered_derivative)
        tentative = self.integral + error * self.dt
        u_unsat = self.kp * error + self.ki * tentative + self.kd * self.filtered_derivative
        if u_unsat > self.v_max:
            u = self.v_max
            if error > 0.0:
                tentative = self.integral
        elif u_unsat < self.v_min:
            u = self.v_min
            if error < 0.0:
                tentative = self.integral
        else:
            u = u_unsat
        self.integral = tentative
        self.prev_error = error
        return u
'''


def to_c(rec: Recommendation, date: Optional[str] = None) -> str:
    kp, ki, kd = rec.gains
    dt = rec.cfg["simulation"]["control_loop_dt_s"]
    tau = rec.cfg.get("controller", {}).get("derivative_filter_tau_s", 0.01)
    vmax = rec.cfg["supply"]["V_rated"]
    return f'''{_header(rec, "//", date)}
// Portable C (C99). Uses double; on a microcontroller without an FPU use float, or scale to fixed point:
// error in encoder counts * (2*pi/COUNTS_PER_REV) -> radians; keep Ki*dt and Kd/dt as precomputed Q16.16 constants and
// saturate the integral accumulator explicitly. Sample at exactly DT_S (hardware timer), read the encoder before computing.
#ifndef DTRL_PID_H
#define DTRL_PID_H

#define KP      {kp!r}
#define KI      {ki!r}
#define KD      {kd!r}
#define DT_S    {dt!r}    /* control period [s] */
#define TAU_F_S {tau!r}   /* derivative filter time constant [s] */
#define V_MAX   {vmax!r}  /* output saturation [V] */

typedef struct {{ double integral, prev_error, filtered_derivative; }} pid_state_t;

static inline void pid_reset(pid_state_t *s) {{ s->integral = 0.0; s->prev_error = 0.0; s->filtered_derivative = 0.0; }}

/* error in radians (target - measured output angle); returns the voltage command [V]. */
static inline double pid_step(pid_state_t *s, double error) {{
    const double alpha = DT_S / (TAU_F_S + DT_S);
    const double raw = (error - s->prev_error) / DT_S;
    s->filtered_derivative += alpha * (raw - s->filtered_derivative);
    double tentative = s->integral + error * DT_S;
    const double u_unsat = KP * error + KI * tentative + KD * s->filtered_derivative;
    double u;
    if (u_unsat > V_MAX)      {{ u = V_MAX;  if (error > 0.0) tentative = s->integral; }}
    else if (u_unsat < -V_MAX) {{ u = -V_MAX; if (error < 0.0) tentative = s->integral; }}
    else                       {{ u = u_unsat; }}
    s->integral = tentative;
    s->prev_error = error;
    return u;
}}

#endif
'''


def to_arduino(rec: Recommendation, date: Optional[str] = None) -> str:
    cpr = rec.cfg["encoder"]["output_cpr"]
    vmax = rec.cfg["supply"]["V_rated"]
    return f'''{_header(rec, "//", date)}
// Arduino-style sketch skeleton. The encoder, driver pins and PWM mapping are placeholders you must adapt:
// ENABLE THE MOTOR ONLY with a current limit, hard stops and an emergency stop in place (docs/validation_plan.md section 3).
#include "dtrl_pid.h"   // the C header generated alongside this sketch

const double COUNTS_PER_REV = {cpr};        // OUTPUT-shaft counts per revolution
const double SUPPLY_V = {vmax!r};
volatile long encoderCounts = 0;           // update from your quadrature interrupt
pid_state_t pid;
double targetDeg = 90.0;
unsigned long nextTick;

void setup() {{
  pid_reset(&pid);
  // pinMode(...), attachInterrupt(...), PWM setup, motor driver ENABLE stays LOW until a handshake
  nextTick = micros();
}}

void loop() {{
  if ((long)(micros() - nextTick) >= 0) {{
    nextTick += (unsigned long)(DT_S * 1e6);
    long counts = encoderCounts;                                  // read first, then compute
    double angle = counts * 2.0 * 3.14159265358979 / COUNTS_PER_REV;
    double error = targetDeg * 3.14159265358979 / 180.0 - angle;
    double v = pid_step(&pid, error);
    double duty = v / SUPPLY_V;                                   // -1 .. 1 ; map to PWM + direction pin for your H-bridge
    // writeMotor(duty);
  }}
}}
'''
