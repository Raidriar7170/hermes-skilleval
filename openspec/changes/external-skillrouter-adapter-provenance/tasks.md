## 1. OpenSpec And Scope

- [x] 1.1 Create change `external-skillrouter-adapter-provenance`.
- [x] 1.2 Add proposal, design, tasks, and `external-skillrouter-adapter` spec.
- [x] 1.3 Keep PR-1 limited to adapter/provenance/validation; do not implement
  PR-2 scoring or model inference.

## 2. Tests And Fixtures

- [x] 2.1 Add tiny SkillRouter fixture under `tests/fixtures/external/`.
- [x] 2.2 Add failing tests for canonical task/skill loading and metadata
  preservation.
- [x] 2.3 Add failing tests for JSONL, gzipped JSONL, and shard directory
  loading.
- [x] 2.4 Add failing tests for duplicate IDs, empty query, missing relevance,
  malformed gzip/JSONL, and relevant skill missing from tier.
- [x] 2.5 Add failing CLI smoke tests for `external-validate` success and
  validation failure.
- [x] 2.6 Add official-shaped tiny Eval Core fixture covering
  `instruction_text`, object-shaped `relevance.json`, top-level `easy/` and
  `hard/` gzipped shards, `generic_only`, single-skill, and multi-skill tasks.

## 3. Implementation

- [x] 3.1 Add `src/hermes_skilleval/external/` package with canonical records
  and adapter protocol.
- [x] 3.2 Implement SkillRouter adapter load/iterate/validate/provenance.
- [x] 3.3 Implement SHA-256 input file hashing and sanitized manifests.
- [x] 3.4 Add `external-validate` CLI command that writes `manifest.json` and
  `validation.json`.
- [x] 3.5 Ensure validation does not compute metrics, run routers, download
  data, or load models.
- [x] 3.6 Support real SkillRouter Eval Core task/relevance/tier layout while
  preserving PR-1 as adapter/provenance/validation only.

## 4. Documentation And Human Brief

- [x] 4.1 Add a concise Chinese Human Brief for PR-1.
- [x] 4.2 Document that PR-1 produces adapter/provenance evidence only, not
  benchmark results.

## 5. Validation

- [x] 5.1 Run focused RED/GREEN tests for new external adapter behavior.
- [x] 5.2 Run `python -m pytest -q`.
- [x] 5.3 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 5.4 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check --phase17-output-dir docs/demo/phase17-calibrated-release-selector --release-output-dir docs/demo/phase18-ci-release-reproducibility`.
- [x] 5.5 Run `git diff --check`.
- [x] 5.6 Confirm no full external data, model weights, embedding caches,
  credentials, raw traces, PR-2 scoring, or live-agent runtime entered the diff.
