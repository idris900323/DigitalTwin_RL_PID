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
  "yamlSha256": "6a6a32dcb3171237d9cfac46cbe33bad2c1025e64dcf682de803fb50e230c818",
  "defaultMotor": "rmcs_3070",
  "motors": {
    "rmcs_3070": {
      "name": "Johnson RMCS-3070",
      "synthetic": false,
      "scenario": "method_c",
      "supply": {
        "V_rated": 12.0
      },
      "gearbox": {
        "ratio": 180.0,
        "efficiency": 0.8
      },
      "encoder": {
        "cpr": 9360
      },
      "motor": {
        "R": 1.6,
        "L": 0.0,
        "Kt": 0.001974,
        "Ke": 0.006366,
        "Jm": 5e-07,
        "Bm": 1e-06
      },
      "params": {
        "R": {
          "value": 1.6,
          "lo": 0.4,
          "hi": 1.7600000000000002,
          "provenance": "assumed",
          "confidence": "low",
          "method": "V / current rating (not labelled stall: R is at most this)"
        },
        "K": {
          "value": 0.005687136633150393,
          "lo": 0.005232165702498362,
          "hi": 0.006142107563802425,
          "provenance": "calculated",
          "confidence": "medium",
          "method": "no-load balance V = R*I0 + K*w0 = 0.005687"
        },
        "eta": {
          "value": 0.8,
          "lo": 0.6000000000000001,
          "hi": 1.0,
          "provenance": "assumed",
          "confidence": "low",
          "method": "stated efficiency"
        },
        "Bm": {
          "value": 1e-06,
          "lo": 7e-07,
          "hi": 1.3e-06,
          "provenance": "assumed",
          "confidence": "medium",
          "method": "stated"
        },
        "tau_c": {
          "value": 0.0,
          "lo": 0.0,
          "hi": 0.002274854653260157,
          "provenance": "assumed",
          "confidence": "low",
          "method": "assumed zero; up to half of the no-load torque could be Coulomb"
        },
        "Jm": {
          "value": 5e-07,
          "lo": 1.6666666666666665e-07,
          "hi": 1.5e-06,
          "provenance": "assumed",
          "confidence": "low",
          "method": "stated rotor inertia"
        },
        "L": {
          "value": 0.0,
          "lo": 0.0,
          "hi": 0.005,
          "provenance": "assumed",
          "confidence": "low",
          "method": "neglected (0); plausible up to a few mH"
        }
      },
      "conflicts": [
        "meaning of the current rating",
        "output stall torque versus K, stall current and efficiency"
      ],
      "leastCertain": [
        "Jm",
        "R",
        "tau_c"
      ],
      "hasPolicy": true
    },
    "synthetic_brushed_48v": {
      "name": "Synthetic BR-48-30",
      "synthetic": true,
      "scenario": "derived",
      "supply": {
        "V_rated": 48.0
      },
      "gearbox": {
        "ratio": 30.0,
        "efficiency": 0.85
      },
      "encoder": {
        "cpr": 240000
      },
      "motor": {
        "R": 2.4,
        "L": 0.0,
        "Kt": 0.1494267515923567,
        "Ke": 0.1494267515923567,
        "Jm": 0.00013640822025700182,
        "Bm": 0.00021414661852407806
      },
      "params": {
        "R": {
          "value": 2.4,
          "lo": 2.16,
          "hi": 2.64,
          "provenance": "calculated",
          "confidence": "medium",
          "method": "V / stall current"
        },
        "K": {
          "value": 0.1494267515923567,
          "lo": 0.13747261146496817,
          "hi": 0.16138089171974523,
          "provenance": "calculated",
          "confidence": "medium",
          "method": "no-load balance V = R*I0 + K*w0 = 0.1494; stall torque / stall current = 0.1494"
        },
        "eta": {
          "value": 0.85,
          "lo": 0.765,
          "hi": 0.935,
          "provenance": "datasheet",
          "confidence": "medium",
          "method": "stated efficiency"
        },
        "Bm": {
          "value": 0.00021414661852407806,
          "lo": 2.141466185240781e-05,
          "hi": 0.00021414661852407806,
          "provenance": "calculated",
          "confidence": "low",
          "method": "K*I0/w0: all of the no-load current as viscous friction (upper bound)"
        },
        "tau_c": {
          "value": 0.0,
          "lo": 0.0,
          "hi": 0.033621019108280255,
          "provenance": "assumed",
          "confidence": "low",
          "method": "assumed zero; up to half of the no-load torque could be Coulomb"
        },
        "Jm": {
          "value": 0.00013640822025700182,
          "lo": 4.546940675233394e-05,
          "hi": 0.00040922466077100543,
          "provenance": "assumed",
          "confidence": "low",
          "method": "rotor-cylinder approximation from the motor mass"
        },
        "L": {
          "value": 0.0,
          "lo": 0.0,
          "hi": 0.005,
          "provenance": "assumed",
          "confidence": "low",
          "method": "neglected (0); plausible up to a few mH"
        }
      },
      "conflicts": [],
      "leastCertain": [
        "Jm",
        "Bm",
        "tau_c"
      ],
      "hasPolicy": false
    },
    "synthetic_coreless_12v": {
      "name": "Synthetic CL-12-100",
      "synthetic": true,
      "scenario": "derived",
      "supply": {
        "V_rated": 12.0
      },
      "gearbox": {
        "ratio": 100.0,
        "efficiency": 0.72
      },
      "encoder": {
        "cpr": 6400
      },
      "motor": {
        "R": 3.2,
        "L": 0.0,
        "Kt": 0.008467528941780716,
        "Ke": 0.008467528941780716,
        "Jm": 6.023297083246218e-07,
        "Bm": 7.406926278914674e-07
      },
      "params": {
        "R": {
          "value": 3.2,
          "lo": 3.04,
          "hi": 3.3600000000000003,
          "provenance": "datasheet",
          "confidence": "high",
          "method": "stated winding resistance"
        },
        "K": {
          "value": 0.008467528941780716,
          "lo": 0.007790126626438259,
          "hi": 0.009144931257123174,
          "provenance": "calculated",
          "confidence": "medium",
          "method": "no-load balance V = R*I0 + K*w0 = 0.008468; stall torque / stall current = 0.008474"
        },
        "eta": {
          "value": 0.72,
          "lo": 0.648,
          "hi": 0.792,
          "provenance": "datasheet",
          "confidence": "medium",
          "method": "stated efficiency"
        },
        "Bm": {
          "value": 7.406926278914674e-07,
          "lo": 7.406926278914675e-08,
          "hi": 7.406926278914674e-07,
          "provenance": "calculated",
          "confidence": "low",
          "method": "K*I0/w0: all of the no-load current as viscous friction (upper bound)"
        },
        "tau_c": {
          "value": 0.0,
          "lo": 0.0,
          "hi": 0.000508051736506843,
          "provenance": "assumed",
          "confidence": "low",
          "method": "assumed zero; up to half of the no-load torque could be Coulomb"
        },
        "Jm": {
          "value": 6.023297083246218e-07,
          "lo": 2.007765694415406e-07,
          "hi": 1.8069891249738653e-06,
          "provenance": "assumed",
          "confidence": "low",
          "method": "rotor-cylinder approximation from the motor mass"
        },
        "L": {
          "value": 0.0,
          "lo": 0.0,
          "hi": 0.005,
          "provenance": "assumed",
          "confidence": "low",
          "method": "neglected (0); plausible up to a few mH"
        }
      },
      "conflicts": [],
      "leastCertain": [
        "Jm",
        "Bm",
        "tau_c"
      ],
      "hasPolicy": false
    }
  },
  "recommendations": {
    "rmcs_3070": {
      "constraint_probability": {
        "accuracy": 1.0,
        "overshoot": 1.0,
        "settling": 1.0
      },
      "gains": {
        "Kd": 2.9290538522819873,
        "Ki": 0.10744231192910968,
        "Kp": 73.20465642182674
      },
      "label": "TIER 1 - datasheet estimate: safe starting point, expect to re-tune (preliminary, not validated)",
      "load": "bare_shaft",
      "margins": {
        "crossover_rad_s": 19.24687915420091,
        "delay_margin_s": 0.04086683495890771,
        "gain_margin_db": 32.241180955200036,
        "phase_margin_deg": 45.066512978568085
      },
      "method": "optimised (robust)",
      "next_measurement": "rotor inertia: free-run speed decay with and without a known added inertia (docs/validation_plan.md T6)",
      "predictions": {
        "IAE / |ref| [s]": {
          "p5": 0.09581728281363273,
          "p50": 0.10980888325600177,
          "p95": 0.1698488473366573
        },
        "control effort [mean V^2 / Vmax^2]": {
          "p5": 0.061047353425602906,
          "p50": 0.07052634798637458,
          "p95": 0.12697866009636224
        },
        "overshoot [%]": {
          "p5": 0.021470432640413938,
          "p50": 0.021696660582237983,
          "p95": 1.7616975187459167
        },
        "peak current [A]": {
          "p5": 8.496403935673,
          "p50": 17.44497829933146,
          "p95": 27.846316320530903
        },
        "settling time [s]": {
          "p5": 0.27935000000000004,
          "p50": 0.2885,
          "p95": 0.3432999999999999
        },
        "steady-state error [deg]": {
          "p5": 0.01624890051482329,
          "p50": 0.01771158156353824,
          "p95": 0.01860981088406951
        }
      },
      "profile_hash": "256ca5262cf4d1a0",
      "seed": 0,
      "tier": 1,
      "warnings": [
        "datasheet conflict unresolved: meaning of the current rating",
        "datasheet conflict unresolved: output stall torque versus K, stall current and efficiency",
        "predicted peak current reaches 27.8 A in some plausible plants, above the 7.5 A rating: set a driver current limit (config driver.current_limit_A) and re-run"
      ]
    },
    "synthetic_brushed_48v": {
      "constraint_probability": {
        "accuracy": 1.0,
        "overshoot": 1.0,
        "settling": 1.0
      },
      "gains": {
        "Kd": 0.8697527402067194,
        "Ki": 0.09352465532198424,
        "Kp": 63.759540177009065
      },
      "label": "TIER 1 - datasheet estimate: safe starting point, expect to re-tune (preliminary, not validated)",
      "load": "bare_shaft",
      "margins": {
        "crossover_rad_s": 12.706145423981361,
        "delay_margin_s": 0.08679355676593546,
        "gain_margin_db": 37.953613184751035,
        "phase_margin_deg": 63.18644765005865
      },
      "method": "optimised (robust)",
      "next_measurement": "rotor inertia: free-run speed decay with and without a known added inertia (docs/validation_plan.md T6)",
      "predictions": {
        "IAE / |ref| [s]": {
          "p5": 0.09762500937450014,
          "p50": 0.10556493777361953,
          "p95": 0.11708537579236158
        },
        "control effort [mean V^2 / Vmax^2]": {
          "p5": 0.051544404884158714,
          "p50": 0.05668227871398419,
          "p95": 0.06573400861469197
        },
        "overshoot [%]": {
          "p5": 0.005834599208766475,
          "p50": 0.0058911738198396,
          "p95": 1.0023433126731456
        },
        "peak current [A]": {
          "p5": 18.59310017983293,
          "p50": 20.550477486644553,
          "p95": 21.976593710015806
        },
        "settling time [s]": {
          "p5": 0.25105,
          "p50": 0.318,
          "p95": 0.35764999999999997
        },
        "steady-state error [deg]": {
          "p5": 0.0037529312794364065,
          "p50": 0.00525417099434879,
          "p95": 0.006742611990495025
        }
      },
      "profile_hash": "62996aeda0f81eb4",
      "seed": 0,
      "tier": 1,
      "warnings": [
        "an optimised gain sits at the edge of its search range: the bounds were too tight, widen them and re-run"
      ]
    },
    "synthetic_coreless_12v": {
      "constraint_probability": {
        "accuracy": 1.0,
        "overshoot": 1.0,
        "settling": 1.0
      },
      "gains": {
        "Kd": 0.303332298869463,
        "Ki": 0.04395481707762285,
        "Kp": 9.430689359607968
      },
      "label": "TIER 1 - datasheet estimate: safe starting point, expect to re-tune (preliminary, not validated)",
      "load": "bare_shaft",
      "margins": {
        "crossover_rad_s": 9.27884378137798,
        "delay_margin_s": 0.11947521416013347,
        "gain_margin_db": 41.21528541654862,
        "phase_margin_deg": 63.51763408948804
      },
      "method": "optimised (robust)",
      "next_measurement": "rotor inertia: free-run speed decay with and without a known added inertia (docs/validation_plan.md T6)",
      "predictions": {
        "IAE / |ref| [s]": {
          "p5": 0.11662661013866137,
          "p50": 0.12351450490686836,
          "p95": 0.13468766779946756
        },
        "control effort [mean V^2 / Vmax^2]": {
          "p5": 0.029101947596812363,
          "p50": 0.03333203808879037,
          "p95": 0.04414865609111544
        },
        "overshoot [%]": {
          "p5": 0.032255119071807475,
          "p50": 0.032634971375726546,
          "p95": 1.9551879392563023
        },
        "peak current [A]": {
          "p5": 3.613284116567601,
          "p50": 3.800895510349212,
          "p95": 3.9265786597413013
        },
        "settling time [s]": {
          "p5": 0.3004,
          "p50": 0.4245,
          "p95": 0.4823
        },
        "steady-state error [deg]": {
          "p5": 0.0281646337368857,
          "p50": 0.02826982833495212,
          "p95": 0.028452917687768597
        }
      },
      "profile_hash": "454287f2b4f08c90",
      "seed": 0,
      "tier": 1,
      "warnings": [
        "an optimised gain sits at the edge of its search range: the bounds were too tight, widen them and re-run"
      ]
    }
  },
  "tierLabels": {
    "1": "TIER 1 - datasheet estimate: safe starting point, expect to re-tune",
    "2": "TIER 2 - identified from bench data",
    "3": "TIER 3 - refined on hardware"
  }
};
if (typeof module !== 'undefined' && module.exports) module.exports = DTRL_CONFIG;
