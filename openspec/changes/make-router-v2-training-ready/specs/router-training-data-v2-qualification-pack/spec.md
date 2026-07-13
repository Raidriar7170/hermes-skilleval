## ADDED Requirements

### Requirement: Reviewed v4 qualification is additive to canonical v3 artifacts
The system SHALL write the reviewed v4 qualification report only under `data/router-v2-v4/` and SHALL use v4-specific schema and policy identifiers. It MUST NOT overwrite, rewrite, migrate, or reinterpret the canonical v3 candidate rows, qualification report, manifest, pack README, or historical Phase 14-18 and blind artifacts. Existing v3 regeneration MUST remain byte-identical and blocked as `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`.

#### Scenario: V4 reviewed qualification is produced
- **WHEN** complete human review and every v4 minimum pass
- **THEN** the v4 report is written beside the v4 reviewed package
- **AND** canonical v3 artifact hashes and protected historical tree identities remain unchanged

#### Scenario: V4 input is absent
- **WHEN** the source snapshot exists but a complete `review-decisions.csv` does not
- **THEN** no v4 reviewed qualification report is produced
- **AND** the existing v3 blocked report is not used as a substitute

### Requirement: Reviewed v4 package schemas and identities are exact
The reviewed package SHALL use only these canonical files, identifiers, and
integer versions:

| Repository path | `schema_version` | `policy_id` | `artifact_version` |
|---|---|---|---:|
| `data/router-v2-v4/accepted-pairs.jsonl` | `router-training-data-v2-accepted-pair-v4` | `router-training-data-v2-training-admission-v4` | 4 |
| `data/router-v2-v4/split-manifest.json` | `router-training-data-v2-split-manifest-v4` | `router-training-data-v2-qualification-v4` | 4 |
| `data/router-v2-v4/qualification-report.json` | `router-training-data-v2-qualification-report-v4` | `router-training-data-v2-qualification-v4` | 4 |
| `data/router-v2-v4/training-input-manifest.json` | `router-training-data-v2-training-input-manifest-v4` | `router-training-data-v2-training-admission-v4` | 4 |

The independently supplied `source_snapshot_commit` MUST be the full lowercase
40-hex commit A identity and MUST match every derived artifact. Define `H(x)`
as SHA-256 of strict-UTF-8
`json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
allow_nan=False)` bytes without an LF. `package_id` SHALL equal
`router-v2-v4-reviewed-` plus the first 16 hex characters of `H` over an
exact-shape object containing, and only containing, `source_snapshot_id`,
`source_snapshot_commit`, `source_manifest_sha256`,
`source_candidates_sha256`, and `review_decisions_sha256`. All four derived
artifacts MUST carry that identical package ID. `pair_id` SHALL be exactly
`<task_id>/<skill_id>`, and `accepted_record_id` SHALL be exactly
`router-v2-v4-accepted:<source_record_id>`.

`review-decisions.csv` remains the complete human-owned input with the source
queue's exact 19-column header. The builder MUST read but never generate,
rewrite, normalize, repair, or reorder that file.

#### Scenario: A v4 identifier is changed consistently in one file
- **WHEN** a producer rewrites an artifact identifier and its local hashes but
  the value does not match the exact package derivation and all peer artifacts
- **THEN** the complete package is rejected
- **AND** no compatibility alias or version inference is attempted

### Requirement: Accepted v4 rows have one exhaustive exact shape
Every accepted JSONL row SHALL contain exactly these fields:

`schema_version`, `artifact_version`, `policy_id`, `package_id`,
`accepted_record_id`, `pair_id`, `source_snapshot_id`,
`source_snapshot_commit`, `source_manifest_sha256`,
`source_candidates_sha256`, `review_decisions_sha256`, `source_record_id`,
`source_record_exact_bytes_sha256`, `review_decision_sha256`,
`source_schema_version`, `source_kind`, `source_dataset_id`,
`source_candidate_artifact_path`, `source_artifact_path`,
`source_draft_line_sha256`, `source_split`, `source_role`, `task_id`,
`prompt_family_id`, `positive_skill_id`, `skill_id`, `query_text`,
`query_text_policy`, `prompt_text_sha256`, `skill_record_sha256`,
`skill_text_policy`, `skill_text`, `accepted_for_training`, `training_split`,
`decision`, `supervision_label`, `review_status`, `reviewer`,
`review_reason`, `source_hash`, and `acceptance_hash`.

`artifact_version` MUST be integer `4`, with booleans rejected;
`accepted_for_training` MUST be boolean `true` and means only package
membership, never execution authorization. Every other field MUST be a string.
Identity, query, skill, reviewer, and reason strings MUST be nonblank using
`value.strip()` only as a predicate while preserving stored bytes. Every SHA
field MUST be lowercase 64-hex. Constants SHALL be:

- `source_schema_version="router-v2-reviewed-source-record-v1"`;
- `source_kind="ROUTER_V2_V4_AUTHORED_DRAFT"`;
- `source_dataset_id="router-v2-v4-reviewed-source-snapshot"`;
- `source_candidate_artifact_path="data/router-v2-v4/source-candidates.jsonl"`;
- `source_artifact_path="data/router-v2-v4/source-draft.jsonl"`;
- `source_split="train"`, `query_text_policy="prompt_only"`,
  `skill_text_policy="router_skill_text_v1"`, and `training_split="train"`.

For the authenticated commit-A Skill Index object, `skill_text` MUST equal
exactly `" ".join([skill.id.replace("-", " "), skill.name,
skill.category or "", skill.description, " ".join(skill.trigger_terms),
skill.body])`, without trimming or normalization. The same object MUST
independently reproduce `skill_record_sha256` and `skill_text`.

Only these mappings are admitted:

| Source role | Human decision | `supervision_label` | `review_status` |
|---|---|---|---|
| `POSITIVE` | `ACCEPT_POSITIVE` | `POSITIVE` | `ACCEPTED_POSITIVE` |
| `HARD_NEGATIVE_CANDIDATE` | `SECONDARY_POSITIVE` | `POSITIVE` | `ACCEPTED_SECONDARY_POSITIVE` |
| `HARD_NEGATIVE_CANDIDATE` | `TRUE_HARD_NEGATIVE` | `HARD_NEGATIVE` | `ACCEPTED_HARD_NEGATIVE` |

No evaluation, no-skill, easy-negative, ambiguous, source-defect, rejected,
blank, or unknown decision may appear. Accepted IDs, pair IDs, source IDs, and
source-identity tuples MUST each be unique. Accepted rows MUST equal the split
manifest's training membership exactly, in source-manifest order, without
filtering. At most one accepted row with `supervision_label="POSITIVE"` MAY
exist for a `task_id`. In particular, an owner `ACCEPT_POSITIVE` row and its
same-draft candidate `SECONDARY_POSITIVE` row MUST NOT both be accepted; this
prevents the identical query from becoming two positive skills and then acting
as an in-batch false negative.

`review_decision_sha256` SHALL be `H` over an exact object containing only
`source_record_id`, `source_record_exact_bytes_sha256`, `decision`, `reviewer`,
and `reason`. `source_hash` SHALL be `H` over exactly these accepted-row
projections: `source_snapshot_id`, `source_snapshot_commit`,
`source_manifest_sha256`, `source_candidates_sha256`, `source_record_id`,
`source_record_exact_bytes_sha256`, `pair_id`, `source_schema_version`,
`source_kind`, `source_dataset_id`, `source_candidate_artifact_path`,
`source_artifact_path`, `source_draft_line_sha256`, `source_split`,
`source_role`, `task_id`, `prompt_family_id`, `positive_skill_id`, `skill_id`,
`query_text`, `query_text_policy`, `prompt_text_sha256`,
`skill_record_sha256`, `skill_text_policy`, and `skill_text`.
`acceptance_hash` SHALL be `H` over exactly `source_hash`,
`review_decisions_sha256`, `review_decision_sha256`, `policy_id`, `package_id`,
`accepted_record_id`, `pair_id`, `accepted_for_training`, `training_split`,
`decision`, `supervision_label`, `review_status`, `reviewer`, and
`review_reason`.

#### Scenario: A self-consistent accepted row rewrites source bytes
- **WHEN** source, decision, or accepted-row values and producer hashes agree
  locally but do not match the independently read commit-A source bytes
- **THEN** the complete package fails
- **AND** no accepted row is returned or silently discarded

### Requirement: The v4 split manifest is a complete reviewed partition
`split-manifest.json` SHALL contain exactly `schema_version`,
`artifact_version`, `policy_id`, `package_id`, `source_snapshot_id`,
`source_snapshot_commit`, `source_manifest_sha256`,
`source_candidates_sha256`, `review_decisions_sha256`,
`accepted_pairs_sha256`, `ordering`, `members`, `counts`,
`train_positive_by_skill`, `families`, and `family_intersections`.

`members` MUST contain all 192 source records exactly once in source-manifest
record order. Each member SHALL contain exactly `source_record_id`,
`source_record_exact_bytes_sha256`, `review_decision_sha256`, `task_id`,
`prompt_family_id`, `source_split`, `source_role`, `positive_skill_id`,
`skill_id`, `decision`, `partition`, `accepted_record_id`, and
`supervision_label`. Skill identities may be string or `null` according to the
source schema. `accepted_record_id` and `supervision_label` MUST be strings
only for training partitions and `null` otherwise. `partition` is exactly one
of `TRAIN_POSITIVE`, `TRAIN_HARD_NEGATIVE`, `CALIBRATION_POSITIVE`,
`NON_BLIND_TEST_POSITIVE`, `CALIBRATION_NO_SKILL`,
`NON_BLIND_TEST_NO_SKILL`, or `EXCLUDED`.

Partition mapping is exhaustive:

- train `POSITIVE/ACCEPT_POSITIVE` and train
  `HARD_NEGATIVE_CANDIDATE/SECONDARY_POSITIVE` map to `TRAIN_POSITIVE` and
  their exact accepted positive record;
- train `HARD_NEGATIVE_CANDIDATE/TRUE_HARD_NEGATIVE` maps to
  `TRAIN_HARD_NEGATIVE` and its exact accepted hard-negative record;
- calibration `POSITIVE/ACCEPT_POSITIVE` maps to `CALIBRATION_POSITIVE`;
- non-blind-test `POSITIVE/ACCEPT_POSITIVE` maps to
  `NON_BLIND_TEST_POSITIVE`;
- calibration `NO_SKILL_CANDIDATE/NO_SKILL_CONFIRMED` maps to
  `CALIBRATION_NO_SKILL`;
- non-blind-test `NO_SKILL_CANDIDATE/NO_SKILL_CONFIRMED` maps to
  `NON_BLIND_TEST_NO_SKILL`;
- every other role-compatible complete human decision maps only to `EXCLUDED`.

No evaluation partition produces an accepted training row or supervision
label. A role-incompatible decision rejects the complete package instead of
mapping to `EXCLUDED`.

`ordering` SHALL contain exactly:

- `split_order=["train","calibration","non_blind_test"]`;
- `source_role_order=["POSITIVE","HARD_NEGATIVE_CANDIDATE","NO_SKILL_CANDIDATE"]`;
- `member_sort_keys=["split","prompt_family_id","source_role","source_record_id"]`.

`counts` SHALL contain exactly `source_record_count`, `reviewed_record_count`,
`accepted_train_positive_count`, `true_hard_negative_count`,
`accepted_train_pair_count`, `accepted_calibration_positive_count`,
`accepted_non_blind_test_positive_count`,
`confirmed_calibration_no_skill_count`,
`confirmed_non_blind_test_no_skill_count`, and `excluded_record_count`.
`train_positive_by_skill` SHALL contain exactly all 16 canonical skill IDs with
nonnegative integer counts. `families` SHALL contain exactly `train`,
`calibration`, and `non_blind_test`, each a unique UTF-8-byte-sorted string
array derived from every source row. `family_intersections` SHALL contain
exactly `train_calibration`, `train_non_blind_test`, and
`calibration_non_blind_test`, all equal to `[]`.

#### Scenario: A reviewed source row is omitted from split membership
- **WHEN** the 192-row source/review join is not represented exactly once in
  split-manifest order
- **THEN** package construction fails
- **AND** aggregate count agreement does not substitute for row membership

### Requirement: V4 qualification report fields and blockers are closed sets
`qualification-report.json` SHALL contain exactly `artifact_type`,
`schema_version`, `artifact_version`, `policy_id`, `package_id`,
`qualification_status`, `router_decision`, `can_start_preflight`,
`can_start_training`, `blocker_codes`, `query_contract`, `thresholds`,
`counts`, `coverage`, `family_diagnostics`, `reviewer_diagnostics`, `lineage`,
`checks`, and `non_actions`.

On a published PASS, constants are
`artifact_type="router-training-data-v2-qualification-report"`,
`qualification_status="PASS"`, `router_decision="KEEP_BASELINE"`,
`can_start_preflight=true`, `can_start_training=false`, and
`blocker_codes=[]`. `query_contract` SHALL contain exactly
`formatter="router_query_text(prompt: str)"`,
`query_text_policy="prompt_only"`, `primary_task_query_field="query_text"`,
`prompt_hash_field="prompt_text_sha256"`, `alternate_task_query_fields=[]`,
and `skill_text_policy="router_skill_text_v1"`.

`thresholds` SHALL contain exactly
`train_positive_minimum=64`, `true_hard_negative_minimum=48`,
`accepted_train_pair_minimum=100`,
`accepted_train_pair_policy_maximum=160`,
`accepted_train_pair_effective_maximum=128`,
`calibration_positive_required=16`,
`non_blind_test_positive_required=16`,
`calibration_no_skill_minimum=16`,
`non_blind_test_no_skill_minimum=16`, and
`train_positive_skill_coverage_required=16`. `counts` MUST have the exact
split-manifest count shape and be independently recomputed.

`coverage` SHALL contain exactly `canonical_skill_ids`,
`covered_train_positive_skill_ids`, `missing_train_positive_skill_ids`,
`covered_train_positive_skill_count`, and `train_positive_by_skill`; PASS
requires the first two arrays to equal the same 16 UTF-8-byte-sorted IDs,
missing to equal `[]`, and count to equal `16`. `family_diagnostics` SHALL
contain exactly independent `families` and `family_intersections` objects with
the split-manifest shapes.

`reviewer_diagnostics` SHALL contain exactly `reviewer_ids`,
`distinct_reviewer_count`, `single_reviewer_pilot`, and `limitation_codes`.
Reviewer IDs are the distinct exact identities from all 192 decisions sorted
by UTF-8 bytes. `single_reviewer_pilot` equals
`distinct_reviewer_count == 1`; `limitation_codes` is exactly
`["SINGLE_REVIEWER_PILOT"]` then and `[]` otherwise. No reviewer identity is
normalized or inferred.

`lineage` SHALL contain exactly `source_snapshot_id`,
`source_snapshot_commit`, `source_manifest_sha256`,
`source_candidates_sha256`, `review_decisions_sha256`,
`accepted_pairs_sha256`, and `split_manifest_sha256`. `checks` SHALL contain
exactly `accepted_pair_membership`, `artifact_lineage`, `count_thresholds`,
`evaluation_controls`, `human_review`, `protected_source_boundary`,
`reviewer_attribution`, `role_decision_compatibility`, `source_snapshot`,
`split_family_disjointness`, `train_positive_skill_coverage`, and
`train_positive_task_uniqueness`, each equal to `"PASS"`.

`non_actions` SHALL equal the sorted list `archive`, `blind_v2`, `checkpoint`,
`dashboard`, `deploy`, `gpu_access`, `human_brief`, `model_load`,
`model_training`, `preflight_execution`, `release`, `router_promotion`, `tag`,
and `threshold_tuning`.

Before publication, failure SHALL return `REVIEW_REQUIRED`, `KEEP_BASELINE`,
`can_start_preflight=false`, `can_start_training=false`, and a sorted unique
subset of exactly these blocker codes:

`ACCEPTED_TRAIN_PAIR_COUNT_OUT_OF_RANGE`, `ARTIFACT_LINEAGE_INVALID`,
`CALIBRATION_NO_SKILL_COUNT_BELOW_MINIMUM`,
`CALIBRATION_POSITIVE_COUNT_NOT_EXACT`, `HUMAN_REVIEW_INCOMPLETE`,
`NON_BLIND_TEST_NO_SKILL_COUNT_BELOW_MINIMUM`,
`NON_BLIND_TEST_POSITIVE_COUNT_NOT_EXACT`,
`PROTECTED_SOURCE_BOUNDARY_VIOLATION`, `REVIEW_DECISIONS_INVALID`,
`REVIEW_EVIDENCE_MISSING`, `ROLE_DECISION_INCOMPATIBLE`,
`SOURCE_SNAPSHOT_INVALID`, `SPLIT_FAMILY_OVERLAP`,
`TRAIN_POSITIVE_COUNT_BELOW_MINIMUM`,
`TRAIN_POSITIVE_SKILL_COVERAGE_INCOMPLETE`, `TRAIN_POSITIVE_TASK_CONFLICT`, and
`TRUE_HARD_NEGATIVE_COUNT_BELOW_MINIMUM`. A nonempty blocker set MUST publish
none of the four canonical derived artifacts.

#### Scenario: A gate fails after staging begins
- **WHEN** any exact-shape, lineage, review, count, coverage, or family gate
  yields a blocker
- **THEN** all staged derived output is removed and no canonical file is changed
- **AND** the failure remains `REVIEW_REQUIRED` with `KEEP_BASELINE`

### Requirement: V4 package serialization and publication are deterministic
JSON and JSONL SHALL use strict UTF-8 without BOM, reject duplicate keys and
NaN/Infinity, serialize compact sorted-key `ensure_ascii=false` objects, and
end every object or JSONL row with exactly one LF. JSONL has no blank rows.
Accepted rows follow source-manifest order filtered to training partitions;
split members follow complete source-manifest order. Skill, family, reviewer,
and blocker arrays are unique and sorted by exact UTF-8 bytes. Decisions CSV
retains the source queue's Python `excel` dialect, minimal quoting,
`lineterminator="\n"`, and UTF-8 without BOM. Every string MUST strict-UTF-8
encode before hashing. In reviewed-package construction, invalid Unicode in an
authenticated source yields `SOURCE_SNAPSHOT_INVALID`, invalid Unicode in a
human decision yields `REVIEW_DECISIONS_INVALID`, and invalid Unicode in a
derived object yields `ARTIFACT_LINEAGE_INVALID`; each remains a
`REVIEW_REQUIRED`, `KEEP_BASELINE`, `can_start_training=false` failure and
publishes nothing. Only the later admission/preflight external surface wraps
invalid package Unicode with stable prefix `TRAINING_INPUT_INVALID`.

The dependency is acyclic: source plus decisions produce accepted pairs;
accepted-pair bytes bind the split manifest; those bytes bind the qualification
report; those bytes finally bind the training-input manifest. All four derived
files MUST be staged beside the canonical directory, independently validated,
and published together without overwrite only after every gate passes. Partial
publication is forbidden.

#### Scenario: Identical reviewed input is rebuilt
- **WHEN** exact source, decision, commit, policy, and runtime-independent
  inputs are rebuilt into fresh targets
- **THEN** all four derived artifacts are byte-identical
- **AND** output location does not enter any logical path or hash

### Requirement: V4 qualification distinguishes data readiness from router decision
The v4 qualification report SHALL independently recompute source, review, accepted-pair, split, coverage, reviewer, and blocker diagnostics from exact bound artifacts. It MAY report that reviewed data is eligible for training preflight only when every reviewed-data gate passes, but it SHALL keep `router_decision="KEEP_BASELINE"`. It MUST NOT report model training, checkpoint creation, benchmark improvement, candidate promotion, release approval, or production readiness.

#### Scenario: Reviewed package meets every data gate
- **WHEN** all accepted-pair counts, evaluation controls, 16/16 coverage, family disjointness, reviewer evidence, hashes, and provenance checks pass with zero blockers
- **THEN** the report marks reviewed-data qualification as PASS and allows only the next side-effect-free preflight stage
- **AND** `router_decision` remains `KEEP_BASELINE`

#### Scenario: One gate is copied rather than recomputed
- **WHEN** a reported count, hash, split intersection, coverage result, or reviewer diagnostic disagrees with independently parsed source data
- **THEN** qualification fails closed
- **AND** a matching value copied from another manifest does not make the pack eligible

### Requirement: V4 qualification discloses review limitations
The v4 report SHALL record the exact distinct reviewer count and whether the pilot used a single reviewer. A single human reviewer MAY satisfy the pilot's attribution requirement only when every decision has non-empty reviewer and reason fields and the report visibly records `single_reviewer_pilot=true` as a limitation. The system MUST NOT infer a reviewer from file ownership, Git identity, environment variables, timestamps, or repeated decision style.

#### Scenario: One named reviewer completed all rows
- **WHEN** one human-supplied reviewer identity appears on every valid decision row
- **THEN** qualification records one distinct reviewer and the single-reviewer limitation
- **AND** it does not claim independent or dual review

#### Scenario: Reviewer field is blank
- **WHEN** any decision row lacks a non-empty reviewer or reason
- **THEN** the complete v4 qualification remains blocked
- **AND** file metadata or Git authorship does not fill the field

### Requirement: V4 qualification preserves non-blind and no-training boundaries
The v4 qualification workflow MUST operate only on the frozen v4 source snapshot and completed human decisions. It MUST NOT inspect old Phase 16 prompts, blind-v2 data, blind labels, training outputs, model predictions, or benchmark results when constructing or qualifying reviewed pairs. It MUST NOT import model frameworks, access a GPU/A100, load a model, create a checkpoint, tune a threshold, run evaluation, or change router selection.

#### Scenario: Local reviewed-data qualification completes
- **WHEN** a valid human-reviewed v4 package is qualified
- **THEN** only v4 data/package artifacts are written by the qualification command
- **AND** no model, GPU, blind, evaluation, release, or promotion action occurs

#### Scenario: A blind-derived row is presented as reviewed
- **WHEN** any source lineage resolves to blind or Phase 16 prompt content
- **THEN** the complete v4 package is rejected before prompt content is consumed for training
- **AND** human approval does not override the protected-source prohibition
