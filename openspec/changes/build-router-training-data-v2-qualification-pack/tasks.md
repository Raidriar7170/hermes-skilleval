## 1. Freeze the Approved Boundary

- [ ] 1.1 Record `pwd`, branch, clean status, base commit, canonical input hashes/counts, and protected Phase 14/15/16 blob identities in the isolated Worker worktree.
- [ ] 1.2 Confirm the canonical inputs remain 12 non-blind migration tasks and 16 Phase 9 skills; stop and re-plan if the skill universe, source counts, or protected evidence changed.
- [ ] 1.3 Confirm the implementation scope excludes the 45-skill benchmark, blind prompt content/hashes, external evaluation-only sets, training, A100/GPU work, checkpoints, calibration, model selection, publication, merge, and archive actions.

## 2. Add Qualification Tests First

- [ ] 2.1 Add failing unit tests for resolved-path and `blind-*` directory preflight before `load_tasks()`, duplicate/missing identities, and mixed gold ecosystem categories; record the expected RED result.
- [ ] 2.2 Add failing unit tests for deterministic task-skill product ordering, stable IDs, prompt hashes, candidate classification, source split/disposition, and exact 192/16/32/144 canonical counts; record the expected RED result.
- [ ] 2.3 Add failing unit tests for qualification-policy counts, target-skill coverage, reserved test rows, blocker codes, `REVIEW_REQUIRED`, `KEEP_BASELINE`, `can_start_training=false`, and absent `training-pairs.jsonl`; record the expected RED result.
- [ ] 2.4 Add failing tests for deterministic manifest input/output hashes, logical paths, JSONL uniqueness, repeated regeneration, and CLI output with no training-framework/subprocess side effects; record the expected RED result.

## 3. Implement the Fail-Closed Pack

- [ ] 3.1 Add `src/hermes_skilleval/router_training_data_v2.py` with preflight validation, deterministic candidate construction, qualification checks, and manifest/pack writers.
- [ ] 3.2 Classify non-gold candidates as same-category review candidates or cross-category easy negatives, reserve all source-test rows, and keep every row non-accepted until the pack is qualified.
- [ ] 3.3 Emit the canonical machine truth fields and blocker codes without fabricating reject, family, calibration, or acceptance evidence.
- [ ] 3.4 Add `qualify-router-training-data-v2` to the CLI, ensuring preflight runs before task loading and the command writes only the requested pack directory.
- [ ] 3.5 Run the focused qualification and CLI tests to GREEN and apply scoped Ruff formatting/checks.

## 4. Generate Review Artifacts

- [ ] 4.1 Regenerate `docs/demo/router-training-data-v2-qualification-pack/candidate-pairs.jsonl`, `manifest.json`, and `qualification-report.json` from the canonical non-blind inputs.
- [ ] 4.2 Add the pack README with the exact regeneration command, authority links, artifact roles, current blocked state, and explicit non-claims.
- [ ] 4.3 Add artifact-contract tests that parse all JSON/JSONL, recompute hashes/counts, verify canonical blockers, and reject any trainer-ready output.
- [ ] 4.4 Generate `docs/human-briefs/2026-07-11-build-router-training-data-v2-qualification-pack.html` from the OpenSpec artifacts, pack, diff, and validation evidence.

## 5. Verify and Review

- [ ] 5.1 Run focused tests and the full `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q` suite.
- [ ] 5.2 Run scoped Ruff checks/format checks, `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`, the release reproducibility gate, JSON/JSONL/hash/determinism checks, and `git diff --check`.
- [ ] 5.3 Compare protected Phase 14/15/16 blob identities with the base commit and scan changed paths/output text for blind-source, training, checkpoint, A100/GPU, and unsupported performance claims.
- [ ] 5.4 Start a read-only Reviewer over the complete diff and require `Must Fix`, `Should Fix`, `Nice to Have`, `Re-plan Needed`, and `Final Verdict`.
- [ ] 5.5 If `Re-plan Needed = No`, return only in-scope Must Fix items to the Worker and rerun focused/full verification; if `Re-plan Needed = Yes`, stop and revise the OpenSpec artifacts before further edits.

## 6. Stop at the Local Publication Gate

- [ ] 6.1 Report changed files, candidate/qualified/reserved counts, exact blocker fields, validation results, protected-evidence status, Reviewer verdict, and remaining risks.
- [ ] 6.2 Stop for explicit user confirmation without training, A100/GPU execution, checkpoint creation, blind evaluation, threshold calibration, router promotion, push, PR creation, merge, release, or OpenSpec archive.
