// Physics core of the servo digital twin (motor + gearbox + joint + encoder + PID), plain JavaScript.
// Mirrors models/*.py and controllers/pid.py. All constants come from config.generated.js
// (generated from config/motor_parameters.yaml); nothing is hard-coded here.
//
// Used two ways: inlined into servo_pid_visualizer_360.html (between the `<<BEGIN physics.js>>` markers,
// kept in sync by tools/generate_js_config.py) and loaded by Node (tools/run_scenarios.js) for the
// cross-implementation tests. Every function takes its config explicitly; there are no globals.
//
// Conventions (same as models/joint.py): 0 deg = arm hanging; torques on the output shaft are positive when
// they oppose positive rotation; payload is a point mass at the arm tip; the optional arm is a thin rod.
// Not modelled here: encoder noise (the Python twin and the trainer can add it; the browser cannot).

const G_ACC = 9.81;

function makeCFG(gen, scenario) {
  const name = scenario || gen.activeScenario;
  const motor = gen.scenarios[name];
  if (!motor) throw new Error('unknown or non-simulatable parameter set: ' + name);
  // Explicit RK4 is unstable once dt exceeds ~2.8*L/R. The Python twin sub-steps; this port does not (yet), so refuse.
  if (motor.L > 0) throw new Error('physics.js does not sub-step the electrical dynamics, so it refuses L > 0 (L = ' + motor.L + ' H); use the Python twin');
  return {
    scenario: name,
    V_rated: gen.supply.V_rated,
    gearboxRatio: gen.gearbox.ratio, gearboxEff: gen.gearbox.efficiency,
    encoderCPR: gen.encoder.cpr,
    motor: Object.assign({}, motor),
    dt: gen.simulation.dt, duration: gen.simulation.durationS, thetaRefDeg: gen.simulation.thetaRefDefaultDeg,
    derivFilterTau: gen.controller.derivativeFilterTauS,
    currentLimitA: gen.driver.currentLimitA,
    joint: Object.assign({}, gen.joint),
    feasMarginal: gen.feasibility.marginalMargin,
  };
}

function nSteps(cfg) { return Math.round(cfg.duration / cfg.dt); }

function motorDerivatives(state, V, tauLoad, p) {
  let [i, w] = state;
  let didt;
  if (p.L > 0) { didt = (V - p.R * i - p.Ke * w) / p.L; }
  else { i = (V - p.Ke * w) / p.R; didt = 0.0; }
  const dwdt = (p.Kt * i - p.Bm * w - tauLoad) / p.Jm;
  return [didt, dwdt, w];
}
function motorCurrent(state, V, p) { return p.L > 0 ? state[0] : (V - p.Ke * state[1]) / p.R; }
function motorStepRK4(state, dt, V, tauLoad, p) {
  const k1 = motorDerivatives(state, V, tauLoad, p);
  const s2 = state.map((s, idx) => s + 0.5 * dt * k1[idx]);
  const k2 = motorDerivatives(s2, V, tauLoad, p);
  const s3 = state.map((s, idx) => s + 0.5 * dt * k2[idx]);
  const k3 = motorDerivatives(s3, V, tauLoad, p);
  const s4 = state.map((s, idx) => s + dt * k3[idx]);
  const k4 = motorDerivatives(s4, V, tauLoad, p);
  return state.map((s, idx) => s + (dt / 6) * (k1[idx] + 2 * k2[idx] + 2 * k3[idx] + k4[idx]));
}

function encoderRead(cfg, thTrue) {
  const radPerCount = 2 * Math.PI / cfg.encoderCPR;
  return Math.round(thTrue / radPerCount) * radPerCount;
}

class PID {
  constructor(Kp, Ki, Kd, dt, outMax, tauF) {
    this.Kp = Kp; this.Ki = Ki; this.Kd = Kd; this.dt = dt;
    this.outMin = -outMax; this.outMax = outMax; this.tauF = tauF;
    this.integral = 0; this.prevErr = 0; this.filtD = 0;
  }
  step(err) {
    const rawD = (err - this.prevErr) / this.dt;
    const alpha = this.dt / (this.tauF + this.dt);
    this.filtD += alpha * (rawD - this.filtD);
    let tentInt = this.integral + err * this.dt;
    const uUnsat = this.Kp * err + this.Ki * tentInt + this.Kd * this.filtD;
    let u;
    if (uUnsat > this.outMax) { u = this.outMax; if (err > 0) tentInt = this.integral; }
    else if (uUnsat < this.outMin) { u = this.outMin; if (err < 0) tentInt = this.integral; }
    else { u = uUnsat; }
    this.integral = tentInt; this.prevErr = err;
    return u;
  }
}

// pl: {mass, len, gravity, vPct, armMass?, Bj?, tauC?, currentLimitA?}  (omitted fields fall back to cfg.joint / cfg)
function jointParams(cfg, pl) {
  const j = cfg.joint;
  const armMass = pl.armMass !== undefined ? pl.armMass : j.armMassKg;
  return {
    mass: pl.mass, len: pl.len, gravity: !!pl.gravity, armMass: armMass,
    Bj: pl.Bj !== undefined ? pl.Bj : j.BJointNmsPerRad,
    tauC: pl.tauC !== undefined ? pl.tauC : j.tauCoulombNm,
    eps: j.omegaEpsRadS,
  };
}
function jointOutputInertia(jp) { return jp.mass * jp.len * jp.len + jp.armMass * jp.len * jp.len / 3; }
function jointGravityMoment(jp) { return jp.gravity ? jp.mass * jp.len + jp.armMass * (jp.len / 2) : 0; }
function jointTorque(jp, thetaOut, omegaOut) {
  let tau = jointGravityMoment(jp) * G_ACC * Math.sin(thetaOut) + jp.Bj * omegaOut;
  if (jp.tauC !== 0) tau += jp.tauC * Math.tanh(omegaOut / jp.eps);
  return tau;
}

// Closed-loop step response. Returns arrays (angles in degrees, V and i in SI). Uses cfg.thetaRefDeg as the target.
function runTwin(cfg, Kp, Ki, Kd, pl) {
  pl = pl || { mass: 0, len: 0.028, gravity: false, vPct: 100 };
  const N = cfg.gearboxRatio, eff = cfg.gearboxEff, dt = cfg.dt;
  const vmax = cfg.V_rated * pl.vPct / 100;                       // motor speed limit = voltage cap
  const iLim = pl.currentLimitA !== undefined ? pl.currentLimitA : cfg.currentLimitA;   // null = no driver limit
  const pid = new PID(Kp, Ki, Kd, dt, vmax, cfg.derivFilterTau);
  const jp = jointParams(cfg, pl);
  const mp = Object.assign({}, cfg.motor, { Jm: cfg.motor.Jm + jointOutputInertia(jp) / (N * N) });
  const thetaRef = cfg.thetaRefDeg * Math.PI / 180;
  let motorState = [0, 0, 0];
  const log = { t: [], theta: [], err: [], V: [], Vcmd: [], i: [] };
  for (let n = 0; n < nSteps(cfg); n++) {
    const omegaM = motorState[1];
    const thTrue = motorState[2] / N;
    const thMeas = encoderRead(cfg, thTrue);
    const err = thetaRef - thMeas;
    const Vcmd = pid.step(err);
    let V = Vcmd;
    if (iLim !== null && iLim !== undefined) {
      const lo = mp.Ke * omegaM - mp.R * iLim, hi = mp.Ke * omegaM + mp.R * iLim;
      V = Math.min(Math.max(Vcmd, lo), hi);
    }
    const tauOut = jointTorque(jp, thTrue, omegaM / N);
    const iMotor = motorCurrent(motorState, V, mp);                // current at the instant V is applied
    motorState = motorStepRK4(motorState, dt, V, tauOut / (N * eff), mp);
    log.t.push((n + 1) * dt);
    log.theta.push(motorState[2] / N * 180 / Math.PI);
    log.err.push(err * 180 / Math.PI);
    log.V.push(V); log.Vcmd.push(Vcmd); log.i.push(iMotor);
  }
  return log;
}

// ---------- metrics (same definitions as simulation/metrics.py) ----------
function riseTime(t, y, ref, lo = 0.1, hi = 0.9) {
  if (ref === 0) return NaN;
  const loT = lo * ref, hiT = hi * ref;
  const iLo = y.findIndex(v => v >= loT), iHi = y.findIndex(v => v >= hiT);
  if (iLo < 0 || iHi < 0) return NaN;
  return t[iHi] - t[iLo];
}
function overshootPct(y, ref) {
  if (ref === 0) return NaN;
  let peak = -Infinity; for (const v of y) if (v > peak) peak = v;
  return Math.max(0, 100 * (peak - ref) / ref);
}
function settlingTime(t, y, ref, tol = 0.02) {
  if (ref === 0) return NaN;
  const band = tol * Math.abs(ref);
  let lastOut = -1;
  for (let i = 0; i < y.length; i++) if (Math.abs(y[i] - ref) > band) lastOut = i;
  if (lastOut === -1) return 0;
  if (lastOut === t.length - 1) return NaN;
  return t[lastOut + 1];
}
function steadyStateError(y, ref) { return y[y.length - 1] - ref; }

// ---------- torque feasibility (mirror of models/feasibility.py) ----------
// margin = available output stall torque / peak gravity holding torque on the path from 0 deg to the target.
// Upper bound: back-EMF lowers the torque available while the joint moves.
function feasibilityJS(cfg, mass, len, thetaDeg, gravity, vPct, armMass, currentLimitA) {
  const m = cfg.motor;
  armMass = armMass || 0;
  const iLim = currentLimitA !== undefined ? currentLimitA : cfg.currentLimitA;
  let iStall = cfg.V_rated * vPct / 100 / m.R;
  if (iLim !== null && iLim !== undefined) iStall = Math.min(iStall, iLim);
  const tauAvail = m.Kt * iStall * cfg.gearboxRatio * cfg.gearboxEff;
  const t = Math.abs(thetaDeg), peakSin = t >= 90 ? 1 : Math.sin(t * Math.PI / 180);
  const k = gravity ? (mass * len + armMass * len / 2) * G_ACC : 0;
  let holdT = Math.abs(k * Math.sin(thetaDeg * Math.PI / 180)); if (holdT < 1e-9) holdT = 0;
  const holdP = Math.abs(k) * peakSin;
  const marginT = holdT > 0 ? tauAvail / holdT : Infinity, marginP = holdP > 0 ? tauAvail / holdP : Infinity;
  const status = marginP < 1 ? 'infeasible' : (marginP < cfg.feasMarginal ? 'marginal' : 'ok');
  return { tau_avail: tauAvail, tau_hold_target: holdT, tau_hold_peak: holdP, margin_target: marginT, margin_path: marginP, status };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { makeCFG, nSteps, runTwin, riseTime, overshootPct, settlingTime, steadyStateError, feasibilityJS };
}
