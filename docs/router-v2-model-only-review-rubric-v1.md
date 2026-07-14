# Router V2 v4 Model-Only Review Rubric v1

## Scope and fixed status

This rubric governs two Codex model-opinion passes and model adjudication over frozen snapshot `router-v2-v4-source-38afe7d5b2500d4a`, bound to source commit `751bb678bf9fb63a357ff3667e3508a0f5ed83a2`.

This is `MODEL_ONLY_PILOT` diagnostic evidence. It is not human review, does not create `review-decisions.csv`, and has no qualification, admission, preflight, training, release, or router-promotion effect. The Router decision remains `KEEP_BASELINE`.

## Required truth block

Every manifest, pass row, adjudication row, and summary object must contain:

```json
{
  "review_mode": "MODEL_ONLY_PILOT",
  "human_reviewer_count": 0,
  "model_review_pass_count": 2,
  "model_adjudication_enabled": true,
  "independent_human_review": false,
  "model_correlation_risk": true,
  "release_eligible": false,
  "router_decision": "KEEP_BASELINE",
  "human_review_status": "REVIEW_REQUIRED",
  "admission_effect": "NONE",
  "can_start_preflight": false,
  "can_start_training": false
}
```

## Evidence available to a pass

For each frozen row, a pass may use only:

- `source_record_id`, exact-row SHA-256, split, and source role;
- query text;
- positive skill identity and description when present;
- candidate skill identity, category, and description when present;
- this rubric and the pass prompt.

`MODEL_PASS_1` must not receive pass 2 output. `MODEL_PASS_2` must not receive pass 1 output. A pass must not consult the adjudication output, a human decision file, training results, benchmark outcomes, or release state. Each pass covers all 192 rows in frozen manifest order.

## Opinion rules

### `POSITIVE`

Use `POSITIVE_ROLE_SUPPORTED` when the query's primary requested work clearly matches the named positive skill. Use `POSITIVE_ROLE_DISPUTED` when the named skill is materially wrong, overly broad, or only incidental. Use `MODEL_UNCERTAIN` when the available descriptions do not support a reliable distinction.

### `HARD_NEGATIVE_CANDIDATE`

Use `HARD_NEGATIVE_ROLE_SUPPORTED` when the candidate is plausibly confusable but should not be routed for the query's primary requested work. Use `HARD_NEGATIVE_ROLE_DISPUTED` when the candidate is actually a valid primary route or is not meaningfully confusable. Use `MODEL_UNCERTAIN` when the boundary cannot be established from the available evidence.

### `NO_SKILL_CANDIDATE`

Use `NO_SKILL_ROLE_SUPPORTED` when none of the canonical skills is a defensible primary route. Use `NO_SKILL_ROLE_DISPUTED` when one or more canonical skills clearly cover the request. Use `MODEL_UNCERTAIN` when coverage is ambiguous.

## Rationale requirements

Each rationale must be a concise, row-specific explanation grounded in the query and skill descriptions. It must explain the primary-routing boundary, not merely restate the source role or opinion. If evidence is insufficient, select `MODEL_UNCERTAIN` and name the missing distinction.

Do not use or imply human-review, acceptance, qualification, admission, production-readiness, release, promotion, or training-label language. Do not add a `reviewer`, `decision`, `accepted`, qualification, admission-decision, or training-label field.

## Adjudication

Adjudication receives both pass rows and their hashes for the same frozen source row. It records whether the opinions agree and emits one role-compatible adjudicated model opinion with a concise rationale. Agreement does not prove correctness or independence; both passes remain correlated model evidence.

For disagreement, adjudication must compare the two rationales against the same row evidence and rubric. If the evidence does not resolve the conflict, it must select `MODEL_UNCERTAIN` rather than force support or dispute.

## Provenance and canonicalization

Record model and prompt provenance exactly when available. If an identifier cannot be obtained, record the literal string `UNAVAILABLE`; never infer it. Serialize every row as UTF-8 canonical JSON with sorted keys, compact separators, one final LF, and a `row_sha256` computed from the canonical object with `row_sha256` omitted.

Only the validator may declare the pilot structurally valid. Even a valid pilot has `admission_effect=NONE`, `release_eligible=false`, `can_start_preflight=false`, and `can_start_training=false`.
