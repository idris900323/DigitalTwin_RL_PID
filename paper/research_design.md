# Research design (simulation-only scope, venue-neutral)

Scope decision: simulation only for now; hardware experiments are not run (motor and bench still open). The hardware sections of the manuscript are a replication protocol and plan with no results.

## Question
Does a reinforcement-learning policy improve the position PID gains of a geared DC-motor joint beyond a validation-tuned constant gain set, on an open, datasheet-derived (unvalidated) digital twin, and by how much of what a scenario-aware oracle could achieve?

## Central claim (revised after the post-hoc sensitivity result; headline = evaluation protocol)
How much of an apparent RL gain survives a properly tuned constant baseline? On the unvalidated twin, a residual PPO around a validation-tuned constant beats that constant by about 0.5-0.6 median return (confirmatory seeds 60000+: static +0.61, changes +0.58, ood +0.45; fresh seeds 80000+: +0.49, +0.60, +0.46). But a much larger validation search for the constant alone recovers most of it (+0.39, +0.67, +0.33), and a non-learned scenario-conditioned rule matches the policy (policy minus rule: -0.04, -0.10, -0.04 with intervals including zero). The policy's remaining advantage over the stronger constant is at most +0.10 (static) and absent when payload and target change. The residual-RL result is secondary. The supported contribution is the evaluation protocol and the evidence that it matters.

## Hypotheses and rules (as applied; not formally pre-registered, see decision_log.md)
- Primary metric: episode return (default reward). Success rate: descriptive only.
- One primary test: validation-selected PPO minus best constant, static regime, feasible scenarios, paired median difference with a 95 % bootstrap CI. Everything else secondary: Wilcoxon signed-rank, Holm over the secondary family.
- Feasible/infeasible split: margin >= 1 for the whole episode; infeasible scenarios reported separately.
- Seed sets: training < 20000; validation 40000-40039; exploratory (for v3) 50000-50099; confirmatory v3 60000-60099; confirmatory v4 70000-70099. Nothing is re-tuned on 50000+, 60000+ or 70000+.

## Negative results kept
v2 unconstrained PPO failure and instability; TD3 does not beat the constant; SAC mixed (median CI excludes zero, Wilcoxon p = 0.116); no policy helps in `changes` in v4; the bandit improves the mean but not the median over the best constant in `static`.

## Out of scope
Hardware results; any statement about industrial robot joints; claims that the twin is validated.
