# skillrouter-official-scorer Specification

## Purpose

Define the PR-2 scorer-only SkillRouter official metric parity surface.

## ADDED Requirements

### Requirement: Consume ranked predictions only

The system SHALL score already-ranked SkillRouter predictions without running
routers or models.

#### Scenario: Score local predictions

- **WHEN** a caller provides a validated SkillRouter data root and ranked
  predictions
- **THEN** the scorer MUST consume the provided ranking only
- **AND** it MUST NOT run routers, embeddings, rerankers, model inference,
  training, live agents, or release promotion

### Requirement: Compute official SkillRouter metrics

The system SHALL compute official SkillRouter metrics for eligible tasks.

#### Scenario: Compute per-task metrics

- **WHEN** a task has selected ground-truth IDs and ranked predictions
- **THEN** the scorer MUST compute nDCG@1, nDCG@3, nDCG@10, Hit@1,
  Precision@3, MRR@10, Recall@10, Recall@20, Recall@50,
  FullCoverage@3, FullCoverage@5, and FullCoverage@10
- **AND** nDCG MUST use graded relevance values
- **AND** recall and full coverage MUST use selected ground-truth IDs
- **AND** Hermes Negative Hit Rate MUST NOT be computed unless explicit
  negative labels exist

### Requirement: Apply official task filtering

The system SHALL match SkillRouter official task filtering semantics.

#### Scenario: Filter tasks and relevance

- **WHEN** scoring in core mode
- **THEN** tasks with `task_type == generic_only` MUST be dropped
- **AND** core mode MUST use `core_gt_ids` as-is when the key is present
- **AND** core mode MUST fallback to `gt_skill_ids` only when `core_gt_ids` is
  missing
- **WHEN** scoring in single mode
- **THEN** single mode MUST use `gt_skill_ids` and keep only tasks with exactly
  one GT ID
- **AND** tier relevance MUST be filtered to skills present in the selected
  candidate skill pool tier

### Requirement: Aggregate official slices

The system SHALL aggregate official metrics per selected candidate skill pool
tier.

#### Scenario: Aggregate metrics

- **WHEN** scoring completes for one tier
- **THEN** results MUST include aggregate slices for all, single, and multi
- **AND** Easy/Hard MUST NOT be derived from task difficulty
- **WHEN** scoring produces a combined report
- **THEN** it MUST use `by_tier.easy` and `by_tier.hard`
- **AND** aggregate metrics MUST be arithmetic means over eligible tasks in each
  slice
- **AND** empty slices MUST be represented without fabricated metric values

### Requirement: Provide scorer parity CLI

The system SHALL expose an optional local CLI command for scorer parity.

#### Scenario: Run scorer CLI

- **WHEN** `skilleval external-score --benchmark skillrouter --data-root <root>
  --predictions <predictions> --tier easy --output <out>` is run
- **THEN** it MUST write official scorer JSON
- **AND** `--tiers easy hard` MUST write a combined `by_tier` report
- **AND** it MUST return non-zero for malformed predictions or invalid data
- **AND** it MUST NOT download data or run model/router code
