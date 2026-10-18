# Research design (simulation-only scope, venue-neutral)

Scope decision: simulation only for now; hardware experiments are not run (motor and bench still open). The hardware sections of the manuscript are a replication protocol and plan with no results.

## Question
Does a reinforcement-learning policy improve the position PID gains of a geared DC-motor joint beyond a validation-tuned constant gain set, on an open, datasheet-derived (unvalidated) digital twin, and by how much of what a scenario-aware oracle could achieve?

## Central claim (the only RL claim the evidence supports)
In simulation on the unvalidated twin, a PPO policy acting as a residual on a validation-tuned constant beats that constant by about 0.5-0.6 median return (roughly 6-10 % of |return|), across seeds and on fresh seeds 60000+ (static +0.61, changes +0.58, ood +0.45). It is not "RL tunes PID well": PPO captures only part of the oracle headroom (seed-average 44 % / 10 % / 31 % in static / changes / ood).

**Open threat to this claim (post-hoc check running):** the learned policies end at nearly constant gains, so the benefit may come from a better constant than the baseline search found rather than from adaptation. `simulation/constant_sensitivity.py` adds two validation-derived constants. The claim and the abstract are to be revised according to its result.

## Hypotheses and rules (as applied; not formally pre-registered, see decision_log.md)
- Primary metric: episode return (default reward). Success rate: descriptive only.
- One primary test: validation-selected PPO minus best constant, static regime, feasible scenarios, paired median difference with a 95 % bootstrap CI. Everything else secondary: Wilcoxon signed-rank, Holm over the secondary family.
- Feasible/infeasible split: margin >= 1 for the whole episode; infeasible scenarios reported separately.
- Seed sets: training < 20000; validation 40000-40039; exploratory (for v3) 50000-50099; confirmatory v3 60000-60099; confirmatory v4 70000-70099. Nothing is re-tuned on 50000+, 60000+ or 70000+.

## Negative results kept
v2 unconstrained PPO failure and instability; TD3 does not beat the constant; SAC mixed (median CI excludes zero, Wilcoxon p = 0.116); no policy helps in `changes` in v4; the bandit improves the mean but not the median over the best constant in `static`.

## Out of scope
Hardware results; any statement about industrial robot joints; claims that the twin is validated.
