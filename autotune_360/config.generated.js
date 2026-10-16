// GENERATED - do not edit; run `python tools/generate_js_config.py`
// source: config/motor_parameters.yaml
const DTRL_CONFIG = {
  "activeScenario": "method_c",
  "scenarios": {
    "method_a": {
      "R": 1.6,
      "L": 0.0,
      "Kt": 0.001974,
      "Ke": 0.001974,
      "Jm": 5e-07,
      "Bm": 1e-06
    },
    "method_c": {
      "R": 1.6,
      "L": 0.0,
      "Kt": 0.001974,
      "Ke": 0.006366,
      "Jm": 5e-07,
      "Bm": 1e-06
    },
    "method_d": {
      "R": 1.6,
      "L": 0.0,
      "Kt": 0.005687137,
      "Ke": 0.005687137,
      "Jm": 5e-07,
      "Bm": 2.413696e-06,
      "eff": 0.34717
    },
    "method_d2": {
      "R": 1.6,
      "L": 0.0,
      "Kt": 0.005687137,
      "Ke": 0.005687137,
      "Jm": 5e-07,
      "Bm": 2.413696e-06,
      "eff": 0.8
    },
    "method_d3": {
      "R": 1.6,
      "L": 0.0,
      "Kt": 0.005687137,
      "Ke": 0.005687137,
      "Jm": 5e-07,
      "Bm": 2.413696e-06,
      "eff": 0.319325
    }
  },
  "supply": {
    "V_rated": 12.0
  },
  "gearbox": {
    "ratio": 180.0,
    "efficiency": 0.8
  },
  "encoder": {
    "cpr": 9360,
    "noiseCountsRms": 0.0
  },
  "simulation": {
    "dt": 0.001,
    "durationS": 2.0,
    "thetaRefDefaultDeg": 90.0
  },
  "controller": {
    "derivativeFilterTauS": 0.01
  },
  "driver": {
    "currentLimitA": null
  },
  "joint": {
    "payloadMassKg": 0.0,
    "armLengthM": 0.0,
    "armMassKg": 0.0,
    "gravityOn": false,
    "BJointNmsPerRad": 0.0,
    "tauCoulombNm": 0.0,
    "omegaEpsRadS": 0.01
  },
  "feasibility": {
    "marginalMargin": 1.2
  },
  "pidDefaults": {
    "Kp": 15.0,
    "Ki": 0.0,
    "Kd": 0.3
  },
  "pidPresets": {
    "legacy_default": {
      "Kp": 5.0,
      "Ki": 20.0,
      "Kd": 0.05
    },
    "sluggish": {
      "Kp": 1.5,
      "Ki": 0.0,
      "Kd": 0.0
    },
    "oscillatory": {
      "Kp": 45.0,
      "Ki": 0.0,
      "Kd": 0.0
    },
    "tuned": {
      "Kp": 15.0,
      "Ki": 0.0,
      "Kd": 0.3
    }
  },
  "provenance": {
    "supply.V_rated": "DATASHEET",
    "gearbox.ratio": "DATASHEET",
    "gearbox.efficiency": "ESTIMATED",
    "encoder.hall_sensors": "DATASHEET",
    "encoder.quadrature_multiplier": "DATASHEET",
    "encoder.base_cpr": "DATASHEET",
    "encoder.output_cpr": "DATASHEET",
    "encoder.noise_counts_rms": "ASSUMED",
    "base_motor.no_load_speed_rpm": "DATASHEET",
    "base_motor.no_load_current_A": "DATASHEET",
    "base_motor.rated_torque_gcm": "DATASHEET",
    "base_motor.load_current_max_A": "DATASHEET",
    "base_motor.derived.method_a.R_ohm": "CALCULATED",
    "base_motor.derived.method_a.Kt_Nm_per_A": "CALCULATED",
    "base_motor.derived.method_a.Ke_V_s_per_rad": "CALCULATED",
    "base_motor.derived.method_b.Ke_V_s_per_rad": "CALCULATED",
    "base_motor.estimated.L_H": "ASSUMED",
    "base_motor.estimated.Jm_kgm2": "ESTIMATED",
    "base_motor.estimated.Bm_Nms_per_rad": "ESTIMATED",
    "output.rated_speed_rpm": "DATASHEET",
    "output.stall_torque_kgcm": "DATASHEET",
    "output.rated_torque_kgcm": "DATASHEET",
    "mass_g": "DATASHEET",
    "mechanical_dims_mm": "DATASHEET",
    "simulation.control_loop_dt_s": "ASSUMED",
    "simulation.theta_ref_default_deg": "ASSUMED",
    "simulation.run_duration_s": "ASSUMED",
    "controller.derivative_filter_tau_s": "ASSUMED",
    "driver.delay_steps": "ASSUMED",
    "joint.B_joint_Nms_per_rad": "UNKNOWN",
    "joint.tau_coulomb_Nm": "UNKNOWN",
    "feasibility.marginal_margin": "ASSUMED",
    "sensitivity_ranges.datasheet_rel": "DATASHEET",
    "sensitivity_ranges.calculated_rel": "CALCULATED",
    "sensitivity_ranges.assumed_rel": "ESTIMATED"
  },
  "yamlSha256": "f4a5b29d08147975fa36928983fa3b6086990c693ce182d1eb0bb2960ec76dc4"
};
if (typeof module !== 'undefined' && module.exports) module.exports = DTRL_CONFIG;
