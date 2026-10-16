# Follow-ups (found during Group 1, deliberately not fixed inline)

1. **Trainer still duplicates plant constants** (`CFG` in `train_autotune_360.py`, `CFG` in the HTML) and the marginal-margin threshold (1.2). `tests/test_feasibility.py` checks they match the YAML for now; G2.1 removes the duplication via a generated config.
2. **JS feasibility uses the page's own constants**, not generated ones (same G2.1 item). `tests/browser` checks it against `models/feasibility.py`.
3. **Qt demo has no gravity yet**, so the torque-margin status line was removed (it would always read "no gravity holding torque"). G2.3 adds gravity and brings the line back.
4. **Policy initial bias** (`b3`) still starts near the legacy gains (5, 20, 0.05). It only affects the starting point of training; worth revisiting once a feasibility feature or the Tuned preset is the natural start.
5. **Feasibility is not a policy input.** The tuner gets mass, length, gravity, speed limit and target but not the margin itself. Adding it would change `FEATURE_VERSION` and the JS contract.
6. **`meta.json` records the git commit the trainer ran on**, i.e. the commit *before* the one that stores the new weights. Consider recording a "dirty" flag.
7. **Line endings:** several files are CRLF and some are LF (git warns on every add). A `.gitattributes` with `* text=auto` would settle it; not done because it would rewrite many files.
8. **`.vscode` is intentionally not ignored** (existing `.gitignore` comment); the improvement prompt listed `.vscode` as ignorable. Kept the repo's deliberate choice.
9. **Browser tests need Chromium** (`playwright install chromium`) and a WebGL-capable launch (`--enable-unsafe-swiftshader --ignore-gpu-blocklist`); without those flags the 3D canvas renders blank although the tests still pass.
10. **Trainer cost is noisy per batch** (different contexts each iteration); the final policy is judged only by the held-out table.
11. **Torque margin ignores back-EMF** (and any driver current limit), so it is an upper bound on available torque while moving; now documented in `models/feasibility.py` and in the browser banner/tooltip. A moving-state margin would need the speed profile.
12. **Marginal band (margin 1.0-1.2) is outside the training distribution** (about 3 % of raw draws). The policy is weaker there; options: include the band in training, or add the margin as a policy feature (changes `FEATURE_VERSION`).

## Investigation: why the HTML is 15 MB (no packaging decision taken yet)

The 15.76 MB page is not "a 0.5 MB GLB plus libraries". Measured by decoding the file:

| Part | Size |
|---|---|
| Embedded CAD (`GLB_B64`, base64 of an 11.08 MB GLB) | **14.77 MB (94 %)** |
| three.js r128 | 0.60 MB |
| Chart.js 4.4.4 | 0.21 MB |
| GLTFLoader + OrbitControls | 0.13 MB |
| Application script (physics, UI, policy weights) | about 0.05 MB |

The embedded GLB is **not** `cad/JGB37-520_converted.glb`: it is a different tessellation of the same STEP and the same bounding box, with **517,684 triangles versus 23,480** (22x denser). Three screws account for about 83k triangles (27.6k each versus 1.1k in the repo GLB). The repo GLB is `cascadio.step_to_glb` at its defaults (`tol_linear=0.01`, `tol_angular=0.5`), which also explains the faceted look of the Qt demo.

`cascadio.step_to_glb` size by tolerance (same STEP):

| tol_linear / tol_angular | GLB size | triangles | page size if embedded (about 1.0 MB for the rest) |
|---|---|---|---|
| 0.01 / 0.5 (repo default) | 0.54 MB | 23,480 | about 1.7 MB |
| 0.003 / 0.2 | 1.64 MB | 82,828 | about 3.2 MB |
| 0.001 / 0.1 | 4.69 MB | 255,506 | about 7.2 MB |
| (current embedded, roughly 0.0005) | 11.08 MB | 517,684 | 15.8 MB |

A 37 mm motor drawn in a viewport a few hundred pixels wide cannot show more than tens of thousands of triangles, so the extra 10 MB buys no visible detail. Packaging options (Git LFS, release asset, sibling files) are worth choosing only after deciding the mesh density: with the 0.003/0.2 mesh the single-file page is about 3 MB and may not need any of them.

**Decision (Group 2 review): use the 83k-triangle mesh (`tol_linear=0.003`, `tol_angular=0.2`) everywhere.** `cad/JGB37-520_converted.glb` is regenerated at those tolerances (1.6 MB, same 11 parts and bounds), the Qt demo uses it, and `tools/generate_js_config.py` embeds the same file in the browser page, so there is one mesh and one source. The page drops from 15.8 MB to 3.2 MB, which makes Git LFS, release assets and sibling-file loading unnecessary. (The old 15 MB blobs stay in git history.) `tests/test_cad_mesh.py` pins the density, part names and bounds.

## Earlier proposal (superseded by the measurements and the decision above): packaging options

| Option | Pros | Cons |
|---|---|---|
| A. Git LFS for the HTML | Keeps the file in the repo; simple for users who clone | Needs LFS enabled for everyone and on the host; bandwidth quotas; still a 15 MB blob changing on every edit |
| B. Build script that injects the GLB and policy into a small template, publish the result as a GitHub release asset | Repo holds ~100 KB template + the GLB/policy it already has; history stays small; the single-file artifact is still downloadable | Adds a build step; the page in the repo is no longer directly openable |
| C. Page loads `JGB37-520_converted.glb` and `autotune_policy_360.json` from sibling files when served over HTTP | Smallest repo, no build step, no duplication of the policy (removes the "embedded vs committed" drift) | Needs a local web server (already needed because `file:` is blocked); not a single portable file |

Recommendation: **C for development plus B for sharing**. C removes the embedded-policy duplication that the parity test currently guards, and B produces the one-file version when someone wants to email it. Waiting for a decision before changing anything.

## Found during Group 2

13. **Explicit RK4 was unstable for L > 0 at realistic inductances** (L/R = 60 us - 3 ms versus a 1 ms control step). `DCMotor.step` now sub-steps automatically (h <= 2 L/R, capped at 20,000); L = 0 is unchanged. The browser physics (`physics.js`) and the trainer have no sub-stepping, but they only run L = 0 today. Needed before the L sweep in the sensitivity study (G3.2) is mirrored there.
14. **PID is not bumpless for Ki changes** (integral state is the plain integral of e). Changing Ki mid-run steps the output by dKi * integral. Fine for fixed gains; the step-wise RL environment (G4) must rate-limit Ki changes or switch to storing the integral of Ki*e. Documented in `tests/test_pid.py`.
15. **`simulation/metrics.py` mishandled negative steps** (overshoot always 0, rise time wrong). Fixed by mirroring the response; the JS metrics still assume a positive target (the page only uses 0-360 deg).
16. **Noise is not modelled in the browser physics.** The noise scenario is Python + trainer only (documented in `tests/test_cross_implementation.py`).
18. **Toolchain-specific reproducibility:** policy weights are byte-identical only on the same numpy/Python (see `autotune_360/README.md`); cross-platform tolerance 7.3e-4 measured by the maintainer.
19. **Inductance:** `DCMotor.step` raises beyond `MAX_SUBSTEPS`; `physics.js` and the trainer refuse L > 0 until they sub-step.

17. **Deviations from the base code in `html/`** that you may want to revisit: default gains now Tuned (base: 5/20/0.05, kept as "Legacy default"); trainer samples feasible contexts only (base: all contexts; `--include-infeasible` restores it) and uses derived child RNG streams (so retrained weights differ from the base policy, which is kept in `html/`); the HTML physics is now inlined from `physics.js` and `config.generated.js` instead of hand-written constants; the arm-length slider default is 3.0 cm (base 2.8, snapped by the browser). On every scenario the base supports, the refactored code reproduces the base to 1e-9 (`tests/test_base_code_oracle.py`).

## Paper-readiness constraints to honour in Groups 2-4 (from `PAPER_PREPARATION_PROMPT.md`, not yet enacted)

The paper effort needs the software to produce auditable, regenerable data. Keep these in mind while building the improvement work, so nothing has to be retrofitted:

1. **Raw-log schema.** Per-tick runs should be writable in the paper's schema (`t_s, step_idx, target_deg, theta_deg, theta_counts, omega_rad_s, error_deg, v_cmd_V, v_applied_V, i_A, temp_C, vsupply_V, kp, ki, kd, gain_update_flag, payload_kg, arm_len_m, gravity_on, run_id, experiment_id, seed, session_id, unit_id, method`, plus `true_params_hash` for simulation). `DigitalTwin.step()` already returns most of these; `simulate_pid.py` (G3.1) and the RL env (G4) should emit them. Note `i_A` only became real with G1.1.
2. **Run provenance.** Every script that produces data takes a seed, logs it, and writes a manifest with commit, config hash, seeds, versions and file checksums (the trainer's `meta.json` is the first example).
3. **Single-command regeneration.** Figures and tables come from scripts reading `data/` and `config/` only; a top-level `make` (`data-sim`, `analyze`, `figures`, `tables`, `smoke`) is wanted. G3.1/G3.2 outputs should already be regenerable by one command.
4. **Wording.** "Preliminary" until validation thresholds pass; RL results labelled pre-validation. The trainer, browser page and docs already follow this.
5. **Fair baselines and budgets.** `simulation/compare_controllers.py` (G4.3) should log the evaluation budget of each tuning method and use paired scenarios with disjoint training/test seeds.
6. **One colour and marker per method across all figures** (define it once in a shared plotting module when the first comparison figure is written).
7. **No local paths in artefacts.** Keep absolute paths (`C:\Users\...`) out of committed metadata, figures and logs (relevant for later double-blind submission).
8. **Licences.** The JGB37-520 CAD and the Johnson datasheet PDF are in the repo; record their terms (open question 9 in the improvement prompt) before any public release.
