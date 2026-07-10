## 1. Freeze the Approved Boundary

- [x] 1.1 Record `pwd`, branch, clean status, apply base `aec4a09e7a60a5a1eb534b4198078acc24ff5cd5`, canonical input hashes/counts, and protected Phase 14/15/16/17/18 blob identities in the isolated Worker worktree.
- [x] 1.2 Confirm the canonical inputs remain 12 non-blind migration tasks and 16 Phase 9 skills; stop and re-plan if the skill universe, source counts, or protected evidence changed.
- [x] 1.3 Confirm the implementation scope excludes the 45-skill benchmark, blind prompt content/hashes, external evaluation-only sets, training, A100/GPU work, checkpoints, calibration, model selection, publication, merge, and archive actions.

## 2. Add Qualification Tests First

- [x] 2.1 Add failing unit tests for root/directory/file symlink resolution and `blind-*` directory/metadata preflight before prompt loading, duplicate/missing identities, mixed gold ecosystem categories, and slash-bearing IDs; record the expected RED result.
- [x] 2.2 Add failing unit tests for the exact candidate-row schema, deterministic ordering/IDs, normalized prompt hashes, candidate classification, four dispositions, and exact 192/16/32/144 canonical counts; record the expected RED result.
- [x] 2.3 Add failing unit tests for 32 train-policy vs 0 accepted pairs, 64 reserved rows, 11/16 positive coverage, the exact eight canonical blockers, `REVIEW_REQUIRED`, `KEEP_BASELINE`, `can_start_training=false`, and absent `training-pairs.jsonl`; record the expected RED result.
- [x] 2.4 Add failing tests for resolved protected/existing output rejection including symlink ancestors, safe-parent atomic publication/cleanup, deterministic manifest policy/input/output hashes, repository-relative logical paths, JSONL uniqueness, repeated regeneration, and CLI output with no training-framework/subprocess side effects; record the expected RED result.

## 3. Implement the Fail-Closed Pack

- [x] 3.1 Add `src/hermes_skilleval/router_training_data_v2.py` with preflight validation, deterministic candidate construction, qualification checks, and manifest/pack writers.
- [x] 3.2 Classify non-gold candidates as same-category review candidates or cross-category easy negatives, reserve all source-test rows, and keep every version 1 row non-accepted.
- [x] 3.3 Emit the canonical counts and exact eight blocker codes without accepting or fabricating reject, family, calibration, reviewed-negative, or human-acceptance evidence.
- [x] 3.4 Add `qualify-router-training-data-v2` to the CLI, ensuring preflight runs before task loading and only the requested pack remains as persistent output.
- [x] 3.5 Run the focused qualification and CLI tests to GREEN and apply scoped Ruff formatting/checks.

## 4. Generate Review Artifacts

- [x] 4.1 Regenerate `docs/demo/router-training-data-v2-qualification-pack/candidate-pairs.jsonl`, `manifest.json`, and `qualification-report.json` from the canonical non-blind inputs.
- [x] 4.2 Add the pack README with a fresh-temporary-target regeneration and byte/hash comparison command, authority links, artifact roles, current blocked state, and explicit non-claims.
- [x] 4.3 Add artifact-contract tests that parse all JSON/JSONL, recompute hashes/counts, verify canonical blockers, and reject any trainer-ready output.
- [ ] 4.4 Generate `docs/human-briefs/2026-07-11-build-router-training-data-v2-qualification-pack.html` from the OpenSpec artifacts, pack, diff, and validation evidence.

## 5. Verify and Review

- [ ] 5.1 Run focused tests and the full `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q` suite.
- [ ] 5.2 Run scoped Ruff checks/format checks, `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`, the release reproducibility gate, JSON/JSONL/hash/determinism checks, and `git diff --check`.
- [ ] 5.3 Compare protected Phase 14/15/16/17/18 blob identities with apply base `aec4a09e7a60a5a1eb534b4198078acc24ff5cd5` and scan changed paths/output text for blind-source, training, checkpoint, A100/GPU, and unsupported performance claims.
- [ ] 5.4 Start a read-only Reviewer over the complete diff and require `Must Fix`, `Should Fix`, `Nice to Have`, `Re-plan Needed`, and `Final Verdict`.
- [ ] 5.5 If `Re-plan Needed = No`, return only in-scope Must Fix items to the Worker and rerun focused/full verification; if `Re-plan Needed = Yes`, stop and revise the OpenSpec artifacts before further edits.

## 6. Stop at the Local Publication Gate

- [ ] 6.1 Report changed files, candidate/qualified/reserved counts, exact blocker fields, validation results, protected-evidence status, Reviewer verdict, and remaining risks.
- [ ] 6.2 Stop for explicit user confirmation without training, A100/GPU execution, checkpoint creation, blind evaluation, threshold calibration, router promotion, push, PR creation, merge, release, or OpenSpec archive.
