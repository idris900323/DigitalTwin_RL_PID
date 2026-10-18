# Decision log (replaces a pre-registration for the RL experiments)

The RL experiments were **not pre-registered** before they were run. This log records, in order, what was decided when, so readers can judge which results are confirmatory. Commits are from the project history (`git log`).

| Step | What was decided / run | Evidence level |
|---|---|---|
| v2 design (commit 6e2b599 and earlier) | Multiplicative residual-free actions, Kp/Ki/Kd bounds, reward weights, 5 seeds, checkpoint = best on the training-evaluation seeds. Comparison on test seeds 50000-50099 with a best-constant baseline chosen on validation seeds 40000+ and a hindsight oracle. | Design fixed before its own test run: pre-specified for v2. Result: PPO worse than the best constant (primary median difference -1.75). |
| Review of v2 (before v3) | Statistics rules fixed: return primary metric; one primary test (validation-selected PPO minus best constant, `static`, feasible scenarios, paired median difference with 95 % bootstrap CI); Holm over the secondary family; infeasible scenarios (margin < 1 at any point) reported separately; checkpoints chosen on validation seeds. | Fixed before v3 was run. |
| v3 design (commit 051e238) | Residual formulation around the validation-chosen best constant, lower learning rate, shaped reward (time outside the 2 % band), 400k decisions, 3 seeds, checkpoint selection on validation seeds. **Chosen after seeing the v2 test results on seeds 50000+.** | Seeds 50000+ are EXPLORATORY for v3. |
| v3 on seeds 50000-50099 | Run once; labelled exploratory. | Exploratory. |
| v3 on seeds 60000-60099 | Run once, nothing trained or selected on them. | **Confirmatory** for v3. |
| v4 design | Smaller residual range (span 1.5, Ki offset 10), 200k decisions, PPO, SAC and TD3, 3 seeds each. Fixed before looking at the 60000+ results for v4 purposes; run once on seeds 70000-70099. | **Confirmatory** for v4 (a separate experiment). |
| Post-hoc constant-sensitivity analysis | Added **after** the confirmatory runs because the learned policies end at nearly constant gains (median PPO gains vary little across scenarios, the `*Gain*` macros in `paper/generated/numbers.tex`). Two extra constants derived on validation seeds only: an extended-search best constant and the PPO policy's median gains on the validation scenarios. Evaluated once on the test seeds. | POST HOC, labelled as such wherever reported. |

Rules kept throughout: nothing was re-tuned on seeds 50000+, 60000+ or 70000+; every run is in `experiment_ledger.csv`; negative results are reported (v2 failure and instability, TD3, SAC mixed, no helpful policy in `changes` for v4).

Known departures from the paper-preparation prompt: no formal pre-registration file for the RL runs (this log instead); no hardware data (scope decision: simulation only, hardware sections are a replication plan); the related-work search is incomplete (see `literature_log.md`).

## Update (after the first paper draft)

- A first post-hoc look (seeds 60000-60099; constants derived on validation seeds only) found that a much larger validation search for the constant already recovers most of the residual-PPO gain (extended constant: static +0.48, changes +0.60, ood +0.21 median return over the original best constant, against PPO +0.61, +0.58, +0.45). This changed the decision: the paper is framed around the evaluation protocol (how much of an apparent RL gain survives a properly tuned constant), with the residual-RL result as a secondary result; the final title waits for the sensitivity result.
- Because seeds 60000+ had already been used for the v3 confirmatory comparison, the full post-hoc analysis (extended constant, policy-distilled constants, a non-learned scenario-conditioned baseline, gain scatter) is run once on a fresh seed range, 80000-80099 (ledger L12, L13). Related work is extended only after the claims are final; more seeds are added only if the residual claim survives the check.

## Update (after the reframing was accepted)

- Reframing accepted and the title stands. The post-hoc sensitivity table was recomputed independently from `results/constant_sensitivity_v3_80k/per_episode.csv` and matches.
- Kd-bound check added as a supplement item (ledger L14): the extended-constant search is repeated with the Kd upper bound raised from 2 to 4 (constants only; the learned policy keeps its training environment), constants derived on validation seeds, evaluated once on a fresh range 90000-90099. It reports whether the constants move off the bound and whether the policy minus extended-constant difference changes. Nothing is re-tuned on seeds 50000+, 60000+, 70000+ or 80000+; no training seeds are added; related work is not extended.
- Wording fixed: most of the policy's gain over the original constant is a better constant; a small residual remains in static and ood (about 1.8 % and 0.6 % of |return|) and is not attributed to adaptation. Wilcoxon 1945, the Lawrence et al. journal details and the Tobin IROS acceptance stay in `unverified_refs.md` and are not marked verified. LaTeX is not compiled here: see `static_check_report.md`.

