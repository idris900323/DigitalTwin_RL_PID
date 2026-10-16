# Follow-ups (found during Group 1, deliberately not fixed inline)

1. **Trainer still duplicates plant constants** (`CFG` in `train_autotune_360.py`, `CFG` in the HTML) and the marginal-margin threshold (1.2). `tests/test_feasibility.py` checks they match the YAML for now; G2.1 removes the duplication via a generated config.
2. **JS feasibility uses the page's own constants**, not generated ones (same G2.1 item). `tests/browser` checks it against `models/feasibility.py`.
3. **Qt demo has no gravity yet**, so its new torque-margin status line always reads "no gravity holding torque". G2.3 adds gravity and makes it meaningful.
4. **Policy initial bias** (`b3`) still starts near the legacy gains (5, 20, 0.05). It only affects the starting point of training; worth revisiting once a feasibility feature or the Tuned preset is the natural start.
5. **Feasibility is not a policy input.** The tuner gets mass, length, gravity, speed limit and target but not the margin itself. Adding it would change `FEATURE_VERSION` and the JS contract.
6. **`meta.json` records the git commit the trainer ran on**, i.e. the commit *before* the one that stores the new weights. Consider recording a "dirty" flag.
7. **Line endings:** several files are CRLF and some are LF (git warns on every add). A `.gitattributes` with `* text=auto` would settle it; not done because it would rewrite many files.
8. **`.vscode` is intentionally not ignored** (existing `.gitignore` comment); the improvement prompt listed `.vscode` as ignorable. Kept the repo's deliberate choice.
9. **Browser tests need Chromium** (`playwright install chromium`) and a WebGL-capable launch (`--enable-unsafe-swiftshader --ignore-gpu-blocklist`); without those flags the 3D canvas renders blank although the tests still pass.
10. **Trainer cost is noisy per batch** (different contexts each iteration); the final policy is judged only by the held-out table.
11. **Torque margin ignores back-EMF**, so it is an upper bound on available torque while moving. A moving-state margin would need the speed profile.

## Proposal (not executed): the 15 MB self-contained HTML

| Option | Pros | Cons |
|---|---|---|
| A. Git LFS for the HTML | Keeps the file in the repo; simple for users who clone | Needs LFS enabled for everyone and on the host; bandwidth quotas; still a 15 MB blob changing on every edit |
| B. Build script that injects the GLB and policy into a small template, publish the result as a GitHub release asset | Repo holds ~100 KB template + the GLB/policy it already has; history stays small; the single-file artifact is still downloadable | Adds a build step; the page in the repo is no longer directly openable |
| C. Page loads `JGB37-520_converted.glb` and `autotune_policy_360.json` from sibling files when served over HTTP | Smallest repo, no build step, no duplication of the policy (removes the "embedded vs committed" drift) | Needs a local web server (already needed because `file:` is blocked); not a single portable file |

Recommendation: **C for development plus B for sharing**. C removes the embedded-policy duplication that the parity test currently guards, and B produces the one-file version when someone wants to email it. Waiting for a decision before changing anything.
