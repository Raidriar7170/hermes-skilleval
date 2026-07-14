## ADDED Requirements

### Requirement: V4 source authoring uses the canonical 16-skill universe
The system SHALL build the Router V2 v4 source snapshot only from the canonical Skill Index at `docs/demo/phase9-real-skill-library-migration/skills.json` and an explicitly authored pre-review `data/router-v2-v4/source-draft.jsonl`. The first-slice draft MAY be authored by the implementing agent from approved constraints; authoring MUST NOT be represented as human review or row-level approval. The system MUST bind the exact Skill Index bytes and MUST reject missing, extra, duplicate, slash-containing, or category-mismatched skill identities. It MUST NOT read, copy, mine, calibrate on, or select from Phase 14-18, `benchmarks/blind-migration-tasks`, an old Phase 16 prompt, a public scored prompt, or any other protected evaluation source.

#### Scenario: Canonical source universe is accepted
- **WHEN** the source builder receives the exact canonical 16-skill index and a valid v4 draft
- **THEN** all generated skill references belong to those 16 identities
- **AND** the source manifest records the canonical logical path, SHA-256, and byte size

#### Scenario: Protected prompt source is referenced
- **WHEN** any draft source path, provenance value, resolved input, or declared origin references a blind, Phase 14-18, scored, or public evaluation prompt
- **THEN** source validation fails before snapshot artifacts are written
- **AND** no prompt content from that source is loaded or hashed into the v4 snapshot

### Requirement: Source draft expands to exactly 192 balanced pending records
The source draft SHALL contain exactly 128 prompt drafts and SHALL expand deterministically to exactly 192 source records: 64 train positives, 64 train same-category hard-negative candidates, 16 calibration positives, 16 non-blind-test positives, 16 calibration no-skill candidates, and 16 non-blind-test no-skill candidates. `positive_skill_id` owns the prompt source. Each canonical `positive_skill_id` MUST own exactly four train-positive drafts, one calibration-positive draft, one non-blind-test-positive draft, and the four hard-negative candidate records expanded from its train drafts. `skill_id` is the reviewed candidate: it equals `positive_skill_id` on a positive, is the distinct same-category target on a hard-negative candidate, and is `null` together with `positive_skill_id` on a no-skill row. Across hard-negative candidates, every canonical `skill_id` target MUST occur exactly four times.

Every source record SHALL set `status="PENDING_REVIEW"`, `decision=""`, `reviewer=""`, and `reason=""`. The three human fields MUST be present as empty strings rather than omitted or populated. No row SHALL set or imply `accepted_for_training=true`.

#### Scenario: Balanced canonical draft is expanded
- **WHEN** the valid 128-draft catalog is built
- **THEN** the source snapshot has exactly 192 rows with the required six role/split counts
- **AND** positive and hard-negative source coverage is exactly balanced across all 16 skills
- **AND** every human field is present and blank on every row

#### Scenario: A count is satisfied by duplicating another skill
- **WHEN** total row counts are correct but any skill has the wrong positive, hard-negative-source, or hard-negative-target count
- **THEN** the entire source build fails
- **AND** 16/16 coverage is not inferred from aggregate volume

#### Scenario: A pre-review row contains a decision
- **WHEN** any source or initial queue row has a non-empty decision, reviewer, reason, acceptance flag, or accepted supervision label
- **THEN** source validation fails
- **AND** the builder does not sanitize the value back to blank

### Requirement: Draft and source record schemas are exact
Every source-draft row SHALL contain exactly `schema_version`, `draft_id`, `prompt_family_id`, `split`, `draft_role`, `positive_skill_id`, `hard_negative_skill_id`, and `prompt_text`. `schema_version` MUST be `router-v2-reviewed-source-draft-v1`; `draft_role` MUST be `SKILL_POSITIVE` or `NO_SKILL`; and `draft_id` and `prompt_family_id` MUST match `[a-z0-9][a-z0-9-]*` and be unique declared identities. `positive_skill_id` MUST be non-null only for `SKILL_POSITIVE`. `hard_negative_skill_id` MUST be non-null only for train `SKILL_POSITIVE` and MUST be null in every other draft.

Every generated source row SHALL contain exactly `schema_version`, `artifact_version`, `policy_id`, `source_record_id`, `draft_id`, `task_id`, `prompt_family_id`, `split`, `source_role`, `positive_skill_id`, `skill_id`, `query_text`, `query_text_policy`, `prompt_text_sha256`, `skill_record_sha256`, `source_kind`, `source_artifact_path`, `source_draft_line_sha256`, `status`, `decision`, `reviewer`, and `reason`. The three source roles are exactly `POSITIVE`, `HARD_NEGATIVE_CANDIDATE`, and `NO_SKILL_CANDIDATE`. `task_id` MUST equal `draft_id`. The schema, artifact version, policy, source kind, source path, and query policy MUST respectively be `router-v2-reviewed-source-record-v1`, integer `1`, `router-v2-reviewed-source-policy-v1`, `ROUTER_V2_V4_AUTHORED_DRAFT`, `data/router-v2-v4/source-draft.jsonl`, and `prompt_only`. For a non-null candidate `skill_id`, `skill_record_sha256` MUST hash compact sorted-key `ensure_ascii=false` JSON bytes of that exact parsed Skill Index object; it MUST be `null` for a no-skill row.

`source_record_id` MUST be derived exactly as `<draft_id>:positive:<skill_id>`, `<draft_id>:hard-negative-candidate:<skill_id>`, or `<draft_id>:no-skill` according to source role. An unknown or missing draft/source key, invalid relation, or non-canonical ID MUST reject the complete snapshot.

#### Scenario: Exact source shapes are generated
- **WHEN** a valid draft row expands into source rows
- **THEN** every draft and source row has exactly its declared fields and versioned constants
- **AND** source IDs, task ID, owner skill, candidate skill, role, and hashes are deterministically related

#### Scenario: Source row has an extension field
- **WHEN** a draft or generated row contains an unknown key even when its value looks harmless
- **THEN** the complete snapshot is rejected
- **AND** the field is not discarded during canonical serialization

### Requirement: Prompt families are explicit and split-disjoint
Every draft SHALL declare one stable non-empty `prompt_family_id` and exactly one split from `train`, `calibration`, or `non_blind_test`. The builder MUST NOT infer family from category, skill, task ID, prompt text, path, or neighboring rows. A family ID MUST occur in only one split. The positive and hard-negative candidate expanded from one train draft SHALL retain the same family and exact prompt; this is the only allowed two-row prompt reuse.

#### Scenario: Families are disjoint
- **WHEN** all draft families are grouped by split
- **THEN** every pairwise split intersection is empty
- **AND** each expanded record retains the draft's declared family and split

#### Scenario: One family crosses evaluation boundary
- **WHEN** the same family ID occurs in train and calibration, train and non-blind-test, or calibration and non-blind-test
- **THEN** the source snapshot is rejected before publication
- **AND** a renamed or inferred family is not substituted

### Requirement: Exact and near-duplicate prompts fail closed
The source validator MUST require one-line printable ASCII prompt text from `U+0020` through `U+007E`, with no leading/trailing or repeated whitespace, and MUST reject duplicate UTF-8 prompt bytes between different drafts. It SHALL compute near-duplicate similarity by applying Unicode NFKC, casefolding, mapping every character outside ASCII `a-z` and `0-9` to one ASCII space, collapsing each run and stripping both ends, then constructing the set of every contiguous five-character substring including internal spaces. Jaccard SHALL equal intersection size divided by union size. Empty normalized text, normalized text shorter than five characters, or two different drafts with similarity greater than or equal to `0.85` MUST fail validation. The manifest MUST record algorithm ID `ascii-nfkc-casefold-char5-jaccard-v1`, threshold `0.85`, Python version, and `unicodedata.unidata_version`.

#### Scenario: Different drafts contain exact duplicate prompts
- **WHEN** two stable draft IDs have byte-identical prompt text
- **THEN** the builder fails with both draft IDs
- **AND** it does not treat their different skill, family, or split metadata as uniqueness

#### Scenario: Cross-split prompts are near duplicates
- **WHEN** two different drafts reach the `0.85` similarity threshold after canonical normalization
- **THEN** the builder rejects the complete snapshot
- **AND** it does not publish a family-disjoint claim

#### Scenario: Train positive and hard-negative rows share a prompt
- **WHEN** the two records were expanded from the same valid train draft
- **THEN** their exact prompt and family reuse is accepted
- **AND** their source record IDs, roles, and skill IDs remain distinct

#### Scenario: Protected prompt exact bytes are reused
- **WHEN** an independent test extracts a designated protected prompt string in memory and computes a one-way exact-UTF-8 hash collision with a new draft prompt
- **THEN** the draft is rejected as protected textual reuse
- **AND** the protected text or digest is not exposed to the builder, manifest, review queue, mining, calibration, or selection
- **AND** hashing only the whole containing file is not accepted as this check

### Requirement: Snapshot bytes and row provenance are canonical
The builder SHALL serialize JSON and JSONL as UTF-8 with `ensure_ascii=false`, sorted object keys, compact separators, and exactly one LF byte after every JSONL row. CSV SHALL use the Python standard-library `excel` dialect, a fixed declared column order, UTF-8 without BOM, and LF line endings. Generated source rows SHALL be ordered by declared split order, prompt family, source role, and stable source record ID. Source-candidate and review-queue bytes MUST be identical for the same input bytes and policy regardless of output location or supported Python/Unicode runtime. Manifest bytes MUST be identical for the same input bytes, policy, `platform.python_version()`, and `unicodedata.unidata_version`; when either recorded runtime identifier differs, only the exact `runtime` object MAY differ.

`review-queue.csv` SHALL have exactly this ordered header: `source_record_id`, `source_record_exact_bytes_sha256`, `draft_id`, `task_id`, `prompt_family_id`, `split`, `source_role`, `positive_skill_id`, `positive_skill_name`, `skill_id`, `skill_name`, `skill_category`, `skill_description`, `query_text`, `prompt_text_sha256`, `status`, `decision`, `reviewer`, `reason`. Null skill identities and displays MUST serialize as empty CSV cells. CSV MUST use the Python standard-library `excel` dialect with `lineterminator="\n"`, minimal quoting, UTF-8 without BOM, and that exact column order.

`source-manifest.json` SHALL have exactly the top-level keys `schema_version`, `artifact_version`, `policy_id`, `snapshot_id`, `ordering`, `duplicate_policy`, `runtime`, `inputs`, `outputs`, `counts`, `skill_distribution`, `records`, and `non_actions`. `runtime` SHALL contain exactly `python_version` and `unicode_data_version`, populated from `platform.python_version()` and `unicodedata.unidata_version`. `inputs.skill_index`, `inputs.source_draft`, `outputs.source_candidates`, and `outputs.review_queue` SHALL each contain exactly `path`, `sha256`, `byte_size`, and `row_count`. Every `records` entry SHALL contain exactly `source_record_id`, `draft_id`, `draft_line_sha256`, `source_record_exact_bytes_sha256`, `prompt_text_sha256`, `prompt_family_id`, `split`, `source_role`, `positive_skill_id`, and `skill_id`. Both line-hash fields MUST hash the canonical JSON object bytes plus that row's terminating LF byte.

`ordering` SHALL contain exactly `split_order`, `source_role_order`, and `sort_keys`, with values `train/calibration/non_blind_test`, `POSITIVE/HARD_NEGATIVE_CANDIDATE/NO_SKILL_CANDIDATE`, and `split/prompt_family_id/source_role/source_record_id` in those exact array orders. `duplicate_policy` SHALL contain exactly `algorithm_id="ascii-nfkc-casefold-char5-jaccard-v1"` and `threshold=0.85`. `counts` SHALL contain exactly `total`, `train_positive`, `train_hard_negative_candidate`, `calibration_positive`, `non_blind_test_positive`, `calibration_no_skill_candidate`, and `non_blind_test_no_skill_candidate`. `skill_distribution` SHALL contain exactly `train_positive_by_skill`, `calibration_positive_by_skill`, `non_blind_test_positive_by_skill`, `hard_negative_owner_by_skill`, and `hard_negative_target_by_skill`. `non_actions` SHALL equal the sorted array `accepted_pairs`, `archive`, `blind_v2`, `checkpoint`, `dashboard`, `deploy`, `gpu_access`, `human_brief`, `model_training`, `preflight`, `release`, `review_decisions`, `router_promotion`, `tag`, `threshold_tuning`, and `training_input`.

`snapshot_id` SHALL equal `router-v2-v4-source-` plus the first 16 lowercase hex characters of SHA-256 over exact Skill Index bytes, one NUL byte, exact draft bytes, one NUL byte, and UTF-8 policy ID bytes in that order.

The manifest `schema_version`, integer `artifact_version`, and `policy_id` SHALL respectively equal `router-v2-source-snapshot-manifest-v1`, `1`, and `router-v2-reviewed-source-policy-v1`. Input/output paths SHALL serialize as the canonical repository-relative Skill Index path and `data/router-v2-v4/source-draft.jsonl`, `data/router-v2-v4/source-candidates.jsonl`, and `data/router-v2-v4/review-queue.csv`. Isolated regeneration MAY use another physical output directory but MUST retain those canonical logical identities so location does not change bytes within the same recorded runtime identifiers.

The manifest SHALL bind the logical path, SHA-256, and byte size of the canonical Skill Index, source draft, source candidates, and initial review queue. It SHALL also bind every draft line and source-candidate line by stable ID and exact-line SHA-256 together with prompt SHA-256, family, split, role, owner identity, and candidate identity. Every hash and count MUST be recomputed from exact bytes rather than trusted from a row or copied artifact. Unknown or missing keys at any declared exact-shape level MUST reject the snapshot.

#### Scenario: Snapshot is regenerated from identical input and runtime
- **WHEN** the builder runs twice from byte-identical draft and Skill Index inputs under identical Python and Unicode-data versions into fresh targets
- **THEN** the source candidates, manifest, and review queue are byte-identical
- **AND** all aggregate and per-line SHA-256 values match

#### Scenario: Snapshot is regenerated under another supported runtime
- **WHEN** byte-identical draft and Skill Index inputs are built under a different Python or Unicode-data version
- **THEN** source-candidate and review-queue bytes remain identical
- **AND** the manifest records the actual runtime identifiers while every non-runtime value remains identical

#### Scenario: Insignificant-looking serialization changes
- **WHEN** a candidate line is reordered, re-escaped, loses its LF, gains whitespace, or changes Unicode bytes without changing parsed values
- **THEN** exact-byte validation rejects the snapshot
- **AND** parsed-value equality does not substitute for the bound bytes

### Requirement: Review queue is a blank controlled copy
The source builder SHALL write `review-queue.csv` with one row for every source record using the exact declared header. Canonical display values MUST come only from the bound Skill Index; every other non-human value MUST be an exact copy or deterministic projection of the source row. `decision`, `reviewer`, and `reason` SHALL be exactly empty in the frozen queue. The builder MUST NOT create `review-decisions.csv`, assign a reviewer, propose a decision, or write model suggestions.

#### Scenario: Initial queue is generated
- **WHEN** a valid source snapshot is published
- **THEN** the queue has the exact header and 192 rows bound by the source manifest
- **AND** all human cells are blank
- **AND** `review-decisions.csv` is absent

#### Scenario: Queue generator suggests acceptance
- **WHEN** any code path tries to prefill, default, infer, recommend, or model-generate a decision, reviewer, or reason
- **THEN** generation fails before snapshot publication
- **AND** no such suggestion is stored in another source field

### Requirement: Source snapshot freezes at commit A and stops for review
The first apply slice SHALL include only the v4 source authoring, validation, generated snapshot, tests, and authoritative OpenSpec artifacts. After fresh validation it SHALL create exactly one source-snapshot commit with message `data(router): freeze Router V2 reviewed-data source snapshot`. After that commit, the workflow MUST check for a completed `data/router-v2-v4/review-decisions.csv`; when the file is absent or incomplete, it MUST stop and report the commit, snapshot paths and hashes, exact counts, 16/16 coverage, family checks, duplicate checks, required human fields, and the exact truth markers `PENDING_REVIEW`, `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`. It MUST NOT accept a row or continue into reviewed-package construction automatically.

#### Scenario: Commit A has no human decisions
- **WHEN** the validated source snapshot commit exists and `review-decisions.csv` is absent
- **THEN** the workflow reports the mandatory human-review handoff and stops
- **AND** it reports exactly `PENDING_REVIEW`, `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`
- **AND** no accepted-pair, qualification-PASS, training-input, preflight-PASS, training, or checkpoint artifact is created
- **AND** the post-commit gate remains an unchecked OpenSpec task and is reported only in the conversation so the worktree stays clean

#### Scenario: A partial decision file appears
- **WHEN** `review-decisions.csv` exists but any frozen source row is missing or has blank human evidence
- **THEN** the workflow remains `REVIEW_REQUIRED` and stops
- **AND** blanks are not interpreted as rejection or acceptance

### Requirement: Human decisions are complete, compatible, and attributable
The decision importer SHALL require exactly one decision row for every frozen source record, the exact queue header and row count, unique source IDs, byte-equivalent non-human fields, and non-empty human-supplied `decision`, `reviewer`, and `reason`. Allowed decisions are exactly `ACCEPT_POSITIVE`, `TRUE_HARD_NEGATIVE`, `SECONDARY_POSITIVE`, `AMBIGUOUS_MULTI_SKILL`, `EASY_NEGATIVE`, `NO_SKILL_CONFIRMED`, `SOURCE_LABEL_DEFECT`, and `REJECT_DRAFT`. It MUST reject unknown, extra, duplicate, normalized, partially completed, or source-mutating rows as a whole.

Role compatibility SHALL be exhaustive: `POSITIVE` accepts only `ACCEPT_POSITIVE`, `AMBIGUOUS_MULTI_SKILL`, `SOURCE_LABEL_DEFECT`, or `REJECT_DRAFT`; `HARD_NEGATIVE_CANDIDATE` accepts only `TRUE_HARD_NEGATIVE`, `SECONDARY_POSITIVE`, `AMBIGUOUS_MULTI_SKILL`, `EASY_NEGATIVE`, `SOURCE_LABEL_DEFECT`, or `REJECT_DRAFT`; and `NO_SKILL_CANDIDATE` accepts only `NO_SKILL_CONFIRMED`, `AMBIGUOUS_MULTI_SKILL`, `SOURCE_LABEL_DEFECT`, or `REJECT_DRAFT`. Every other role-decision pairing MUST reject the decision file. Non-accepting diagnostic decisions MUST NOT enter training. A pilot with one distinct reviewer MAY pass only when the qualification report discloses `single_reviewer_pilot=true` as a limitation; the system MUST NOT infer independent review.

#### Scenario: Complete human decision file is imported
- **WHEN** every frozen row has an allowed role-compatible decision and non-empty reviewer and reason supplied in the decision file
- **THEN** import preserves the exact source snapshot and emits a decision-bound intermediate result
- **AND** it records the actual distinct reviewer count without inventing identity

#### Scenario: Non-human queue field is changed
- **WHEN** a reviewer edits prompt, skill, role, split, family, source ID, source-line hash, or another frozen field
- **THEN** the entire decision file is rejected
- **AND** the importer does not repair the field from the snapshot and continue

### Requirement: Reviewed package gates are independently recomputed
The reviewed v4 package SHALL require at least 64 accepted train positives, at least 48 `TRUE_HARD_NEGATIVE` train rows, 100 through 160 accepted train pairs inclusive, exactly 16 accepted calibration positives, exactly 16 accepted non-blind-test positives, at least 16 `NO_SKILL_CONFIRMED` rows in each evaluation split, accepted train-positive coverage of all 16 skills, at most one accepted positive per `task_id`, split-family disjointness, and zero blocker codes. Only `TRUE_HARD_NEGATIVE` SHALL enter training as a hard negative. `SECONDARY_POSITIVE` SHALL be remapped to a positive for that row's candidate `skill_id`, SHALL count toward the minimum 64 accepted train positives and 16/16 positive coverage, and SHALL NOT count as a true hard negative. An owner `ACCEPT_POSITIVE` and same-draft `SECONDARY_POSITIVE` MUST NOT both enter training because their identical query would create a multi-skill positive conflict. Calibration, non-blind-test, and no-skill rows MUST remain excluded from embedding training. Because the frozen source has only 128 train rows, the effective pilot maximum is 128 accepted train pairs; the approved 160 policy ceiling MUST NOT authorize another source or synthetic row.

The package, split manifest, qualification report, and training-input manifest MUST independently recompute counts, identities, and hashes and agree. They SHALL bind the source snapshot ID and commit, source manifest, source candidates, review decisions, accepted pairs, and split manifest. `router_decision` SHALL remain exactly `KEEP_BASELINE`.

#### Scenario: All reviewed-data minimums pass
- **WHEN** complete human decisions satisfy every count, coverage, split, provenance, and blocker rule
- **THEN** the reviewed package may become eligible for training preflight
- **AND** the qualification result still records `KEEP_BASELINE` and no training or improvement claim

#### Scenario: Forty-seven true hard negatives remain
- **WHEN** every other reviewed-data gate passes but only 47 rows are `TRUE_HARD_NEGATIVE`
- **THEN** the package remains blocked
- **AND** `EASY_NEGATIVE`, `AMBIGUOUS_MULTI_SKILL`, or blank decisions do not fill the minimum
