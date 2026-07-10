## ADDED Requirements

### Requirement: Generate frozen evaluation plans

The system SHALL generate a frozen external evaluation plan before producing
any scored external matrix report.

#### Scenario: Plan records frozen inputs

- **WHEN** a caller creates an external matrix plan
- **THEN** the plan MUST record the run ID, seed, git commit, dirty-state
  summary, benchmark ID, data root provenance, upstream reference, license
  note, frozen router configs, field views, tiers, candidate subset sizes, and
  output paths
- **AND** each frozen router config MUST include a unique `config_id` plus
  prediction file size and SHA-256 metadata
- **AND** bootstrap confidence interval iteration count and confidence level
  MUST be frozen in the plan
- **AND** the plan MUST be written before any scored matrix output is written

#### Scenario: Matrix requires existing plan

- **WHEN** a caller runs a scored external matrix
- **THEN** the runner MUST consume an existing frozen plan
- **AND** it MUST fail closed if prediction file hashes differ from the plan
- **AND** it MUST fail closed if adapter data file hashes differ from the plan
- **AND** it MUST fail closed if a requested output path differs from the
  frozen matrix output path recorded in the plan
- **AND** it MUST NOT rewrite router IDs, thresholds, prediction paths, field
  views, tiers, or scoring dimensions from scored-label results

### Requirement: Compare frozen prediction inputs only

The system SHALL compare only frozen routers/configs represented by
preregistered ranked prediction inputs.

#### Scenario: Run frozen router matrix

- **WHEN** the matrix runner evaluates frozen router configs
- **THEN** each config MUST identify a router ID, field view, prediction file,
  unique config ID, top-k or threshold metadata when present, and version
  metadata
- **AND** the runner MUST NOT train, tune thresholds, mine hard negatives, run
  embeddings, run rerankers, run model inference, run live agents, promote
  routers, or promote release artifacts

### Requirement: Build deterministic field views

The system SHALL build deterministic skill text views for name-only, metadata,
and full-body comparisons.

#### Scenario: Build skill field views

- **WHEN** the matrix prepares candidate skill text
- **THEN** `name_only` MUST contain only the skill name
- **AND** `metadata` MUST contain the skill name plus description metadata
- **AND** `full_body` MUST contain skill name, description metadata, and body
  text
- **AND** each view builder MUST be versioned in the frozen plan or report

### Requirement: Produce official SkillRouter scores and Hermes diagnostics

The system SHALL keep official SkillRouter scoring separate from Hermes
diagnostics.

#### Scenario: Score full Easy and Hard tiers

- **WHEN** a matrix plan includes SkillRouter Easy and Hard tiers
- **THEN** the runner MUST invoke the PR-2 official scorer for each frozen
  router/config and tier
- **AND** official reports MUST include Easy and Hard scoring over full tier
  candidate pools
- **AND** official reports MUST be keyed by frozen `config_id`, while
  preserving `router_id` and `field_view` inside each report
- **AND** missing task predictions MUST follow PR-2 scorer parity semantics

#### Scenario: Emit stress diagnostics separately

- **WHEN** the matrix computes candidate-pool stress checks
- **THEN** stress results MUST be written under a Hermes diagnostics namespace
- **AND** stress subsets MUST NOT be described as official SkillRouter results
- **AND** Hermes Negative Hit Rate MUST NOT be calculated for SkillRouter
  unless explicit negative labels exist

### Requirement: Sample deterministic candidate subsets

The system SHALL produce deterministic candidate subsets for Hermes stress
diagnostics.

#### Scenario: Build candidate subset

- **WHEN** a candidate subset target size is requested
- **THEN** the subset MUST include all unique selected GT skill IDs before any
  distractors
- **AND** distractors MUST be selected by sorting remaining skill IDs by
  `sha256("20260625:" + skill_id)`
- **AND** the subset MUST record the selected candidate hash and sampling seed

#### Scenario: Target smaller than GT union

- **WHEN** the requested subset size is smaller than the unique selected GT
  skill count
- **THEN** the subset result MUST be field-level `UNAVAILABLE`
- **AND** it MUST include a reason

### Requirement: Compute paired bootstrap confidence intervals

The system SHALL compute deterministic paired bootstrap confidence intervals
for frozen router comparisons.

#### Scenario: Bootstrap paired deltas

- **WHEN** two frozen router reports share eligible task-level metric rows
- **THEN** the confidence interval MUST sample paired task-level metric deltas
  with seed `20260625`
- **AND** it MUST report point estimate, lower bound, upper bound, confidence
  level, iteration count, metric name, and paired task count

### Requirement: Generate leakage and split diagnostics

The system SHALL generate held-out-skill and held-out-source diagnostics for
external matrix evidence.

#### Scenario: Held-out-skill connected components

- **WHEN** tasks and selected GT skills are available
- **THEN** held-out-skill split generation MUST use connected components over
  task-to-selected-GT-skill edges
- **AND** it MUST report component IDs, task IDs, skill IDs, split assignment,
  and overlap assertions

#### Scenario: Held-out-source unavailable

- **WHEN** source metadata is missing or insufficient for a held-out-source
  split
- **THEN** the held-out-source result MUST be field-level `UNAVAILABLE`
- **AND** it MUST include a reason

### Requirement: Scaffold SkillRouter and SkillsBench overlap reports

The system SHALL provide a deterministic overlap report scaffold between
SkillRouter tasks and future SkillsBench live tasks.

#### Scenario: Create overlap scaffold

- **WHEN** SkillRouter tasks are available and SkillsBench live tasks are not
  selected yet
- **THEN** the overlap report MUST still include schema version, source counts,
  exact ID overlap, normalized text hash overlap, and a high-similarity
  diagnostics placeholder
- **AND** unavailable live-task inputs MUST be represented as field-level
  `UNAVAILABLE` with a reason
