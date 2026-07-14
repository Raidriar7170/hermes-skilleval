## ADDED Requirements

### Requirement: Pilot is bound to the frozen Router V2 v4 source
The validator SHALL accept only snapshot `router-v2-v4-source-38afe7d5b2500d4a`, source commit `751bb678bf9fb63a357ff3667e3508a0f5ed83a2`, the pinned source-candidate and source-manifest SHA-256 values, and the exact 192 source identities and exact-row hashes in manifest order.

#### Scenario: Frozen source binding is intact
- **WHEN** all pilot artifacts match the pinned snapshot, commit, source hashes, ordered identities, and exact-row hashes
- **THEN** source-binding validation passes

#### Scenario: Frozen source binding drifts
- **WHEN** any snapshot, commit, source hash, row identity, row order, or exact-row hash differs
- **THEN** validation fails without normalizing or repairing the artifact

### Requirement: Every object preserves model-only truth
Every JSON object SHALL carry exactly the required `MODEL_ONLY_PILOT` truth fields plus `human_review_status=REVIEW_REQUIRED`, `admission_effect=NONE`, `can_start_preflight=false`, and `can_start_training=false`.

#### Scenario: Truth fields are complete
- **WHEN** every manifest, pass, adjudication, and summary object carries the exact required truth values
- **THEN** truth-surface validation passes

#### Scenario: A truth value is omitted or inflated
- **WHEN** any object omits a required truth field or implies human review, release eligibility, admission, preflight, training, or router promotion
- **THEN** validation fails

### Requirement: Two isolated model passes cover every source row
The pilot SHALL contain exactly two pass files with identities `MODEL_PASS_1` and `MODEL_PASS_2`, each containing exactly 192 canonically ordered model-opinion rows. The passes MUST have distinct run IDs and each MUST state that the other pass output was not provided.

#### Scenario: Two full isolated passes are present
- **WHEN** both pass files contain the exact source rows in order, carry their fixed pass identity, have distinct run IDs, and declare the required isolation condition
- **THEN** pass validation succeeds

#### Scenario: Pass coverage or isolation is invalid
- **WHEN** a pass is missing, partial, duplicated, reordered, mislabeled, reuses the other run ID, or claims access to the other pass output
- **THEN** validation fails

### Requirement: Model opinions are role-compatible and non-admissible
Each pass and adjudication row SHALL use only the model-opinion values permitted for its frozen source role. Rows MUST NOT contain `reviewer`, human `decision`, acceptance, qualification, or admission semantics.

#### Scenario: Opinion matches source role
- **WHEN** a row uses a permitted supported, disputed, or uncertain opinion for its source role and contains no forbidden field
- **THEN** opinion validation passes

#### Scenario: Opinion resembles an admission decision
- **WHEN** a row uses another role's opinion or contains a forbidden review, acceptance, qualification, or admission field
- **THEN** validation fails

### Requirement: Adjudication binds both model pass rows
The adjudication file SHALL contain exactly 192 rows in frozen order and each row SHALL bind the corresponding pass-1 and pass-2 row hashes, record whether the opinions agree, and contain a role-compatible adjudicated model opinion.

#### Scenario: Adjudication is complete and bound
- **WHEN** every adjudication row has the exact two pass-row hashes and an agreement flag consistent with the two opinions
- **THEN** adjudication validation passes

#### Scenario: Adjudication does not match its inputs
- **WHEN** a bound row hash, agreement flag, row order, or adjudicated opinion is inconsistent
- **THEN** validation fails

### Requirement: Artifacts use deterministic canonical encoding
All JSON and JSONL objects SHALL use UTF-8 canonical JSON with sorted keys, compact separators, exactly one final LF per object, no duplicate keys, and validated SHA-256 values. Each model row SHALL carry a hash of its canonical object with the row hash field omitted.

#### Scenario: Canonical bytes and hashes match
- **WHEN** artifact bytes exactly match canonical serialization and all declared hashes recompute
- **THEN** deterministic encoding validation passes

#### Scenario: Equivalent but non-canonical JSON is supplied
- **WHEN** JSON parses but whitespace, key order, duplicate keys, line termination, or a declared hash differs
- **THEN** validation fails

### Requirement: Unknown provenance is explicit and never inferred
Model and prompt provenance fields SHALL contain a non-empty recorded value or the exact marker `UNAVAILABLE`. The validator MUST NOT infer missing metadata from environment, filenames, or model output.

#### Scenario: Provenance is unavailable
- **WHEN** a model or prompt identifier cannot be obtained
- **THEN** the artifact records `UNAVAILABLE` and remains truthful

#### Scenario: Provenance is silently omitted
- **WHEN** a required provenance field is empty, null, absent, or inferred by the validator
- **THEN** validation fails

### Requirement: Pilot has no downstream gate effect
The validator SHALL reject `review-decisions.csv`, paths outside `artifacts/router-v2-v4/model-only-pilot/<pilot-id>/`, or declarations that the pilot feeds qualification, accepted pairs, training input, preflight, training, release, or router promotion. It SHALL leave the existing human-review change tasks untouched.

#### Scenario: Pilot remains diagnostic-only
- **WHEN** the artifact tree uses only the model-only namespace and every object states no admission effect and fail-closed gate values
- **THEN** the pilot can be validated as internal diagnostic evidence while `KEEP_BASELINE` remains in force

#### Scenario: Pilot attempts downstream consumption
- **WHEN** an artifact or repository state attempts to create or consume human review decisions, qualification, admission, preflight, training, release, or promotion inputs
- **THEN** validation fails
