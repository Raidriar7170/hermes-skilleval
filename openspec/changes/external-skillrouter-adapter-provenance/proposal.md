## Why

v0.3 needs a trustworthy external benchmark ingestion layer before any routing
matrix, scoring parity, or live-agent evidence can be produced. This PR-1
creates the SkillRouter adapter and provenance boundary while keeping scored
labels evaluation-only and avoiding model inference or metric claims.

## What Changes

- Add canonical external benchmark task, skill, validation, and provenance
  structures for SkillRouter-style data.
- Add a SkillRouter adapter that loads tasks, relevance labels, and Easy/Hard
  skill shards from a caller-provided data root.
- Support JSON, JSONL, gzipped JSONL, and shard directories for the tiny
  fixture and future pinned upstream data.
- Preserve upstream optional fields in metadata rather than guessing semantics.
- Validate duplicate IDs, empty queries, missing relevance, missing relevant
  skills in a tier, malformed files, and provenance/hash completeness.
- Add an `external-validate` CLI command that writes a manifest and validation
  summary for an offline fixture or local data root.
- Add tiny offline fixtures and tests only. Do not download or commit full
  external data.
- Do not implement PR-2 scoring, official metrics, scorer parity, router
  inference, training, or threshold selection.

## Capabilities

### New Capabilities

- `external-skillrouter-adapter`: Defines the external SkillRouter adapter,
  canonical records, provenance manifest, validation behavior, tiny fixture,
  and CLI validation surface.

### Modified Capabilities

- None.

## Impact

- Affected code: new `src/hermes_skilleval/external/` modules and a scoped
  `external-validate` subcommand in `src/hermes_skilleval/cli.py`.
- Affected tests: new PR-1 external adapter/CLI tests and small fixture files.
- Affected docs/OpenSpec: PR-1 OpenSpec artifacts and Human Brief.
- No external full datasets, model checkpoints, embedding caches, credentials,
  raw traces, scored-result tuning, PR-2 metrics, or live-agent runtime are in
  scope.
