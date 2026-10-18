# Paper outline (draft stage; venue-neutral IEEE-style; simulation only)

Status: a first full draft exists in `paper/manuscript/` (LaTeX, not compiled: no LaTeX toolchain on the drafting machine). Every number in it is a macro generated from `results/` by `paper/make_numbers.py`. Not polished; waiting for your comments on this outline and on `figure_table_list.md`.

## Title candidates (pick one; each implies a different claim)
1. *Residual Reinforcement Learning on a Tuned Constant: A Simulation Study of PID Gain Adaptation for a Geared DC-Motor Joint* (current draft; claims the residual result)
2. *Does Learned PID Adaptation Beat a Tuned Constant? A Pre-Validation Simulation Study on a Digital Twin* (question form; safest)
3. *Honest Baselines for Learned PID Gain Adaptation: Validation-Tuned Constants and Hindsight Oracles on a DC-Motor Digital Twin* (methodology-first)
4. *When Does RL Help PID Tuning? Negative and Positive Results on a Geared DC-Motor Digital Twin* (balanced; invites the negative results)
5. *A Reproducible Protocol for Evaluating Learned PID Tuners, with a Simulation Case Study and a Hardware Replication Plan* (protocol/artifact-first)

## Structure
- **Abstract** (about 200 words): problem; protocol (validation-selected baselines, oracle, one primary test, infeasible split); scale (100 scenarios per regime, three regimes, 3-5 seeds per algorithm); headline results with CIs; limitation in one clause (simulation only, unvalidated twin); availability. *Revise after the post-hoc constant check.*
- **1 Introduction:** weak-baseline problem; research question; what the paper does; what it finds (v2 failure, v3 residual result, SAC/TD3, near-constant gains); scope; contributions (only the supported ones).
- **2 Related work (stub, incomplete):** classical autotuning; learning-based PID tuning; residual RL; algorithms and evaluation practice. Only verified references; a systematic search is still to do before any novelty claim.
- **3 Problem formulation:** plant equations, controller, scenarios and feasibility, episodes, return (primary), success rate (descriptive).
- **4 Method:** environment; baselines (Tuned, legacy, ZN, bandit, bandit re-tuned, best constant, hindsight oracle); learned policies (v2 multiplicative, v3/v4 residual); checkpoint and seed selection on validation seeds.
- **5 Experimental setup:** seed sets (training / validation / exploratory / confirmatory), regimes, statistics (median CI + mean + IQR; Wilcoxon + Holm), software and provenance.
- **6 Results (simulation only):** 6.1 v2 failure and instability; 6.2 v3 confirmatory (60000+) and exploratory (50000+), success rate descriptive; 6.3 headroom captured; 6.4 infeasible scenarios; 6.5 v4 (smaller range; SAC mixed, TD3 no, no helpful policy in `changes`); 6.6 post-hoc constant-sensitivity (pending).
- **7 Discussion:** what the evidence supports; why v2 failed (hypotheses only); adaptation or a better constant; practical guidance.
- **8 Limitations and threats to validity:** unvalidated twin, no hardware, one motor, one reward, 3 seeds, baseline strength, design chosen after seeing results, metric weights, modelling gaps, reproducibility scope.
- **9 Conclusion and future work.**
- **Availability.**
- **Appendix A:** hardware replication protocol and plan (no results, thresholds to be fixed before data).
- **Appendix B:** seed-set table, baseline-budget table, hyperparameters, exploratory table.

## Decisions I need from you
1. Title (above) and whether the headline should be the residual result or the evaluation-protocol framing, given the open threat below.
2. Whether the post-hoc constant-sensitivity analysis (added after the confirmatory runs) goes in the main text or the supplement (my recommendation: main text, labelled post hoc).
3. Whether to extend the related-work search now (needed before any novelty claim) or after the claims are final.
4. Whether to add seeds (3 per algorithm is thin; 5-10 would make seed-level statements possible).

## Open threat to the central claim
The learned policies end at nearly constant gains (v4 PPO: Kp 19.6 with a 10-90 % range 19.5-19.8, Kd 1.23; v3: Kp 28 with 24-35). The benefit over `best_constant` may therefore be a better constant than the modest search found, not adaptation. `simulation/constant_sensitivity.py` (running now) adds, on validation seeds only, an extended-search constant and the policy's own median gains, both evaluated once on the confirmatory seeds and labelled post hoc. The abstract, section 6.6, discussion and conclusion are to be revised according to the result, whichever way it goes.
