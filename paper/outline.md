# Paper outline (draft stage; venue-neutral IEEE-style; simulation only)

Status: a first full draft exists in `paper/manuscript/` (LaTeX, not compiled: no LaTeX toolchain on the drafting machine). Every number in it is a macro generated from `results/` by `paper/make_numbers.py`. Not polished; waiting for your comments on this outline and on `figure_table_list.md`.

## Title candidates (current draft title: *How Much of an Apparent RL Gain Survives a Properly Tuned Constant? An Evaluation Protocol for Learned PID Gain Adaptation on a Geared DC-Motor Digital Twin*; options below, confirm one)
1. *Residual Reinforcement Learning on a Tuned Constant: A Simulation Study of PID Gain Adaptation for a Geared DC-Motor Joint* (no longer supported as a headline: the residual result is secondary)
2. *Does Learned PID Adaptation Beat a Tuned Constant? A Pre-Validation Simulation Study on a Digital Twin* (question form; safe)
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

## Result of the post-hoc check (decides the headline)
Fresh seeds 80000-80099, every new baseline derived on validation seeds only (ledger L12, L13; an earlier look on 60000+ is L11):
- The residual PPO still beats the original constant (+0.49 / +0.60 / +0.46 median return, static / changes / ood).
- An extended-search constant (about 240 validation evaluations) gets +0.39 / +0.67 / +0.33, i.e. most of it; the policy's remaining edge over it is +0.10 [+0.06, +0.15] static, -0.11 (not distinguishable from zero) with changes, +0.05 out of distribution.
- A non-learned scenario-conditioned rule (log Kp, log Kd linear in mass, gravity torque, inertia; fitted on validation) matches the policy: policy minus rule -0.04, -0.10, -0.04, intervals include zero.
- The policy does track the load (Kp is clearly higher when gravity acts), the same dependence the rule finds.
- v4 PPO is essentially a constant (pooled distilled constant Kp 19.5, Kd 1.2 beats the original by +0.22 / +0.20 / +0.36); it is not better than the extended constant and is worse than it (and than the rule) when payload and target change.
- Caveats: the extended constants sit at the Kd bound of 2 (set for noise), the rule is simple, and a stronger learner (longer training, more seeds, other rewards) was not tried. More seeds are added only if a configuration beats the stronger baselines.

The paper is therefore framed as: how much of an apparent RL gain survives a properly tuned constant baseline, with the residual-RL result secondary and the negative results kept.

## Decisions I still need
1. Confirm the title (draft title above) or pick another.
2. Whether to open the PR from `paper/draft` now or after your review of the revised text (I have not opened one).
3. Related-work extension is still deferred until the claims are final (they now are, unless you want a stronger learner first).
