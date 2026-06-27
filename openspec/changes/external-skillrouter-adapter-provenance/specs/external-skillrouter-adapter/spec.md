# external-skillrouter-adapter Specification

## Purpose

Define the PR-1 external SkillRouter adapter and provenance surface for v0.3
without implementing scoring, model inference, or release decisions.

## ADDED Requirements

### Requirement: Provide canonical external records

The system SHALL expose canonical external task and skill records for
SkillRouter-style benchmark data.

#### Scenario: Load canonical records

- **WHEN** a caller loads a valid SkillRouter data root
- **THEN** each task MUST have benchmark ID, task ID, query, task type, graded
  relevance mapping, and metadata
- **AND** task query text MUST accept real SkillRouter `instruction_text`
- **AND** each skill MUST have benchmark ID, skill ID, name, description, body,
  source, tier, and metadata
- **AND** `difficulty`, `num_skills`, `skill_names`, `domain`, `excluded`, and
  other unknown upstream fields MUST be preserved in metadata
- **AND** loading MUST NOT require model inference or scoring

### Requirement: Stream SkillRouter skill shards

The system SHALL read SkillRouter skill shards from local files without
requiring full external data in Git.

#### Scenario: Iterate skills by tier

- **WHEN** a caller iterates skills for `easy` or `hard`
- **THEN** the adapter MUST support official top-level tier directories such as
  `<data_root>/easy/` and `<data_root>/hard/`
- **AND** it MUST support JSONL, gzipped JSONL, and shard directories
- **AND** iteration SHOULD stream records rather than requiring all full bodies
  to be loaded into a list first
- **AND** missing tier files MUST fail with an actionable validation error

### Requirement: Validate external data integrity

The system SHALL validate external data before future scoring PRs can use it.

#### Scenario: Validate a data root

- **WHEN** validation runs on a data root
- **THEN** it MUST detect duplicate task IDs, duplicate skill IDs per tier,
  empty `instruction_text`, missing relevance entries, malformed
  JSON/JSONL/gzip, missing tier directories, and missing scored ground-truth
  skill IDs in the task tier
- **AND** it MUST support real `relevance.json` objects keyed by `task_id`,
  including `gt_skill_ids`, `core_gt_ids`, `auxiliary_gt_ids`, `relevance`, and
  `task_type`
- **AND** it MUST preserve graded relevance mappings without computing metrics
- **AND** it MUST return structured errors without silently skipping affected
  tasks
- **AND** it MUST NOT compute official metrics or Hermes negative-hit metrics

### Requirement: Record provenance manifest

The system SHALL record input provenance for the external adapter.

#### Scenario: Write provenance

- **WHEN** validation succeeds or fails
- **THEN** the output manifest MUST include adapter name/version, benchmark ID,
  upstream repo/ref, license note, acquisition date when supplied, adapter
  mapping, input file SHA-256 hashes, generated timestamp, and validation status
- **AND** file hashes MUST be content hashes rather than path-only records
- **AND** hashes MUST include `tasks.jsonl`, `relevance.json`, `manifest.json`
  when present, and all tier shard files
- **AND** sensitive values, credentials, private host details, and raw auth
  material MUST NOT be written

### Requirement: Provide external validation CLI

The system SHALL provide a CLI command for local external data validation.

#### Scenario: Run external-validate

- **WHEN** `skilleval external-validate --benchmark skillrouter --data-root
  <root> --output-dir <out> --upstream-ref <ref> --license-note <note>` is run
- **THEN** it MUST write `manifest.json` and `validation.json`
- **AND** it MUST return zero when validation passes
- **AND** it MUST return non-zero when validation fails
- **AND** it MUST return non-zero when required provenance metadata is left as
  an unset placeholder
- **AND** it MUST not download data, train models, run routers, or score
  predictions

### Requirement: Keep CI fixture small and offline

The system SHALL test the adapter with tiny committed fixtures only.

#### Scenario: Run PR-1 tests

- **WHEN** the test suite runs in CI
- **THEN** it MUST use only small local fixtures, including an official-shaped
  `skillrouter_eval_core_tiny` fixture
- **AND** it MUST NOT require network, GPU, sentence-transformers, full
  SkillRouter corpora, model weights, embedding caches, credentials, or raw
  external traces
