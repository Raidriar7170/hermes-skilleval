## Context

Commit `751bb678bf9fb63a357ff3667e3508a0f5ed83a2` freezes snapshot `router-v2-v4-source-38afe7d5b2500d4a` as 192 ordered candidate rows. The active `make-router-v2-training-ready` contract intentionally admits only human-supplied `review-decisions.csv`; its task 5.3 and tasks 6-10 are still blocked. This sibling change must make model review auditable without impersonating or replacing that human gate.

The pilot has one contract implementation phase and a later execution phase. Contract implementation defines and tests the format but creates no row opinions. Execution runs two isolated Codex passes over all rows, followed by model adjudication, then validates the resulting files.

## Goals / Non-Goals

**Goals:**

- Bind every pilot artifact and opinion to the frozen snapshot, commit, ordered source identity, exact source-row hash, rubric, prompt metadata, and model metadata.
- Require two complete, isolated model passes and adjudication that cryptographically binds both pass rows.
- Carry the exact `MODEL_ONLY_PILOT` truth fields and fail-closed status on every JSON object.
- Produce deterministic canonical JSONL and deterministic content hashes suitable for independent validation.
- Reject language or structure that could be consumed as human review, qualification, admission, preflight, training, release, or promotion evidence.

**Non-Goals:**

- Human review, human acceptance, independent human review, or owner review.
- Creating or modifying `data/router-v2-v4/review-decisions.csv`.
- Qualification, accepted-pair generation, training-input generation, preflight, training, GPU work, blind-v2 conclusions, release, or router promotion.
- Changing the current Router decision from `KEEP_BASELINE` or completing any blocked task in `make-router-v2-training-ready`.

## Decisions

### Separate, non-admissible artifact tree

Each run uses `artifacts/router-v2-v4/model-only-pilot/<pilot-id>/` with `pilot-manifest.json`, `pass-1.model-opinions.jsonl`, `pass-2.model-opinions.jsonl`, `adjudication.model-opinions.jsonl`, and `summary.json`. The validator refuses paths outside this tree and rejects a repository containing `data/router-v2-v4/review-decisions.csv` during validation.

This is preferred over extending the human review schema because a sibling namespace prevents accidental interpretation as human-owned evidence. A Markdown-only report was rejected because it cannot establish complete row coverage or cryptographic bindings.

### Exact immutable source binding

The contract pins commit `751bb678bf9fb63a357ff3667e3508a0f5ed83a2`, snapshot `router-v2-v4-source-38afe7d5b2500d4a`, source candidate SHA-256 `5fa7e7feb1a5fedc2cf8bcc8adf17afe3356f9d4614b2848b0d74f88718e3d2a`, source manifest SHA-256 `330f13d58833450293374f91e253dadf452b5a7d5233a4aa025984e09b0ed511`, and exactly 192 manifest record identities in manifest order. Every pass row repeats `source_record_id` and `source_record_exact_bytes_sha256` from that ordered source manifest.

### Opinion-only vocabulary

Opinions are role-specific and cannot be mistaken for accepted training labels:

- `POSITIVE`: `POSITIVE_ROLE_SUPPORTED`, `POSITIVE_ROLE_DISPUTED`, or `MODEL_UNCERTAIN`.
- `HARD_NEGATIVE_CANDIDATE`: `HARD_NEGATIVE_ROLE_SUPPORTED`, `HARD_NEGATIVE_ROLE_DISPUTED`, or `MODEL_UNCERTAIN`.
- `NO_SKILL_CANDIDATE`: `NO_SKILL_ROLE_SUPPORTED`, `NO_SKILL_ROLE_DISPUTED`, or `MODEL_UNCERTAIN`.

No `reviewer`, `decision`, `accepted`, `qualification`, or `admission` field is permitted. Adjudication uses the same role-compatible opinion vocabulary and records agreement state and a bounded rationale.

### Truth block on every JSON object

Every manifest, pass row, adjudication row, and summary object carries the exact fields `review_mode=MODEL_ONLY_PILOT`, `human_reviewer_count=0`, `model_review_pass_count=2`, `model_adjudication_enabled=true`, `independent_human_review=false`, `model_correlation_risk=true`, `release_eligible=false`, and `router_decision=KEEP_BASELINE`. It also carries `human_review_status=REVIEW_REQUIRED`, `admission_effect=NONE`, `can_start_preflight=false`, and `can_start_training=false`.

### Isolated pass identities and explicit unknowns

Pass files have fixed identities `MODEL_PASS_1` and `MODEL_PASS_2`; each row records its pass identity and an isolation statement that the other pass output was not provided. The two passes must have different run IDs and must not claim statistical or human independence. Model and prompt provenance fields accept only a non-empty explicit value or the exact marker `UNAVAILABLE`; they are never inferred by the validator.

### Canonical bytes and chained row hashes

Each JSONL object is UTF-8, one LF-terminated line, sorted keys, compact separators, and no duplicate JSON keys. Each row contains `row_sha256`, computed from the same object with `row_sha256` omitted. Adjudication rows bind both corresponding pass `row_sha256` values. JSON documents use the same canonical encoding with one final LF; declared file hashes exclude the self-referential document that declares them.

## Risks / Trade-offs

- **Correlated model errors can agree across passes** → Every object states `model_correlation_risk=true`; agreement is reported as model agreement only and has no admission effect.
- **Future code could misread opinions as labels** → Use a separate path and vocabulary, reject forbidden acceptance fields, and keep all gate fields fail-closed.
- **Unavailable runtime metadata reduces provenance detail** → Record `UNAVAILABLE` explicitly and never fabricate an identifier.
- **Canonical serialization is stricter than normal JSON parsing** → Publish a validator and rubric before running passes; reject and regenerate malformed artifacts rather than normalizing them silently.
- **Repository HEAD can move after the frozen commit** → Bind artifacts to the source commit and exact source hashes rather than requiring the working tree HEAD to remain equal to commit A.

## Migration Plan

1. Land the contract, tests, rubric, and proposal-boundary Human Brief without creating review artifacts.
2. Run two isolated model passes over all 192 rows, preserving their separate run identities.
3. Run model adjudication over all 192 pass-row pairs.
4. Generate summary metadata and validate the complete pilot directory.
5. Keep human review and all downstream gates blocked. Rollback removes only the sibling change and pilot artifact tree; frozen source data remains untouched.

## Open Questions

None. Any future request to let model opinions affect internal training requires a separate approved OpenSpec change and cannot be inferred from this pilot.
