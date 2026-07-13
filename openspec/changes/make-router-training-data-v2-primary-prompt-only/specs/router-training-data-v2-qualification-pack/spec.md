## MODIFIED Requirements

### Requirement: Candidate construction is deterministic and type-safe
The system SHALL emit one `router-training-data-v2-candidate-v2` row for every task-skill combination, sorted by task ID and skill ID, with unique `<task-id>/<skill-id>` pair IDs. Every row MUST set `query_text` to the loader-normalized `task.prompt` byte-for-byte, set `query_text_policy="prompt_only"`, and set `prompt_text_sha256` to the SHA-256 of the UTF-8 bytes of that exact `query_text`. Task ID, category, difficulty, and robustness tags MAY be used only as structured validation, classification, split, or provenance inputs and MUST NOT be concatenated, serialized, or otherwise encoded into the primary query. Category MAY continue to distinguish same-category from cross-category candidates. The row MUST NOT expose a legacy, alternate, composite, or second query representation. Manifest file hashes SHALL continue to cover raw input bytes. The system MUST distinguish `positive`, `same_category_negative_candidate`, and `cross_category_easy_negative` without describing an unreviewed or cross-category negative as a qualified hard negative.

#### Scenario: Canonical v2 matrix is generated
- **WHEN** the 12 canonical migration tasks and 16 canonical skills are qualified
- **THEN** `candidate-pairs.jsonl` contains exactly 192 sorted unique `router-training-data-v2-candidate-v2` rows
- **AND** every row sets `query_text_policy="prompt_only"`
- **AND** the rows contain 16 positives, 32 same-category negative candidates, and 144 cross-category easy negatives

#### Scenario: Primary query equals the loaded prompt
- **WHEN** a task is loaded and candidates are constructed for it
- **THEN** each candidate's `query_text` equals the loader-normalized `task.prompt` byte-for-byte
- **AND** recomputing SHA-256 over the UTF-8 bytes of `query_text` equals `prompt_text_sha256`

#### Scenario: Benchmark metadata changes while prompt stays fixed
- **WHEN** task ID, category, difficulty, or robustness tags change in valid isolated fixtures while the loader-normalized prompt remains byte-identical
- **THEN** candidate `query_text` remains byte-identical
- **AND** `prompt_text_sha256` remains identical
- **AND** none of those metadata values is added to a primary query representation

#### Scenario: No dual or composite query is emitted
- **WHEN** a v2 candidate row is serialized
- **THEN** `query_text` is its only primary-query text field
- **AND** the row contains no legacy, alternate, metadata-enriched, or composite query field

#### Scenario: V2 regeneration uses identical inputs
- **WHEN** the command runs twice with byte-identical inputs and the v2 policy
- **THEN** the candidate matrix, qualification report, and manifest are byte-identical

### Requirement: Held-out source rows remain reserved
The system MUST preserve the original task split as `source_split`. It MUST use `TRAIN_CANDIDATE_POSITIVE`, `REVIEW_REQUIRED_NEGATIVE_CANDIDATE`, and `EXCLUDED_EASY_NEGATIVE` for the three `dev` dispositions and MUST mark every candidate derived from a source `test` task as `RESERVED_SOURCE_TEST`. Every row MUST set `accepted_for_training=false`, and version 2 MUST NOT write `training-pairs.jsonl`, `training-pairs-v2.jsonl`, or another trainer-ready pair file.

#### Scenario: Canonical test candidates are emitted
- **WHEN** the canonical source includes four `test` tasks
- **THEN** all 64 task-skill candidate rows from those tasks are marked reserved
- **AND** their 5 positives and 11 same-category negative candidates do not count as train candidates

#### Scenario: V2 qualification remains incomplete
- **WHEN** version 2 writes any diagnostic pack
- **THEN** `training-pairs.jsonl` and `training-pairs-v2.jsonl` are absent
- **AND** `can_start_training` is `false`

### Requirement: Qualification fails closed on evidence gaps
The version 2 diagnostic report SHALL use `schema_version="router-training-data-v2-qualification-report-v2"` and `policy_id="router-training-data-v2-qualification-v2"`. It SHALL expose the machine-readable prompt-only query contract, checks, and blocker codes and SHALL always set `qualification_status="REVIEW_REQUIRED"`, `router_decision="KEEP_BASELINE"`, and `can_start_training=false`. The query contract MUST identify `query_text` as the sole primary query field, `task.prompt` as its source, loader normalization, `prompt_text_sha256` as the SHA-256 binding, task ID/category/difficulty/robustness tags as forbidden primary-query inputs, and an empty alternate-query-field list. The report SHALL NOT accept or infer reviewed-negative, true-reject, task-family, calibration-membership, or human-acceptance evidence. A future change is required before the system can authorize training.

#### Scenario: Canonical source is assessed honestly under v2
- **WHEN** the current migration tasks and Phase 9 skill index are qualified without new reviewed metadata
- **THEN** the report remains `REVIEW_REQUIRED` and `can_start_training=false`
- **AND** it records incomplete pair volume and target-skill coverage
- **AND** it records 28 source pairs, 192 matrix candidates, 16 positives, 32 same-category negative candidates, 144 cross-category easy negatives, 32 train-policy candidates, 0 accepted train pairs, 64 reserved matrix rows, 11/16 train-positive skill coverage, and 0 reject examples
- **AND** its sorted blocker codes are exactly `INDEPENDENT_CALIBRATION_SPLIT_MISSING`, `MANUAL_ACCEPTANCE_MISSING`, `PAIR_COUNT_BELOW_MINIMUM`, `REJECT_EXAMPLES_MISSING`, `SAME_CATEGORY_NEGATIVES_UNREVIEWED`, `TARGET_POSITIVE_COVERAGE_INCOMPLETE`, `TASK_FAMILY_METADATA_MISSING`, and `TASK_FAMILY_SPLIT_NOT_INDEPENDENT`

#### Scenario: Report exposes the v2 query contract
- **WHEN** a qualification report is written
- **THEN** its machine-readable query contract declares `prompt_only`, `query_text`, `task.prompt`, loader normalization, SHA-256 binding through `prompt_text_sha256`, the four forbidden metadata inputs, and no alternate query fields
- **AND** its policy and schema identifiers are the v2 identifiers

#### Scenario: Cross-category volume reaches the numeric target
- **WHEN** total candidate volume is between 100 and 200 only because cross-category easy negatives are included
- **THEN** those easy negatives do not count toward the accepted train-pair threshold
- **AND** qualification remains blocked

### Requirement: Provenance manifest binds inputs and outputs
The system SHALL write a deterministic `router-training-data-v2-manifest-v2` manifest with `artifact_version=2` and `policy_id="router-training-data-v2-qualification-v2"`. It SHALL contain the same machine-readable prompt-only query contract as the qualification report, repository-relative logical input paths, SHA-256 records for all non-blind task metadata/prompts and the skill index, output hashes for the candidate matrix and qualification report, counts, ordering rules, and explicit non-actions. The query contract MUST identify `query_text` as the sole primary query field, `task.prompt` as its loader-normalized source, `prompt_text_sha256` as its SHA-256 binding, task ID/category/difficulty/robustness tags as forbidden primary-query inputs, and no alternate query fields. The manifest MUST NOT contain machine-specific absolute output paths or blind prompt-derived values, and version 2 MUST reject inputs outside the discovered repository root.

#### Scenario: V2 manifest hashes verify
- **WHEN** a consumer recomputes every listed input and output SHA-256
- **THEN** each recomputed value matches the manifest
- **AND** the candidate/report counts match the referenced artifacts
- **AND** the manifest and report contain identical prompt-only query contracts

#### Scenario: Pack is regenerated in another output directory
- **WHEN** identical logical inputs are used from the same repository snapshot
- **THEN** output-directory location does not change manifest bytes

#### Scenario: V2 artifacts replace the v1 snapshot at the canonical pack path
- **WHEN** apply regenerates the canonical pack in a fresh target and updates the committed pack
- **THEN** candidate, report, and manifest hashes all differ from their v1 committed hashes
- **AND** no second canonical pack path or dual v1/v2 output is created

### Requirement: Human-facing documentation does not replace evidence
The pack README and Chinese Human Briefs SHALL link to the current OpenSpec artifacts, JSON/JSONL outputs, tests, and validation evidence as authoritative sources. They MUST state the prompt-only v2 contract, current readiness, remaining blockers, and excluded claims without presenting the candidate matrix as accepted training data. The proposal brief MUST visibly state `PROPOSED` and `APPLY_NOT_STARTED`. After apply, a distinct apply brief MUST present fresh v2 hashes and validation evidence, while the 2026-07-11 v1 qualification brief MUST be visibly marked `HISTORICAL_V1_SNAPSHOT` wherever its old hashes or evidence could otherwise be read as current. The README regeneration command MUST write to a fresh temporary target and compare bytes/hashes with the committed pack instead of attempting to overwrite it. Human-facing documents MUST state that they are review/navigation aids rather than a second source of truth.

#### Scenario: Reviewer opens the proposal brief before apply
- **WHEN** the prompt-only change has proposal artifacts but implementation has not started
- **THEN** the brief shows `PROPOSED` and `APPLY_NOT_STARTED`
- **AND** it links to the proposal, design, delta specification, and tasks at paths that exist in the current checkout
- **AND** it does not claim that v2 artifacts, hashes, training, evaluation, merge, or release already exist

#### Scenario: Reviewer opens the v2 apply brief
- **WHEN** apply is complete and summarized for human review
- **THEN** the current brief shows the prompt-only policy, v2 schemas and hashes, `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`
- **AND** it states that no model training, blind rerun, A100/GPU job, checkpoint, benchmark gain, commit, push, PR, merge, archive, or release occurred during apply

#### Scenario: Reviewer opens the previous qualification brief after v2 apply
- **WHEN** the earlier v1 brief remains in the repository after the canonical pack has moved to v2
- **THEN** it visibly identifies itself as `HISTORICAL_V1_SNAPSHOT`
- **AND** it directs readers to the current v2 apply brief and machine artifacts instead of presenting v1 hashes or query evidence as current
