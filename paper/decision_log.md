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
| Post-hoc constant-sensitivity analysis | Added **after** the confirmatory runs because the learned policies end at nearly constant gains (median PPO gains vary little across scenarios, `paper/gain_spread` in `make_numbers.py` outputs). Two extra constants derived on validation seeds only: an extended-search best constant and the PPO policy's median gains on the validation scenarios. Evaluated once on the test seeds. | POST HOC, labelled as such wherever reported. |

Rules kept throughout: nothing was re-tuned on seeds 50000+, 60000+ or 70000+; every run is in `experiment_ledger.csv`; negative results are reported (v2 failure and instability, TD3, SAC mixed, no helpful policy in `changes` for v4).

Known departures from the paper-preparation prompt: no formal pre-registration file for the RL runs (this log instead); no hardware data (scope decision: simulation only, hardware sections are a replication plan); the related-work search is incomplete (see `literature_log.md`).
