## ADDED Requirements

### Requirement: Training admission uses an exact v3 package contract
The trainer SHALL accept input only through a JSON manifest with exactly these required and allowed top-level fields: `schema_version`, `artifact_version`, `policy_id`, `package_id`, `accepted_pairs`, and `qualification_report`. Unknown or missing top-level fields MUST be rejected. `schema_version` MUST equal `router-training-data-v2-training-input-manifest-v3`, `artifact_version` MUST be the integer `3`, `policy_id` MUST equal `router-training-data-v2-training-admission-v3`, and `package_id` MUST be a string whose `value.strip()` is non-empty. This predicate MUST NOT trim or replace the package ID: the exact original bytes MUST be stored in the handoff and bound by its secret-keyed canonical content fingerprint.

`accepted_pairs` SHALL be an object with exactly `path`, `sha256`, and `row_count`; `qualification_report` SHALL be an object with exactly `path` and `sha256`. Unknown or missing nested fields MUST be rejected. Each `sha256` MUST be a 64-character lowercase hexadecimal SHA-256, and `row_count` MUST be a positive integer equal to the number of parsed accepted rows. The bound qualification report MUST use `schema_version="router-training-data-v2-qualification-report-v3"`, `artifact_version=3`, and `policy_id="router-training-data-v2-qualification-v3"`; it MUST set `can_start_training=true`, MUST expose `blocker_codes=[]`, and its `counts.accepted_train_pair_count` MUST equal both `accepted_pairs.row_count` and the parsed accepted-row count.

The package root SHALL be the manifest's parent directory. Both nested `path` values MUST be non-empty canonical POSIX-relative strings interpreted from that root. A path MUST be rejected if it is absolute, is `.` or contains an empty, `.` or `..` segment, contains a backslash, is not already in canonical POSIX form, traverses any symlink component or symlink target, resolves outside the package root, or resolves to anything other than an existing regular file. The accepted-pairs and qualification-report references MUST resolve to distinct files. Path, SHA-256, and count validation MUST complete before either file is admitted as package content.

#### Scenario: Fully bound v3 package is admitted
- **WHEN** a package uses all three exact v3 identifiers, both bound files match their declared paths and SHA-256 values, all accepted counts agree, and the bound report has `can_start_training=true` with no blocker codes
- **THEN** package-level validation succeeds
- **AND** row-level validation proceeds over the entire accepted-pairs artifact

#### Scenario: Manifest shape is open-ended or incomplete
- **WHEN** the manifest or either nested object has any unknown field or lacks any exact required field
- **THEN** the entire package is rejected
- **AND** no compatibility, default value, or inferred field is applied

#### Scenario: Package identity is whitespace-only or padded
- **WHEN** `package_id` is whitespace-only
- **THEN** the package is rejected before any handoff is constructed
- **AND** when a non-blank package ID has leading or trailing whitespace, those exact bytes are preserved and bound by the genuine handoff fingerprint rather than trimmed

#### Scenario: Bound path is unsafe or aliases the other input
- **WHEN** either bound path is absolute, non-canonical, contains `.`, `..`, an empty segment or backslash, traverses a symlink, names a non-regular file, escapes the package root, or both references resolve to the same file
- **THEN** the entire package is rejected before row or report content is consumed
- **AND** a matching declared hash does not make the path admissible

#### Scenario: Bound report is not training-ready
- **WHEN** the bound qualification report sets `can_start_training=false`, has one or more blocker codes, or reports an accepted count different from the manifest or parsed rows
- **THEN** the entire package is rejected
- **AND** no row is admitted for training

### Requirement: Every admitted row is an exact accepted-pair v3 record
Every admitted row SHALL be a JSON object with exactly these required and allowed fields:

`schema_version`, `artifact_version`, `policy_id`, `accepted_record_id`, `pair_id`, `source_record_id`, `source_schema_version`, `source_kind`, `source_dataset_id`, `source_artifact_path`, `source_split`, `candidate_type`, `task_id`, `skill_id`, `query_text`, `query_text_policy`, `prompt_text_sha256`, `skill_text`, `accepted_for_training`, `training_split`, `supervision_label`, `review_status`, `reviewer`, `review_reason`, `source_hash`, and `acceptance_hash`.

Every listed field is required and every unlisted field is forbidden. An unknown or missing field MUST reject the entire package. In particular, `label`, category/difficulty/robustness/family metadata, and every legacy, alternate, composite, or second task-query field are forbidden. The row SHALL set `schema_version="router-training-data-v2-accepted-pair-v3"`, integer `artifact_version=3`, `policy_id="router-training-data-v2-training-admission-v3"`, `source_schema_version="router-training-data-v2-candidate-v3"`, `query_text_policy="prompt_only"`, `accepted_for_training=true`, and `training_split="train"`. `accepted_record_id`, `pair_id`, `source_record_id`, `task_id`, `skill_id`, `query_text`, `skill_text`, `reviewer`, and `review_reason` MUST each be a string whose `value.strip()` is non-empty. This predicate MUST NOT trim, normalize, or replace the stored value: prompt and canonical hashes continue to bind the exact original UTF-8 text. `prompt_text_sha256`, `source_hash`, and `acceptance_hash` MUST each be a 64-character lowercase hexadecimal SHA-256, and `prompt_text_sha256` MUST equal SHA-256 over the exact UTF-8 bytes of `query_text`.

The only valid bidirectional supervision/review relations are `supervision_label="POSITIVE"` if and only if `review_status="ACCEPTED_POSITIVE"`, and `supervision_label="HARD_NEGATIVE"` if and only if `review_status="ACCEPTED_HARD_NEGATIVE"`.

#### Scenario: Formally accepted positive is valid
- **WHEN** a v3 row has prompt-only query binding, `accepted_for_training=true`, `training_split="train"`, `supervision_label="POSITIVE"`, `review_status="ACCEPTED_POSITIVE"`, and non-empty reviewer evidence
- **THEN** the row satisfies the supervision and review relation
- **AND** validation continues to its provenance and canonical hashes

#### Scenario: Row has an unknown field or omits an exact field
- **WHEN** an accepted row adds any unlisted field, including `label` or a second task-query representation, or omits any required field
- **THEN** the entire package is rejected
- **AND** the field is not ignored, defaulted, normalized, or upgraded

#### Scenario: Human-reviewed hard negative is valid
- **WHEN** a v3 row has prompt-only query binding, `accepted_for_training=true`, `training_split="train"`, `supervision_label="HARD_NEGATIVE"`, `review_status="ACCEPTED_HARD_NEGATIVE"`, and non-empty reviewer evidence
- **THEN** the row satisfies the supervision and review relation
- **AND** validation continues to its provenance and canonical hashes

#### Scenario: Raw label is not authorization
- **WHEN** a row has a raw benchmark `label`, a known gold skill, or another source annotation but lacks the exact accepted-row schema, acceptance flag, split, review status, reviewer, or review reason
- **THEN** the entire package is rejected
- **AND** the raw label or annotation is not upgraded, inferred, or treated as training authorization

#### Scenario: Whitespace-only identity or evidence is rejected
- **WHEN** any of `accepted_record_id`, `pair_id`, `source_record_id`, `task_id`, `skill_id`, `query_text`, `skill_text`, `reviewer`, or `review_reason` contains only whitespace
- **THEN** the entire package is rejected
- **AND** a non-blank value with leading or trailing whitespace is preserved byte-for-byte for canonical hashing rather than trimmed

### Requirement: Source admission and identities are exact and default-deny
Every admitted row SHALL set `source_kind="ROUTER_TRAINING_DATA_V2_CANDIDATE"`, `source_dataset_id="router-training-data-v2-qualification-pack"`, `source_artifact_path="docs/demo/router-training-data-v2-qualification-pack/candidate-pairs.jsonl"`, and `source_split="dev"`. The gate MUST compare these values exactly and MUST NOT infer an allowed source from path substrings, the absence of a forbidden word, or free-text provenance. `source_artifact_path` is a bound provenance value; the trainer MUST NOT reopen it as an alternate input after package validation.

The only admitted role mappings are:

- `candidate_type="positive"` if and only if `supervision_label="POSITIVE"` and `review_status="ACCEPTED_POSITIVE"`.
- `candidate_type="same_category_negative_candidate"` if and only if `supervision_label="HARD_NEGATIVE"` and `review_status="ACCEPTED_HARD_NEGATIVE"`.

Every other `source_kind`, dataset, artifact path, source split, candidate type, or role mapping is denied by default. This includes legacy, provisional, cross-category easy-negative, source-test/reserved, blind-derived, Phase 16-derived, and unknown sources even when their free text claims human review.

`accepted_record_id`, `pair_id`, and `source_record_id` MUST each be a non-blank string and MUST each be independently unique across the complete package. The source-identity tuple `(source_kind, source_dataset_id, source_artifact_path, source_record_id)` MUST also be unique across the complete package.

#### Scenario: Exact positive source is reviewed and accepted
- **WHEN** an exact allowlisted `dev` candidate has `candidate_type="positive"`, `supervision_label="POSITIVE"`, `review_status="ACCEPTED_POSITIVE"`, and all other row relations are valid
- **THEN** source and role validation succeeds
- **AND** validation continues without consulting a raw label or source artifact

#### Scenario: Exact same-category negative is reviewed and accepted
- **WHEN** an exact allowlisted `dev` candidate has `candidate_type="same_category_negative_candidate"`, `supervision_label="HARD_NEGATIVE"`, `review_status="ACCEPTED_HARD_NEGATIVE"`, and all other row relations are valid
- **THEN** source and role validation succeeds
- **AND** the negative is not admitted from a raw label, easy-negative type, or inferred review evidence

#### Scenario: Provenance is unsupported but looks safe
- **WHEN** a row changes any exact allowlisted provenance value or role mapping, including to a non-blind-looking path or free text that claims acceptance
- **THEN** the entire package is rejected by default
- **AND** no substring, path-name, or free-text heuristic can authorize it

#### Scenario: Any stable identity is duplicated
- **WHEN** two rows share an `accepted_record_id`, `pair_id`, `source_record_id`, or source-identity tuple
- **THEN** the entire package is rejected
- **AND** otherwise different hashes or review fields do not make either duplicate admissible

### Requirement: Canonical hashes bind source content and acceptance separately
Every accepted row MUST carry a `source_hash` and an `acceptance_hash`, each recomputed from parsed values rather than trusted from the row. The `source_hash` payload SHALL contain exactly `source_record_id`, `pair_id`, `source_schema_version`, `source_kind`, `source_dataset_id`, `source_artifact_path`, `source_split`, `candidate_type`, `task_id`, `skill_id`, `query_text`, `query_text_policy`, `prompt_text_sha256`, and `skill_text`, copied without trimming, normalization, inference, or additional keys. The `acceptance_hash` payload SHALL contain exactly the verified `source_hash`, `policy_id`, `accepted_record_id`, `pair_id`, `supervision_label`, `accepted_for_training`, `training_split`, `review_status`, `reviewer`, and `review_reason`, again with no additional keys.

Each payload SHALL be serialized equivalently to `json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`, encoded directly as UTF-8, and hashed with SHA-256. Object keys are sorted, array order is preserved, compact separators add no insignificant whitespace, and no newline or other byte is appended. As a serialization-only example, parsed payload `{"z":[2,1],"a":"x"}` produces exactly the UTF-8 bytes for `{"a":"x","z":[2,1]}` with no trailing newline. Hashes establish content and decision integrity only. They do not prove source authenticity and MUST NOT replace stable identifiers, exact provenance, or reviewer evidence. Binding accepted rows to an independently authenticated source snapshot is a deferred prerequisite for a separately authorized reviewed-data phase; this change MUST NOT add a blind/task-ID/path substring heuristic or widen the exact source allowlist as a substitute.

#### Scenario: Source content is tampered
- **WHEN** a source-bound prompt, query hash, skill value, source identifier, split, or provenance value changes without a matching canonical `source_hash`
- **THEN** the entire package is rejected
- **AND** no acceptance record is consumed

#### Scenario: Acceptance evidence is tampered
- **WHEN** a supervision label, acceptance flag, training split, review status, reviewer, or review reason changes without a matching canonical `acceptance_hash`
- **THEN** the entire package is rejected
- **AND** an unchanged `source_hash` does not authorize the changed decision

#### Scenario: Canonical serialization changes
- **WHEN** a hash is computed with unsorted keys, ASCII escaping, non-compact separators, reordered array values, a trailing newline, omitted payload fields, or extra payload fields
- **THEN** the recomputed canonical digest does not match and the entire package is rejected
- **AND** semantically similar non-canonical JSON is insufficient

#### Scenario: Valid hashes do not prove source authenticity
- **WHEN** source and acceptance hashes recompute successfully for an exact allowlisted row
- **THEN** they prove only integrity of the serialized source content and acceptance decision
- **AND** independent source-snapshot authenticity remains a deferred prerequisite without blind substring inference or protected-data access in this change

### Requirement: Validation is whole-package and fail-closed
The gate MUST validate every exact manifest and nested-object field, every safe package reference, the bound report, and every exact accepted-row field before returning any training example. It MUST reject the entire package for an unknown or missing field; a legacy or unversioned manifest or row; unsupported provenance or role mapping; a provisional candidate; a cross-category easy negative; a reserved source-test row; a blind-derived or Phase 16-derived row; invalid review evidence; a missing, unsafe, aliased, or mismatched file/hash/count; a tampered canonical hash; or any duplicate required identity. Invalid rows MUST NOT be filtered, skipped, repaired, inferred, upgraded, or partially consumed. No CLI flag, environment variable, alternate loader, compatibility mode, direct trainer API, path heuristic, free-text provenance, directly constructed dataclass, or forged object MAY bypass the v3 gate.

#### Scenario: One row is invalid among otherwise valid rows
- **WHEN** any one row is missing, malformed, tampered, duplicated, provisional, easy-negative, source-test-reserved, blind-derived, Phase 16-derived, or unsupported
- **THEN** the entire package is rejected
- **AND** zero rows are returned to the trainer

#### Scenario: Legacy input requests compatibility
- **WHEN** a caller supplies legacy Phase 14 pairs, a v1 or v2 qualification artifact, an unversioned pair file, or requests a compatibility or bypass mode
- **THEN** the entire input is rejected
- **AND** the gate does not infer v3 acceptance or review fields

#### Scenario: Current blocked qualification pack is supplied
- **WHEN** the current canonical qualification report with `REVIEW_REQUIRED`, `KEEP_BASELINE`, `can_start_training=false`, eight blocker codes, and zero accepted train pairs is bound to a training manifest
- **THEN** the package is rejected
- **AND** the current diagnostic candidates are not treated as accepted training rows

### Requirement: Legacy embedding export remains diagnostic-only
The legacy `export-embedding-training-data` workflow MAY emit versioned, prompt-only diagnostic candidates for inspection or compatibility diagnostics. Every emitted diagnostic row MUST use the shared prompt-only query contract and set `accepted_for_training=false`, and the export result MUST set `can_start_training=false`. The exporter MUST NOT describe an unreviewed negative as an accepted hard negative, mint formal `review_status`, `reviewer`, or `review_reason` evidence, generate admission `source_hash` or `acceptance_hash` values, generate a `router-training-data-v2-training-input-manifest-v3`, or present its output as trainer-ready. Exporter output is categorically outside the v3 admission contract and the trainer MUST reject it rather than infer, upgrade, or synthesize acceptance evidence.

#### Scenario: Versioned prompt-only diagnostics are exported
- **WHEN** `export-embedding-training-data` runs successfully on allowed diagnostic inputs
- **THEN** it emits only versioned prompt-only diagnostic candidates with `accepted_for_training=false`
- **AND** its result sets `can_start_training=false`
- **AND** it emits no formal review evidence, admission hashes, or training-input manifest

#### Scenario: Trainer receives legacy exporter output
- **WHEN** any diagnostic output from `export-embedding-training-data` is supplied to the trainer
- **THEN** the entire input is rejected before framework, GPU, model, or output side effects
- **AND** the trainer does not infer an accepted positive or accepted hard negative from labels, candidate types, or diagnostic metadata

### Requirement: The gate runs before frameworks, GPU, models, and outputs
Complete package validation SHALL run in a standard-library-only bootstrap before importing `torch`, importing `sentence_transformers`, initializing or querying a GPU runtime, importing model-dependent trainer modules, constructing or loading a model, creating an output directory, opening a training output, or writing a log, checkpoint, or other training artifact. A rejected package MUST leave all of those framework and output side effects unstarted.

#### Scenario: Invalid package fails before framework import
- **WHEN** package or row validation fails
- **THEN** neither `torch` nor `sentence_transformers` has been imported by the training process
- **AND** no GPU, model, output directory, log, or checkpoint side effect has begun

#### Scenario: Valid package crosses the bootstrap boundary once
- **WHEN** the complete manifest and every accepted row pass validation
- **THEN** one immutable, ordered collection containing every validated row exactly once may be handed to the framework-dependent training path
- **AND** framework imports, GPU handling, model loading, and output creation remain downstream of that successful gate

#### Scenario: Fresh process proves invalid input cannot import frameworks
- **WHEN** the actual trainer script runs in a fresh Python process with an invalid manifest or an invalid accepted row and shadow `torch` and `sentence_transformers` modules whose import would write a sentinel
- **THEN** the process exits nonzero with the stable training-input gate error
- **AND** neither the import sentinel nor the configured output root exists

### Requirement: Downstream training consumes only the accepted prompt-only handoff
After whole-package validation succeeds, the gate SHALL produce exactly one immutable handoff that preserves accepted-row file order and contains every accepted row exactly once. The example and handoff constructors MUST require one unexported validation seal held only inside the loader/verifier closure, MUST store that seal in frozen slots, and MUST reject an ordinary constructor call without the closure token. The same closure SHALL hold a separate secret used to compute a canonical keyed fingerprint for every example's four exposed fields and for the handoff package ID plus every complete example in file order. Each object MUST store its fingerprint in a frozen slot, but the fingerprint secret MUST NOT be stored in an instance. The seal, fingerprint secret, and authorized builder MUST NOT exist as module-global objects. The module SHALL expose an internal verifier that shares the closure seal and fingerprint secret. The downstream training function MUST invoke that verifier as its first operation, before grouping, framework import, model/GPU access, or output handling. Verification MUST reject a wrong handoff type, a missing or forged handoff seal, a non-tuple collection, a wrong example type, any missing or forged example seal, any example fingerprint mismatch, or any handoff fingerprint mismatch caused by package-ID, field, membership, order, or collection replacement.

Only after seal verification succeeds MAY the downstream trainer group examples, and it MUST group only by `supervision_label` (`POSITIVE` or `HARD_NEGATIVE`). For every example it MUST derive the task-side model input only as `router_query_text(query_text)` and MAY use `skill_text` only as the separate skill-side model input. It MUST NOT read, reconstruct, or infer a raw `label`, category, candidate type, source path, source dataset, source split, or other source metadata as a model input, grouping key, weight, gate, or target. It MUST NOT reopen the source artifact or qualification pack after handoff.

#### Scenario: Valid rows are grouped for the trainer
- **WHEN** a fully valid package contains accepted positives and accepted hard negatives
- **THEN** the immutable handoff groups them only by `supervision_label`
- **AND** each task-side input is byte-identical to `router_query_text(query_text)`
- **AND** source metadata and forbidden raw labels are not reread or converted into training features

#### Scenario: Handoff is attempted before whole-package success
- **WHEN** any package, report, path, row, identity, provenance, review, or hash check has not succeeded
- **THEN** no mutable or immutable handoff is created
- **AND** zero rows reach framework-dependent code

#### Scenario: Ordinary constructor forgery is rejected
- **WHEN** an ordinary caller invokes an example or handoff constructor without the closure-held validation seal or supplies an arbitrary replacement token
- **THEN** construction is rejected
- **AND** no framework import, model/GPU access, grouping, or output side effect occurs

#### Scenario: Object-level forged handoff is rejected downstream
- **WHEN** a caller uses `object.__new__` and low-level attribute assignment to forge a handoff or example without the authentic closure-held seal
- **THEN** the downstream verifier rejects it as its first operation
- **AND** no framework import, model/GPU access, grouping, or output side effect occurs

#### Scenario: Genuine sealed content is mutated through low-level assignment
- **WHEN** a caller uses `object.__setattr__` to change a field on a genuine sealed example, change the genuine package ID, or replace/reorder the genuine handoff's examples
- **THEN** the downstream verifier detects a secret-keyed content fingerprint mismatch as its first operation
- **AND** no framework import, model/GPU access, grouping, or output side effect occurs

### Requirement: New trainer artifacts use exact Router Training Data V2 v3 lineage
Every train config generated for this gate SHALL set `schema_version="router-training-data-v2-train-config-v3"`, integer `artifact_version=3`, `policy_id="router-training-data-v2-training-admission-v3"`, and `artifact_type="router-training-data-v2-train-config"`; it MUST NOT contain `phase`. Every train-run summary written by this trainer SHALL set `schema_version="router-training-data-v2-train-run-summary-v3"`, integer `artifact_version=3`, the same admission policy, and `artifact_type="router-training-data-v2-train-run-summary"`; it MUST NOT contain `phase` or identify itself as Phase 14.

Every model manifest written by this trainer SHALL set `schema_version="router-training-data-v2-model-manifest-v3"`, integer `artifact_version=3`, the same admission policy, and `artifact_type="router-training-data-v2-model-manifest"`; it MUST NOT contain `phase` or identify itself as Phase 15. The shared historical `model_manifest` defaults, APIs, and committed Phase 14–18 artifacts MUST remain unchanged. This trainer MAY call the shared inventory builder only after admission succeeds, but MUST replace historical identity in memory before writing its own manifest. Generated model-card title, prose, and example command SHALL use Router Training Data V2 v3 wording and a neutral v3 train-config path; they MUST NOT describe the new work or config as Phase 14.

#### Scenario: Config and run summary use new lineage
- **WHEN** a v3 train config is built and a synthetic accepted handoff reaches the fake downstream training path
- **THEN** the config and run summary expose their exact Router Training Data V2 v3 schema, artifact, and policy identifiers
- **AND** neither artifact contains `phase` or a Phase 14 identity

#### Scenario: Trainer model manifest uses new lineage without rewriting history
- **WHEN** the fake downstream path writes a model file inventory
- **THEN** the trainer-written manifest exposes the exact Router Training Data V2 model-manifest v3 identity and no `phase`
- **AND** the shared historical manifest writer defaults and every protected Phase 14–18 artifact remain unchanged

#### Scenario: Generated model card does not reuse Phase 14 lineage
- **WHEN** a model card is rendered for the v3 train config
- **THEN** its title, prose, and example command identify Router Training Data V2 v3 rather than Phase 14
- **AND** it points to a neutral v3 train-config path rather than the historical Phase 14 config

### Requirement: This change validates only a synthetic passing fixture
This change MUST NOT create a real `router-training-data-v2-training-input-manifest-v3` package, real accepted-pair v3 artifact, reviewed positive set, reviewed hard-negative set, or production qualification report with `can_start_training=true`. Tests MAY construct a minimal temporary synthetic package, synthetic accepted rows, and a synthetic v3 qualification report with `can_start_training=true` and `blocker_codes=[]` solely to prove that the valid branch and immutable downstream handoff are reachable. Such fixtures MUST be clearly synthetic, MUST NOT reference protected Phase 14–18 or blind data, MUST group only by `supervision_label`, MUST use `router_query_text(query_text)` for task-side input, and MUST NOT be committed, published, or represented as trainer-ready project data.

#### Scenario: Synthetic valid fixture exercises the success path
- **WHEN** a test builds a fully self-consistent synthetic v3 package that satisfies every package, row, hash, and review relation
- **THEN** the gate accepts that fixture for test purposes
- **AND** it makes one immutable prompt-only handoff grouped by `supervision_label`
- **AND** the fixture and synthetic true report are not written to the canonical qualification pack or presented as real reviewed data

#### Scenario: Apply completes without real training input
- **WHEN** this bounded contract change is implemented and validated
- **THEN** no real training-input manifest or accepted-pair artifact is generated
- **AND** no training, GPU/A100 job, model load, output directory, or checkpoint is started
