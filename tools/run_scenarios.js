// Run the canonical scenarios (tests/scenarios.json) through the browser physics core in Node.
// Usage: node tools/run_scenarios.js tests/scenarios.json out.json
// Loads autotune_360/config.generated.js and autotune_360/physics.js, the same files that are inlined in the HTML page.
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname, '..', 'autotune_360');
const gen = require(path.join(dir, 'config.generated.js'));
const phys = require(path.join(dir, 'physics.js'));

const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
for (const sc of spec.scenarios) {
  if (sc.skip_js) continue;
  const cfg = phys.makeCFG(gen, sc.params);
  cfg.thetaRefDeg = sc.target_deg;
  if (sc.t_end) cfg.duration = sc.t_end;
  if (sc.dt) cfg.dt = sc.dt;
  const pl = {
    mass: sc.mass || 0, len: sc.length === undefined ? 0.028 : sc.length, gravity: !!sc.gravity,
    vPct: sc.v_pct === undefined ? 100 : sc.v_pct,
  };
  if (sc.current_limit_A !== undefined) pl.currentLimitA = sc.current_limit_A;
  const log = phys.runTwin(cfg, sc.kp, sc.ki, sc.kd, pl);
  out[sc.id] = { theta: log.theta, V: log.V, i: log.i, t: log.t };
}
fs.writeFileSync(process.argv[3], JSON.stringify(out));
