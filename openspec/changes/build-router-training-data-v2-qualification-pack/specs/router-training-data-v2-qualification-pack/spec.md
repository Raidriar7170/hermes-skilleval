## ADDED Requirements

### Requirement: Qualification uses the canonical non-blind migration universe
The system SHALL build the router-training-data-v2 qualification pack from an explicit non-blind migration-task root and the canonical 16-skill migration index. It MUST reject missing skill references, mixed gold-skill ecosystem categories, duplicate task IDs, and duplicate skill IDs.

#### Scenario: Canonical inputs are accepted
- **WHEN** the command receives `benchmarks/migration-tasks` and the canonical Phase 9 skill index
- **THEN** it uses exactly the loaded non-blind tasks and indexed skills as its candidate universe
- **AND** it records their logical paths and content hashes in the manifest

#### Scenario: Another taxonomy is not silently combined
- **WHEN** task references do not belong to the supplied 16-skill index
- **THEN** qualification fails before artifacts are written
- **AND** the command does not fill the gap from the 45-skill benchmark universe

### Requirement: Blind evaluation data is excluded before prompt loading
The system MUST fail before calling the task-content loader when a resolved task source contains `blind-migration-tasks` or a discovered task directory basename starts with `blind-`. The qualification workflow MUST NOT read, hash, copy, mine, calibrate on, or select against blind prompt content.

#### Scenario: Blind root is supplied
- **WHEN** the task source resolves within `benchmarks/blind-migration-tasks`
- **THEN** the command exits nonzero before reading prompt content
- **AND** no qualification-pack artifact is written

#### Scenario: Blind-like task directory is nested elsewhere
- **WHEN** preflight discovers a task directory whose basename starts with `blind-`
- **THEN** the command exits nonzero before calling `load_tasks()`
- **AND** it does not inspect that directory's prompt content

### Requirement: Candidate construction is deterministic and type-safe
The system SHALL emit one candidate row for every task-skill combination, sorted by task ID and skill ID, with unique stable pair IDs. It MUST distinguish `positive`, `same_category_negative_candidate`, and `cross_category_easy_negative` without describing an unreviewed or cross-category negative as a qualified hard negative.

#### Scenario: Canonical matrix is generated
- **WHEN** the 12 canonical migration tasks and 16 canonical skills are qualified
- **THEN** `candidate-pairs.jsonl` contains exactly 192 sorted unique rows
- **AND** the rows contain 16 positives, 32 same-category negative candidates, and 144 cross-category easy negatives

#### Scenario: Regeneration uses identical inputs
- **WHEN** the command runs twice with byte-identical inputs and policy
- **THEN** the candidate matrix, qualification report, and manifest are byte-identical

### Requirement: Held-out source rows remain reserved
The system MUST preserve the original task split as `source_split` and MUST mark every candidate derived from a source `test` task as reserved rather than train eligible. It SHALL NOT write a trainer-ready `training-pairs.jsonl` while any qualification requirement is unmet.

#### Scenario: Canonical test candidates are emitted
- **WHEN** the canonical source includes four `test` tasks
- **THEN** all 64 task-skill candidate rows from those tasks are marked reserved
- **AND** their 5 positives and 11 same-category negative candidates do not count as train candidates

#### Scenario: Qualification remains incomplete
- **WHEN** one or more required checks fail
- **THEN** `training-pairs.jsonl` is absent
- **AND** `can_start_training` is `false`

### Requirement: Qualification fails closed on evidence gaps
The qualification report SHALL expose machine-readable checks and blocker codes and SHALL set `qualification_status="REVIEW_REQUIRED"`, `router_decision="KEEP_BASELINE"`, and `can_start_training=false` unless all policy requirements pass. Passing requires 100–200 accepted train pairs, positive coverage of every target skill, reviewed same-category negatives, reviewed true reject examples, explicit family-disjoint train/calibration/test membership, prompt/task non-overlap across splits, and hash-bound human acceptance.

#### Scenario: Canonical source is assessed honestly
- **WHEN** the current migration tasks and Phase 9 skill index are qualified without new reviewed metadata
- **THEN** the report remains `REVIEW_REQUIRED` and `can_start_training=false`
- **AND** it records incomplete pair volume and target-skill coverage
- **AND** it includes blockers for unreviewed same-category negatives, missing reject examples, non-independent family splits, missing calibration split, and missing human acceptance

#### Scenario: Cross-category volume reaches the numeric target
- **WHEN** total candidate volume is between 100 and 200 only because cross-category easy negatives are included
- **THEN** those easy negatives do not count toward the accepted train-pair threshold
- **AND** qualification remains blocked

### Requirement: Provenance manifest binds inputs and outputs
The system SHALL write a deterministic manifest containing schema and artifact versions, logical input paths, SHA-256 records for all non-blind task metadata/prompts and the skill index, output hashes for the candidate matrix and qualification report, counts, ordering rules, and explicit non-actions. The manifest MUST NOT contain machine-specific absolute output paths or blind prompt-derived values.

#### Scenario: Manifest hashes verify
- **WHEN** a consumer recomputes every listed input and output SHA-256
- **THEN** each recomputed value matches the manifest
- **AND** the candidate/report counts match the referenced artifacts

#### Scenario: Pack is regenerated in another output directory
- **WHEN** identical logical inputs are used from the same repository snapshot
- **THEN** output-directory location does not change manifest bytes

### Requirement: Qualification has no training or release side effects
The qualification command MUST NOT import model-training frameworks, launch subprocesses, access a GPU/A100, create checkpoints, tune thresholds, rerun evaluation, change router selection, mutate Phase 14/15/16 evidence, push, merge, publish, or archive.

#### Scenario: Local qualification completes
- **WHEN** the command writes the blocked canonical pack
- **THEN** only the requested qualification-pack directory is written by the command
- **AND** historical evidence retains its original blob identity
- **AND** the workflow stops for user review before any publication or training action

### Requirement: Human-facing documentation does not replace evidence
The pack README and Chinese Human Brief SHALL link to the OpenSpec artifacts, JSON/JSONL outputs, tests, and validation evidence as authoritative sources. They MUST state the current readiness, remaining blockers, and excluded claims without presenting the candidate matrix as accepted training data.

#### Scenario: Reviewer opens the Human Brief
- **WHEN** the completed apply is summarized for human review
- **THEN** the brief shows `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`
- **AND** it states that no model training, blind rerun, A100 job, checkpoint, benchmark gain, merge, or release occurred
