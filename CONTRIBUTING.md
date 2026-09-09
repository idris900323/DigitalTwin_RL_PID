# Contributing

Read [`master_prompt_digital_twin_rl_pid.md`](master_prompt_digital_twin_rl_pid.md)
before your first PR — it's the project spec, including the hard engineering
rules (§20) and the phase order (§21) this project follows strictly.

## Branching model

- `main` stays always-working — don't push directly to it.
- Branch off `main` as `feature/<short-description>`, e.g.
  `feature/gearbox-efficiency-sweep`, `feature/encoder-noise-model`.
- Open a PR back into `main` when ready. **At least one other person
  reviews before merge.** Small team, so no separate `dev` branch.

## Keeping your branch current

Before pushing, pull the latest `main` and rebase (preferred, keeps history
linear) or merge:

```bash
git fetch origin
git rebase origin/main        # or: git merge origin/main
# resolve any conflicts, then
git push --force-with-lease   # only needed after a rebase
```

Don't `--force` (without `--force-with-lease`) on a shared branch, and never
force-push to `main`.

## Commit messages

Short imperative summary line (≤ ~70 chars), blank line, then a body if the
"why" isn't obvious from the summary:

```
Add gearbox efficiency to load-torque reflection

Was hardcoded to eta=1 in gearbox.py; now reads
config/motor_parameters.yaml's gearbox.efficiency, per the "no
hard-coded parameters" rule.
```

## PR review checklist

- [ ] **No hardcoded parameters.** Anything datasheet/CAD/estimated/assumed
      goes in `config/*.yaml`, tagged with its provenance category
      (CAD-derived / Datasheet / Calculated / Estimated / Assumed /
      Experimental — master prompt §3/§11), never inline in code.
- [ ] **No fabricated datasheet values.** If a parameter can't be derived,
      say so explicitly and propose a defensible estimation method — don't
      invent a number and let it look measured.
- [ ] **No skipped phases.** Check the PR's work against master prompt §21's
      phase order; RL code (Phase 13+) should not appear before the fixed
      PID + validated digital twin exist, etc.
- [ ] **Motor-side vs. output-side quantities** are not mixed without going
      through the gear ratio explicitly (§20).
- [ ] **SI units internally**; RPM/kg-cm/etc. conversions happen at the
      boundary and are shown, not silent.
- [ ] New physics/config changes come with a quick sanity check (a
      `simulation/` script run, or metrics printed) showing the change does
      what it claims — not just "it runs without erroring."
