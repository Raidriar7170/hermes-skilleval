## MODIFIED Requirements

### Requirement: Candidate construction is deterministic and type-safe
The system SHALL emit one `router-training-data-v2-candidate-v3` row with `artifact_version=3` and `policy_id="router-training-data-v2-qualification-v3"` for every task-skill combination, sorted by task ID and skill ID, with unique `<task-id>/<skill-id>` pair IDs. Every row MUST set `query_text` to the unchanged output of the shared `router_query_text(task.prompt)` formatter, set `query_text_policy="prompt_only"`, and set `prompt_text_sha256` to the SHA-256 of the UTF-8 bytes of that exact `query_text`. Task ID, category, difficulty, robustness tags, split, and family MAY be used only as structured validation, classification, split, or provenance inputs and MUST NOT be concatenated, serialized, or otherwise encoded into the primary query or used as a core router scoring, ranking, gating, tie-break, or acceptance feature. Category MAY continue to distinguish same-category from cross-category qualification candidates. The row MUST NOT expose a legacy, alternate, composite, or second task-side query representation. Manifest file hashes SHALL continue to cover raw input bytes. The system MUST distinguish `positive`, `same_category_negative_candidate`, and `cross_category_easy_negative` without describing an unreviewed or cross-category negative as a qualified hard negative.

#### Scenario: Canonical v3 matrix is generated
- **WHEN** the 12 canonical migration tasks and 16 canonical skills are qualified
- **THEN** `candidate-pairs.jsonl` contains exactly 192 sorted unique `router-training-data-v2-candidate-v3` rows with `artifact_version=3`
- **AND** every row sets `query_text_policy="prompt_only"` and `policy_id="router-training-data-v2-qualification-v3"`
- **AND** the rows contain 16 positives, 32 same-category negative candidates, and 144 cross-category easy negatives

#### Scenario: Shared formatter output equals the loaded prompt
- **WHEN** a task is loaded and candidates are constructed for it
- **THEN** each candidate's `query_text` equals `router_query_text(task.prompt)` and the loader-normalized `task.prompt` byte-for-byte
- **AND** recomputing SHA-256 over the UTF-8 bytes of `query_text` equals `prompt_text_sha256`

#### Scenario: Benchmark metadata changes while prompt stays fixed
- **WHEN** task ID, category, difficulty, robustness tags, split, or family changes in valid isolated fixtures while the loader-normalized prompt remains byte-identical
- **THEN** candidate `query_text` remains byte-identical
- **AND** `prompt_text_sha256` remains identical
- **AND** none of those metadata values is added to a task-side query or core scoring feature

#### Scenario: No dual or composite query is emitted
- **WHEN** a v3 candidate row is serialized
- **THEN** `query_text` is its only primary task-side query text field
- **AND** the row contains no legacy, alternate, metadata-enriched, or composite query field

#### Scenario: V3 regeneration uses identical inputs
- **WHEN** the command runs twice with byte-identical inputs and the v3 policy
- **THEN** the candidate matrix, qualification report, and manifest are byte-identical

### Requirement: Held-out source rows remain reserved
The system MUST preserve the original task split as `source_split`. It MUST use `TRAIN_CANDIDATE_POSITIVE`, `REVIEW_REQUIRED_NEGATIVE_CANDIDATE`, and `EXCLUDED_EASY_NEGATIVE` for the three `dev` dispositions and MUST mark every candidate derived from a source `test` task as `RESERVED_SOURCE_TEST`. Every qualification candidate row MUST set `accepted_for_training=false`, and version 3 MUST NOT write `training-pairs.jsonl`, `training-pairs-v2.jsonl`, an accepted-pair v3 artifact, a `router-training-data-v2-training-input-manifest-v3`, or another trainer-ready pair or package file.

#### Scenario: Canonical test candidates are emitted
- **WHEN** the canonical source includes four `test` tasks
- **THEN** all 64 task-skill candidate rows from those tasks are marked reserved
- **AND** their 5 positives and 11 same-category negative candidates do not count as train candidates

#### Scenario: V3 qualification remains incomplete
- **WHEN** version 3 writes any diagnostic pack
- **THEN** no legacy training-pair file, accepted-pair v3 artifact, training-input v3 manifest, or other trainer-ready package is present
- **AND** `can_start_training` is `false`

### Requirement: Qualification fails closed on evidence gaps
The version 3 diagnostic report SHALL use `schema_version="router-training-data-v2-qualification-report-v3"`, `artifact_version=3`, and `policy_id="router-training-data-v2-qualification-v3"`. It SHALL expose the shared formatter-based prompt-only query contract, checks, blocker codes, and `diversity_diagnostics`, and SHALL always set `qualification_status="REVIEW_REQUIRED"`, `router_decision="KEEP_BASELINE"`, and `can_start_training=false`. The query contract MUST identify `router_query_text(prompt: str)` as the formatter, `query_text` as the sole primary task-side query field, `task.prompt` as its loader-normalized source, `prompt_text_sha256` as the SHA-256 binding, task ID/category/difficulty/robustness tags/split/family as forbidden query or scoring inputs, and an empty alternate-query-field list. `diversity_diagnostics` MUST report `unique_prompt_count=12`, `train_policy_unique_prompt_count=8`, `unique_task_family_count=null`, family metadata status `UNAVAILABLE`, a family-independent count of `null`, and `per_skill_unique_train_positive_prompt_count` for all 16 canonical skills. Missing family metadata MUST NOT be inferred from category, task ID, skill, neighboring rows, or any other proxy. The report SHALL NOT accept or infer reviewed-negative, true-reject, task-family, calibration-membership, or human-acceptance evidence. A future separately authorized change is required before the system can authorize training.

#### Scenario: Canonical source is assessed honestly under v3
- **WHEN** the current migration tasks and Phase 9 skill index are qualified without new reviewed metadata
- **THEN** the report remains `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`
- **AND** it records incomplete pair volume and target-skill coverage
- **AND** it records 28 source pairs, 192 matrix candidates, 16 positives, 32 same-category negative candidates, 144 cross-category easy negatives, 32 train-policy candidates, 0 accepted train pairs, 64 reserved matrix rows, 11/16 train-positive skill coverage, and 0 reject examples
- **AND** its sorted blocker codes are exactly `INDEPENDENT_CALIBRATION_SPLIT_MISSING`, `MANUAL_ACCEPTANCE_MISSING`, `PAIR_COUNT_BELOW_MINIMUM`, `REJECT_EXAMPLES_MISSING`, `SAME_CATEGORY_NEGATIVES_UNREVIEWED`, `TARGET_POSITIVE_COVERAGE_INCOMPLETE`, `TASK_FAMILY_METADATA_MISSING`, and `TASK_FAMILY_SPLIT_NOT_INDEPENDENT`

#### Scenario: Report exposes the shared v3 query contract
- **WHEN** a qualification report is written
- **THEN** its machine-readable query contract declares the shared `router_query_text(prompt: str)` formatter, `prompt_only`, `query_text`, `task.prompt`, loader normalization, SHA-256 binding through `prompt_text_sha256`, all six forbidden task-metadata inputs, and no alternate query fields
- **AND** its policy, schema, and artifact identifiers are the v3 identifiers

#### Scenario: Diversity diagnostics cover every canonical skill
- **WHEN** `diversity_diagnostics` is generated from the canonical candidate rows
- **THEN** `unique_prompt_count` is `12`, `train_policy_unique_prompt_count` is `8`, `unique_task_family_count` is `null`, family metadata status is `UNAVAILABLE`, and the family-independent count is `null`
- **AND** `per_skill_unique_train_positive_prompt_count` is `1` for `apply-patch-discipline`, `browser-smoke-testing`, `evidence-backed-final`, `form-interaction-flow`, `plan-mode`, `slash-command-workflow`, `subagent-worker-protocol`, `systematic-debugging`, `test-driven-development`, `verification-before-completion`, and `visual-regression-review`
- **AND** it is explicitly `0` for `accessibility-tree-inspection`, `mcp-tool-routing`, `task-tool-delegation`, `using-git-worktrees`, and `workspace-git-hygiene`

#### Scenario: Missing families remain unavailable
- **WHEN** canonical rows do not contain task-family metadata
- **THEN** family counts remain JSON `null` and the human-readable family status remains `UNAVAILABLE`
- **AND** no family value or family-independent count is inferred from another field

#### Scenario: Cross-category volume reaches the numeric target
- **WHEN** total candidate volume is between 100 and 200 only because cross-category easy negatives are included
- **THEN** those easy negatives do not count toward the accepted train-pair threshold
- **AND** qualification remains blocked

### Requirement: Provenance manifest binds inputs and outputs
The system SHALL write a deterministic `router-training-data-v2-manifest-v3` manifest with `artifact_version=3` and `policy_id="router-training-data-v2-qualification-v3"`. It SHALL contain the same shared formatter-based prompt-only query contract and the same `diversity_diagnostics` values as the qualification report, repository-relative logical input paths, SHA-256 records for all non-blind task metadata/prompts and the skill index, output hashes for the candidate matrix and qualification report, counts, ordering rules, and explicit non-actions. The query contract MUST identify `router_query_text(prompt: str)` as the formatter, `query_text` as the sole primary task-side query field, `task.prompt` as its loader-normalized source, `prompt_text_sha256` as its SHA-256 binding, task ID/category/difficulty/robustness tags/split/family as forbidden task-side query or scoring inputs, and no alternate query fields. A validator MUST independently recompute counts, query hashes, `unique_prompt_count`, train-policy unique prompt count, all 16 per-skill unique train-positive prompt counts, family null/status values, and the family-independent null value from canonical rows; it MUST NOT establish manifest/report agreement by copying values from either artifact. The manifest MUST NOT contain machine-specific absolute output paths or blind prompt-derived values, and version 3 MUST reject inputs outside the discovered repository root or any mixed v1/v2/v3 artifact set.

#### Scenario: V3 manifest hashes and diagnostics verify
- **WHEN** a consumer recomputes every listed input and output SHA-256, count, query hash, and diversity diagnostic from canonical inputs and rows
- **THEN** each recomputed value matches the manifest
- **AND** the candidate/report counts match the referenced artifacts
- **AND** the manifest and report contain identical prompt-only query contracts and diversity diagnostics

#### Scenario: Report and manifest disagree
- **WHEN** a report or manifest copies a stale count, prompt statistic, family value, family status, family-independent value, or per-skill count
- **THEN** independent recomputation detects the mismatch and qualification fails
- **AND** agreement between the two stale artifacts alone is insufficient

#### Scenario: Pack is regenerated in another output directory
- **WHEN** identical logical inputs are used from the same repository snapshot
- **THEN** output-directory location does not change manifest bytes

#### Scenario: V3 artifacts replace the v2 snapshot at the canonical pack path
- **WHEN** apply regenerates the canonical pack in a fresh target and updates the committed pack
- **THEN** candidate, report, and manifest hashes all differ from their v2 committed hashes
- **AND** no second canonical pack path or dual v2/v3 output is created

#### Scenario: Protected historical evidence remains byte-identical
- **WHEN** the v3 qualification pack and its documentation truth repair are produced
- **THEN** the committed Phase 14, 15, 16, 17, and 18 evidence trees and every blind evidence tree have zero modification
- **AND** no blind-v2 data, blind mining, blind rerun, or replacement evidence is created

### Requirement: Human-facing documentation does not replace evidence
The pack README and Chinese Human Briefs SHALL link to the current OpenSpec artifacts, JSON/JSONL outputs, tests, and validation evidence as authoritative sources. They MUST state the shared prompt-only v3 contract, current readiness, remaining blockers, and excluded claims without presenting the candidate matrix as accepted training data. The current README and Human Brief lifecycle wording MUST identify existing local commit `f996690700a79ab4c065ed8523340d2fd387f6b9` instead of describing that completed prompt-only apply as a proposal HEAD or uncommitted diff. This wording correction MUST be described only as truth-surface repair and MUST NOT be presented as new evidence, human acceptance, training readiness, remote CI, lifecycle progress, or a change to qualification counts or decisions. The README regeneration command MUST write to a fresh temporary target and compare bytes/hashes with the committed pack instead of attempting to overwrite it. Human-facing documents MUST state that they are review/navigation aids rather than a second source of truth.

#### Scenario: Reviewer opens the current v3 brief
- **WHEN** the v3 contract apply is summarized for human review
- **THEN** the brief shows the shared formatter, v3 schemas and hashes, `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`
- **AND** it states that no reviewed data, trainer-ready package, model training, blind rerun, A100/GPU job, checkpoint, benchmark gain, push, PR, merge, archive, tag, or release occurred

#### Scenario: Stale lifecycle wording is repaired
- **WHEN** the current pack README or Human Brief describes the prompt-only work as a proposal HEAD or uncommitted apply diff
- **THEN** only that lifecycle truth is corrected to the existing local commit `f996690700a79ab4c065ed8523340d2fd387f6b9`
- **AND** the correction does not claim push, remote CI, review acceptance, training readiness, new evidence, or lifecycle advancement

#### Scenario: Historical evidence remains authoritative and immutable
- **WHEN** documentation links to Phase 14–18 or blind evidence for historical context
- **THEN** those trees retain zero modification
- **AND** the documentation repair is not counted as evidence progress or a replacement for machine artifacts
