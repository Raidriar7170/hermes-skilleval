## ADDED Requirements

### Requirement: Qualification uses the canonical non-blind migration universe
The system SHALL build the router-training-data-v2 qualification pack from an explicit non-blind migration-task root and the canonical 16-skill migration index. It MUST reject missing skill references, mixed gold-skill ecosystem categories, duplicate task IDs, duplicate skill IDs, and task or skill IDs containing `/`.

#### Scenario: Canonical inputs are accepted
- **WHEN** the command receives `benchmarks/migration-tasks` and the canonical Phase 9 skill index
- **THEN** it uses exactly the loaded non-blind tasks and indexed skills as its candidate universe
- **AND** it records their logical paths and content hashes in the manifest

#### Scenario: Another taxonomy is not silently combined
- **WHEN** task references do not belong to the supplied 16-skill index
- **THEN** qualification fails before artifacts are written
- **AND** the command does not fill the gap from the 45-skill benchmark universe

### Requirement: Blind evaluation data is excluded before prompt loading
The system MUST resolve the task root, every discovered task directory, and every `task.yaml` / `prompt.md` file before calling the task-content loader. It MUST fail when a real path contains `blind-migration-tasks`, a task-directory basename starts with `blind-`, or the `id` read from task metadata starts with `blind-`. The qualification workflow MUST NOT read, hash, copy, mine, calibrate on, or select against blind prompt content.

#### Scenario: Blind root is supplied
- **WHEN** the task source resolves within `benchmarks/blind-migration-tasks`
- **THEN** the command exits nonzero before reading prompt content
- **AND** no qualification-pack artifact is written

#### Scenario: Blind-like task directory is nested elsewhere
- **WHEN** preflight discovers a task directory whose basename starts with `blind-`
- **THEN** the command exits nonzero before calling `load_tasks()`
- **AND** it does not inspect that directory's prompt content

#### Scenario: Ordinary symlink resolves into the blind root
- **WHEN** a normally named source, task directory, metadata file, or prompt file resolves within `benchmarks/blind-migration-tasks`
- **THEN** the command exits nonzero during preflight
- **AND** it does not call the task-content loader

#### Scenario: Metadata carries a blind identity
- **WHEN** a normally named task directory has a `task.yaml` ID beginning `blind-`
- **THEN** metadata preflight exits nonzero before reading `prompt.md`

### Requirement: Candidate construction is deterministic and type-safe
The system SHALL emit one `router-training-data-v2-candidate-v1` row for every task-skill combination, sorted by task ID and skill ID, with unique `<task-id>/<skill-id>` pair IDs. `prompt_text_sha256` MUST hash the UTF-8 normalized loaded prompt while manifest file hashes cover raw bytes. It MUST distinguish `positive`, `same_category_negative_candidate`, and `cross_category_easy_negative` without describing an unreviewed or cross-category negative as a qualified hard negative.

#### Scenario: Canonical matrix is generated
- **WHEN** the 12 canonical migration tasks and 16 canonical skills are qualified
- **THEN** `candidate-pairs.jsonl` contains exactly 192 sorted unique rows
- **AND** the rows contain 16 positives, 32 same-category negative candidates, and 144 cross-category easy negatives

#### Scenario: Regeneration uses identical inputs
- **WHEN** the command runs twice with byte-identical inputs and policy
- **THEN** the candidate matrix, qualification report, and manifest are byte-identical

### Requirement: Held-out source rows remain reserved
The system MUST preserve the original task split as `source_split`. It MUST use `TRAIN_CANDIDATE_POSITIVE`, `REVIEW_REQUIRED_NEGATIVE_CANDIDATE`, and `EXCLUDED_EASY_NEGATIVE` for the three `dev` dispositions and MUST mark every candidate derived from a source `test` task as `RESERVED_SOURCE_TEST`. Every row MUST set `accepted_for_training=false`, and version 1 MUST NOT write a trainer-ready `training-pairs.jsonl`.

#### Scenario: Canonical test candidates are emitted
- **WHEN** the canonical source includes four `test` tasks
- **THEN** all 64 task-skill candidate rows from those tasks are marked reserved
- **AND** their 5 positives and 11 same-category negative candidates do not count as train candidates

#### Scenario: Qualification remains incomplete
- **WHEN** version 1 writes any diagnostic pack
- **THEN** `training-pairs.jsonl` is absent
- **AND** `can_start_training` is `false`

### Requirement: Qualification fails closed on evidence gaps
The version 1 diagnostic report SHALL expose machine-readable checks and blocker codes and SHALL always set `qualification_status="REVIEW_REQUIRED"`, `router_decision="KEEP_BASELINE"`, and `can_start_training=false`. It SHALL NOT accept or infer reviewed-negative, true-reject, task-family, calibration-membership, or human-acceptance evidence. A future change is required before the system can authorize training.

#### Scenario: Canonical source is assessed honestly
- **WHEN** the current migration tasks and Phase 9 skill index are qualified without new reviewed metadata
- **THEN** the report remains `REVIEW_REQUIRED` and `can_start_training=false`
- **AND** it records incomplete pair volume and target-skill coverage
- **AND** it records 28 source pairs, 192 matrix candidates, 32 train-policy candidates, 0 accepted train pairs, 64 reserved matrix rows, 11/16 train-positive skill coverage, and 0 reject examples
- **AND** its sorted blocker codes are exactly `INDEPENDENT_CALIBRATION_SPLIT_MISSING`, `MANUAL_ACCEPTANCE_MISSING`, `PAIR_COUNT_BELOW_MINIMUM`, `REJECT_EXAMPLES_MISSING`, `SAME_CATEGORY_NEGATIVES_UNREVIEWED`, `TARGET_POSITIVE_COVERAGE_INCOMPLETE`, `TASK_FAMILY_METADATA_MISSING`, and `TASK_FAMILY_SPLIT_NOT_INDEPENDENT`

#### Scenario: Cross-category volume reaches the numeric target
- **WHEN** total candidate volume is between 100 and 200 only because cross-category easy negatives are included
- **THEN** those easy negatives do not count toward the accepted train-pair threshold
- **AND** qualification remains blocked

### Requirement: Provenance manifest binds inputs and outputs
The system SHALL write a deterministic manifest containing `policy_id="router-training-data-v2-qualification-v1"`, schema and artifact versions, repository-relative logical input paths, SHA-256 records for all non-blind task metadata/prompts and the skill index, output hashes for the candidate matrix and qualification report, counts, ordering rules, and explicit non-actions. The manifest MUST NOT contain machine-specific absolute output paths or blind prompt-derived values, and version 1 MUST reject inputs outside the discovered repository root.

#### Scenario: Manifest hashes verify
- **WHEN** a consumer recomputes every listed input and output SHA-256
- **THEN** each recomputed value matches the manifest
- **AND** the candidate/report counts match the referenced artifacts

#### Scenario: Pack is regenerated in another output directory
- **WHEN** identical logical inputs are used from the same repository snapshot
- **THEN** output-directory location does not change manifest bytes

### Requirement: Pack publication protects historical and stale outputs
The command MUST resolve the absent output target with `Path.resolve(strict=False)` so existing symlink ancestors are resolved, then reject the real target when it lies within or contains any resolved Phase 14, 15, 16, 17, or 18 protected demo directory. It SHALL write a complete pack to a fresh temporary sibling under the resolved safe parent and atomically rename it to the resolved target, removing temporary output after failure. Only the requested pack SHALL remain as persistent output.

#### Scenario: Existing target contains stale training data
- **WHEN** the requested output directory already exists with `training-pairs.jsonl` or any other entry
- **THEN** the command exits nonzero without modifying that directory

#### Scenario: Protected output target is requested
- **WHEN** the requested output path overlaps a protected Phase 14/15/16/17/18 demo directory in either direction
- **THEN** the command exits nonzero before writing any file

#### Scenario: Symlink ancestor redirects into protected evidence
- **WHEN** an absent normally named target has an existing symlink ancestor that resolves into a protected Phase 14/15/16/17/18 directory
- **THEN** resolved-path validation exits nonzero before creating the temporary sibling

#### Scenario: Fresh output target is published
- **WHEN** all artifacts are built successfully for an absent non-protected target
- **THEN** the complete temporary sibling is atomically renamed to that target
- **AND** no persistent partial directory remains

### Requirement: Qualification has no training or release side effects
The qualification command MUST NOT import model-training frameworks, launch subprocesses, access a GPU/A100, create checkpoints, tune thresholds, rerun evaluation, change router selection, mutate Phase 14/15/16/17/18 evidence, push, merge, publish, or archive.

#### Scenario: Local qualification completes
- **WHEN** the command writes the blocked canonical pack
- **THEN** only the requested qualification-pack directory is written by the command
- **AND** historical evidence retains its original blob identity
- **AND** the workflow stops for user review before any publication or training action

### Requirement: Human-facing documentation does not replace evidence
The pack README and Chinese Human Brief SHALL link to the OpenSpec artifacts, JSON/JSONL outputs, tests, and validation evidence as authoritative sources. They MUST state the current readiness, remaining blockers, and excluded claims without presenting the candidate matrix as accepted training data. The README regeneration command MUST write to a fresh temporary target and compare bytes/hashes with the committed pack instead of attempting to overwrite it.

#### Scenario: Reviewer opens the Human Brief
- **WHEN** the completed apply is summarized for human review
- **THEN** the brief shows `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`
- **AND** it states that no model training, blind rerun, A100 job, checkpoint, benchmark gain, merge, or release occurred
