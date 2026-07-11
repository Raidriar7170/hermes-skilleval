## Why

The current embedding-router training export contains only 28 task-skill pairs, while the held-out Phase 16 run preserved Recall@5 but increased Negative Hit Rate and remained `REVIEW_REQUIRED` / `KEEP_BASELINE`. Before any retraining, the repository needs a deterministic qualification surface that separates usable in-domain evidence from easy negatives and makes missing reject, family, calibration, and coverage evidence block training rather than being silently inferred.

## What Changes

- Add a deterministic router-training-data-v2 qualification pack for the existing 16-skill migration-router universe, built only from `benchmarks/migration-tasks` and the canonical Phase 9 skill index.
- Export a closed-world candidate-pair matrix that distinguishes positives, unreviewed same-category negative candidates, and cross-category easy negatives without fabricating prompts or treating either negative class as qualified hard negatives.
- Add a diagnostic-only, fail-closed qualification report and hash-backed manifest covering input identity, deterministic ordering, pair/schema integrity, prompt-hash split leakage, skill-universe membership, candidate/accepted pair volume, reject coverage, explicit family metadata, independent train/calibration/test splits, and train-positive skill coverage.
- Commit an auditable demo pack under `docs/demo/router-training-data-v2-qualification-pack/` with a regeneration README, `candidate-pairs.jsonl`, `manifest.json`, and `qualification-report.json`.
- Preserve `benchmarks/blind-migration-tasks/**` and all Phase 14/15/16/17/18 evidence as immutable exclusions. A resolved blind source path/file, `blind-*` task-directory or metadata identity, protected output target, or protected-evidence mutation fails closed before prompt loading or pack publication.
- Record the canonical snapshot honestly as `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`. Version 1 is deliberately a diagnostic snapshot and has no acceptance/reject/family/calibration input schema, so it cannot authorize training; a later scoped change must add and validate those reviewed evidence types.
- Publish only into a new output whose resolved real path is non-protected, using a temporary sibling under the same resolved safe parent and an atomic rename. Reject an existing target so stale trainer-ready files cannot survive regeneration.
- Exclude model training, checkpoint creation, A100/GPU execution, threshold calibration, model selection, blind evaluation reruns, router promotion, release publication, merge, and archive actions.

## Capabilities

### New Capabilities

- `router-training-data-v2-qualification-pack`: Defines deterministic candidate construction, provenance, qualification gates, blind-data exclusion, blocked readiness semantics, and committed review artifacts for the current migration-router training-data universe.

### Modified Capabilities

None.

## Impact

- Runtime and CLI: a small qualification-pack builder and one offline CLI entry point using existing task and skill-index loaders.
- Artifacts: one JSONL candidate matrix, one manifest, one qualification report, one concise regeneration README, and one Chinese Human Brief.
- Tests: deterministic regeneration, candidate classification/counts, fail-closed gate behavior, path/task denylisting, prompt-hash leakage, manifest hashing, CLI smoke coverage, and protected-evidence identity checks.
- Dependencies and external systems: no new runtime dependency, network access, GPU, A100, model checkpoint, training job, or blind benchmark access is required.
