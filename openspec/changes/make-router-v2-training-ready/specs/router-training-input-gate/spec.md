## ADDED Requirements

### Requirement: V4 admission binds the authenticated reviewed source chain
The v4 training-input gate SHALL accept only an exact-shape v4 manifest and rows whose identifiers, paths, counts, and SHA-256 values bind the immutable source snapshot, source manifest, source candidates, completed human decisions, split manifest, reviewed qualification report, and accepted pairs. It MUST verify the source snapshot ID and exact commit identity, every referenced safe package-root path, every file hash and row count, and every source-record lineage link before returning any training example. Unknown, missing, legacy, mixed-version, aliased, unsafe, uncommitted, dirty, or independently rewritten inputs MUST reject the entire package as `TRAINING_INPUT_INVALID`.

#### Scenario: Complete v4 lineage is admitted
- **WHEN** the exact source, review, split, qualification, accepted-pair, and manifest chain validates with no unknown fields or mismatches
- **THEN** one immutable v4 handoff is constructed from the accepted rows
- **AND** the loader does not reopen source or review files after handoff

#### Scenario: Acceptance package rewrites its own source hash
- **WHEN** a source row and a producer-supplied digest are changed together but no longer match the independently frozen commit-A bytes
- **THEN** the complete input is rejected as `TRAINING_INPUT_INVALID`
- **AND** self-consistent local hashes do not establish source authenticity

### Requirement: V4 training manifest paths and bindings are exact
`data/router-v2-v4/training-input-manifest.json` SHALL contain exactly
`schema_version`, `artifact_version`, `policy_id`, `package_id`,
`source_snapshot`, `source_manifest`, `source_candidates`, `review_decisions`,
`split_manifest`, `accepted_pairs`, and `qualification_report`, with constants
`schema_version="router-training-data-v2-training-input-manifest-v4"`, integer
`artifact_version=4`, and
`policy_id="router-training-data-v2-training-admission-v4"`.
`source_snapshot` SHALL contain exactly `snapshot_id` and `commit`, where commit
is the independently supplied full lowercase 40-hex commit A.

Bindings and paths are closed sets relative to the manifest parent:

- `source_manifest` has exactly
  `{path:"source-manifest.json", sha256}`;
- `source_candidates` has exactly
  `{path:"source-candidates.jsonl", sha256, row_count:192}`;
- `review_decisions` has exactly
  `{path:"review-decisions.csv", sha256, row_count:192}`;
- `split_manifest` has exactly
  `{path:"split-manifest.json", sha256}`;
- `accepted_pairs` has exactly
  `{path:"accepted-pairs.jsonl", sha256, row_count}`;
- `qualification_report` has exactly
  `{path:"qualification-report.json", sha256}`.

No alternate path or field is valid. All bindings MUST resolve to distinct
existing regular files below the package root and reject absolute paths,
backslashes, empty, dot, or dot-dot segments, noncanonical POSIX spelling,
symlink components or targets, hard-link aliases, and root escapes. The
manifest and bound JSON/JSONL files MUST use strict UTF-8, duplicate-key and
NaN/Infinity rejection, compact sorted-key `ensure_ascii=false` serialization,
and one terminal LF. Producer row counts and hashes MUST be recomputed from
physical bytes.

#### Scenario: A safe-looking alternate filename is supplied
- **WHEN** any binding path differs from its exact canonical basename even if
  it remains inside the package root and has matching bytes
- **THEN** v4 admission rejects it as `TRAINING_INPUT_INVALID`
- **AND** path flexibility from v3 or a test fixture is not inferred

### Requirement: Commit A authenticates every source-side byte
The production v4 loader SHALL accept only the exact manifest path and SHALL
authenticate source bytes against one full lowercase 40-hex commit-A identity
captured inside the distinct v4 API closure when the later admission code is
implemented. This production trust root MUST NOT come from the manifest, CLI,
config, environment, repository state, or caller. The loader SHALL discover and
validate the containing Git root from the canonical manifest location. An
internal pure validator MAY accept an explicit trusted commit solely for
temporary-repository tests, but it MUST return only plain validated values and
MUST NOT access the production seal, secret, constructor authority, issued
registries, or handoff constructor. The closure-held commit MUST equal manifest
`source_snapshot.commit`, resolve to a commit object, and be an ancestor of the
current committed integration state. Git commands MUST use argument arrays,
`GIT_OPTIONAL_LOCKS=0`, and no shell.

The loader MUST read the Skill Index, `source-draft.jsonl`,
`source-candidates.jsonl`, `review-queue.csv`, and `source-manifest.json`
directly from that Git object using their canonical repository-relative paths.
Those commit-A bytes MUST independently reproduce the source snapshot ID,
Skill Index/draft/source/queue hashes, manifest record hashes, and every
non-human decision field. Current bound source files must equal the authenticated
commit-A bytes. A logical provenance path carried by a row is a value to
validate and MUST NOT be opened as an input path.

The loader SHALL join all 192 authenticated candidate rows to the exact human
decision rows and split members before reading accepted pairs. It MUST require
complete unique identity coverage and exact non-human queue equivalence. Every
accepted row MUST then reproduce the exact v4 fields, constants, role/decision
mapping, stable IDs, canonical Skill Index `skill_text`, source hash,
acceptance hash, and training membership declared by the reviewed-package
spec. Qualification MUST be exact PASS with `can_start_preflight=true`,
`can_start_training=false`, `router_decision="KEEP_BASELINE"`, zero blockers,
and independently matching counts and hashes. No invalid or extra row is
filtered.

#### Scenario: Package and source commit agree on a rewritten hash
- **WHEN** package files are internally consistent but `git show
  <closure-held-commit-A>:<canonical-path>` yields different source bytes
- **THEN** admission fails before sealed objects are created
- **AND** neither current working bytes nor a producer digest replaces commit A

### Requirement: V4 sealed examples and handoff have exact authenticated fields
The additive v4 API SHALL create a distinct closure-held seal, constructor
authority, HMAC-SHA-256 secret, weak issued-example registry, and weak
issued-handoff registry from the v3 API. None may appear in module globals or
returned instances except for the opaque seal reference and stored fingerprint.
The factory SHALL be deleted after binding the production API. V3 and v4 types,
constructors, secrets, registries, trust roots, and verifier entry points MUST
remain distinct.

A sealed v4 example SHALL be a frozen, slotted, `init=False`, `eq=False`,
weak-referenceable exact type and SHALL expose exactly `accepted_record_id`,
`source_record_id`, `skill_id`, `query_text`, `skill_text`, and
`supervision_label`, plus hidden `_validation_seal` and
`_content_fingerprint` slots. `supervision_label` is exactly `POSITIVE` or
`HARD_NEGATIVE`. A sealed v4 handoff SHALL use the same dataclass constraints
and SHALL expose exactly `package_id`,
`source_snapshot_id`, `source_snapshot_commit`,
`training_input_manifest_sha256`, `source_manifest_sha256`,
`source_candidates_sha256`, `review_decisions_sha256`,
`accepted_pairs_sha256`, `qualification_report_sha256`,
`split_manifest_sha256`, and the immutable `examples` tuple, plus hidden
`_validation_seal` and `_content_fingerprint` slots. Example order MUST equal
accepted-file order. Each constructor MUST require the closure-only constructor
authority without storing it and MUST add a successfully created object to its
corresponding issued registry.

Fingerprint JSON uses strict UTF-8,
`json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"),
allow_nan=False)` without LF. The example fingerprint payload contains exactly
`schema_version="router-v2-sealed-example-v4"` plus the six public example
fields. The handoff fingerprint payload contains
`schema_version="router-v2-sealed-handoff-v4"`, exactly its ten public
lineage/identity string fields, `example_count`, and `example_fingerprints`, an
ordered array of the already recomputed per-example HMAC hex strings. Let
`CJ(payload)` be those canonical JSON bytes. HMAC input SHALL be exactly
`b"hermes-skilleval.training-input\0v4\0" + kind + b"\0" +
len(CJ(payload)).to_bytes(8, "big") + CJ(payload)`, where `kind` is exactly
`b"example"` or `b"handoff"`. Comparison uses `hmac.compare_digest`.

The internal verifier MUST be the first downstream operation. It SHALL require
exact v4 type identity, exact closure seal identity, membership in the matching
issued registry, tuple type, strict-UTF-8
valid nonblank strings, allowed supervision, recomputed example fingerprints,
their exact order, and the recomputed handoff fingerprint. Normal construction,
`object.__new__`, low-level field mutation, example replacement/reordering,
lineage mutation, v3 handoffs, copied HMAC text, or unknown fields MUST fail as
`TRAINING_INPUT_INVALID` before grouping or other side effects.

#### Scenario: Skill ID and lineage are unchanged
- **WHEN** a genuine v4 handoff reaches preflight without mutation
- **THEN** exact type, seal, tuple order, every example fingerprint, exact
  `skill_id`, all lineage hashes, and the handoff fingerprint verify
- **AND** the verifier returns no downgraded plain data structure

#### Scenario: One source hash is replaced on the handoff
- **WHEN** low-level mutation changes a lineage SHA while examples remain intact
- **THEN** the handoff fingerprint fails as `TRAINING_INPUT_INVALID`
- **AND** preflight does not reopen package files to repair the instance

### Requirement: Invalid Unicode has one stable rejection
Every v4 string that participates in identity, provenance, review, prompt, skill text, hashing, serialization, handoff, batching, or lineage SHALL be valid Unicode encodable as strict UTF-8. The gate MUST reject lone UTF-16 surrogate code points and any strict-UTF-8 encoding failure with stable code `TRAINING_INPUT_INVALID` before normalization, hashing, handoff construction, framework import, model access, or output creation. It MUST NOT replace, ignore, escape around, or normalize an invalid code point into admissibility.

#### Scenario: Prompt contains a lone high surrogate
- **WHEN** a parsed prompt value contains an unpaired high surrogate
- **THEN** the entire package is rejected as `TRAINING_INPUT_INVALID`
- **AND** no replacement character, hash, partial handoff, framework import, or output is produced

#### Scenario: Reviewer reason contains a lone low surrogate
- **WHEN** a review field contains an unpaired low surrogate
- **THEN** the same stable package-level rejection occurs
- **AND** review metadata is not treated as outside the Unicode boundary

### Requirement: Sealed v4 examples preserve authenticated skill identity
Every sealed v4 training example SHALL contain the exact accepted `skill_id` in addition to query text, skill text, supervision label, and stable record identity. The closure-held validation seal and secret-keyed fingerprint SHALL bind `skill_id` in each example and bind all example fingerprints, package identity, and ordering in the handoff fingerprint. The secret and constructor authority MUST remain outside module globals and instances. The trainer SHALL invoke the internal verifier as its first downstream operation before grouping, batching, framework import, model access, or output work.

#### Scenario: Genuine v4 handoff is unchanged
- **WHEN** an unchanged handoff returned by the v4 loader reaches preflight
- **THEN** its type, seals, tuple immutability, per-example fingerprints, handoff fingerprint, order, and exact skill IDs verify

#### Scenario: Skill ID is mutated after loading
- **WHEN** low-level mutation changes the `skill_id` of a genuine sealed example or replaces it with another example
- **THEN** fingerprint verification rejects the handoff as `TRAINING_INPUT_INVALID`
- **AND** no batch plan or framework side effect occurs

#### Scenario: Caller constructs a lookalike handoff
- **WHEN** a caller uses normal construction, `object.__new__`, copied fields, forged dataclasses, or an older v3 handoff
- **THEN** exact type, seal, and fingerprint checks reject it
- **AND** structural similarity does not authorize training

### Requirement: V4 rows preserve decision semantics without inference
The v4 gate SHALL admit training rows only when their source role, human decision, supervision label, training split, accepted flag, source identity, review evidence, and canonical hashes form an allowed exact relation. `POSITIVE` permits only `ACCEPT_POSITIVE`, `AMBIGUOUS_MULTI_SKILL`, `SOURCE_LABEL_DEFECT`, or `REJECT_DRAFT`; `HARD_NEGATIVE_CANDIDATE` permits only `TRUE_HARD_NEGATIVE`, `SECONDARY_POSITIVE`, `AMBIGUOUS_MULTI_SKILL`, `EASY_NEGATIVE`, `SOURCE_LABEL_DEFECT`, or `REJECT_DRAFT`; and `NO_SKILL_CANDIDATE` permits only `NO_SKILL_CONFIRMED`, `AMBIGUOUS_MULTI_SKILL`, `SOURCE_LABEL_DEFECT`, or `REJECT_DRAFT`. Every other role-decision pairing MUST fail.

`ACCEPT_POSITIVE` SHALL map to `POSITIVE`; `TRUE_HARD_NEGATIVE` SHALL map to `HARD_NEGATIVE`; and `SECONDARY_POSITIVE` SHALL map to `POSITIVE` for the row's candidate `skill_id`, count toward the minimum 64 accepted train positives and 16/16 positive coverage, and not count as a true hard negative. Evaluation positives, no-skill rows, `EASY_NEGATIVE`, `AMBIGUOUS_MULTI_SKILL`, `SOURCE_LABEL_DEFECT`, `REJECT_DRAFT`, blanks, and every unknown decision MUST remain outside training input. The gate MUST NOT filter, repair, relabel, infer, upgrade, or partially consume invalid rows.

#### Scenario: Reviewed hard negative is valid
- **WHEN** a bound train hard-negative candidate has decision `TRUE_HARD_NEGATIVE`, non-empty human evidence, and every v4 hash relation
- **THEN** it is admitted exactly once with supervision `HARD_NEGATIVE`

#### Scenario: Easy negative is included in accepted pairs
- **WHEN** a row with decision `EASY_NEGATIVE` appears in the training accepted-pair file
- **THEN** the entire package is rejected as `TRAINING_INPUT_INVALID`
- **AND** the row is not silently filtered

#### Scenario: Decision is valid for another source role
- **WHEN** a syntactically allowed decision is paired with a source role outside the exhaustive table
- **THEN** the complete package is rejected as `TRAINING_INPUT_INVALID`
- **AND** the decision is not reinterpreted from prompt text or candidate metadata

### Requirement: V4 handoff supports skill-unique planning and nothing else
After verification, preflight MAY read sealed `skill_id` only to construct and validate the deterministic skill-unique positive batch plan and lineage. Model task-side input SHALL remain exactly `router_query_text(query_text)`, and model candidate-side input MAY use only `skill_text`. Source role, family, split, reviewer, reason, paths, hashes, and other provenance MUST NOT become model input, score, weight, target, or tie-break data.

#### Scenario: Positive batch plan is requested
- **WHEN** the verified v4 handoff contains multiple positives for one skill
- **THEN** preflight uses authenticated skill identity to keep those examples in different MNRL batches
- **AND** it does not concatenate skill ID or provenance into query text

### Requirement: Existing v3 behavior and historical artifacts remain intact
The v4 admission path SHALL be additive. Existing v3 gate tests, synthetic v3 success fixtures, v3 diagnostic exporter rejection, prompt-only query behavior, closure/HMAC misuse guard, and generated v3 lineage identities MUST remain unchanged. The change MUST NOT mutate committed Phase 14-18 or blind artifacts, create a real checkpoint, or reinterpret a v3 package as v4.

#### Scenario: V3 package is passed to the v4 gate
- **WHEN** a valid or invalid v3 manifest is supplied where v4 is required
- **THEN** the gate rejects the version mismatch without upgrading it
- **AND** the dedicated existing v3 behavior remains available to its current callers

#### Scenario: Protected artifact identities are checked after apply
- **WHEN** the v4 source and preflight code is validated
- **THEN** Phase 14-18 and blind tree identities match the baseline
- **AND** no v4 file is written into a protected historical path
