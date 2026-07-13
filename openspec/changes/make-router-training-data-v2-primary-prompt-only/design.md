## Context

The committed Router Training Data V2 qualification pack is deliberately blocked and diagnostic-only, but its v1 candidate builder uses `_task_text(task)` to concatenate task ID, category, difficulty, prompt, and robustness tags into `query_text`. Production routing receives the user's prompt rather than benchmark metadata, so the current representation can leak evaluation-only structure into a future trainer even though no pair is accepted today.

This change is a contract correction, not a qualification or modeling phase. It is stacked on local archive truth-fix commit `4f995c2595a6314ae86111a54409af9f7243b51a`, which has not been integrated into `main`. The existing archive, the canonical 12-task × 16-skill matrix, all eight blockers, the Phase 16 `KEEP_BASELINE` decision, blind preflight, and Phase 14–18 evidence identities remain constraints.

## Goals / Non-Goals

**Goals:**

- Make every primary candidate `query_text` equal the loader-normalized `task.prompt` byte-for-byte.
- Bind that equality with `prompt_text_sha256`, an explicit row policy, and an identical machine-readable query contract in the report and manifest.
- Advance candidate, report, manifest, and qualification policy identifiers to v2 so consumers cannot mistake the corrected representation for v1.
- Regenerate the same committed pack deterministically while preserving every qualification count, blocker, disposition, and readiness decision.
- Keep current documentation authoritative and clearly label the earlier v1 Human Brief as historical after apply.

**Non-Goals:**

- Manually reviewing the 32 same-category candidates, accepting training pairs, filling five missing positive skills, adding reject/no-skill examples, or defining task families or an independent calibration split.
- Generating `training-pairs-v2.jsonl` or any trainer-ready file.
- Changing training code, `embedding_training`, runtime routers, MiniLM/cross-encoder models, thresholds, or router promotion logic.
- Reading or mining Phase 16 blind prompts, calibrating/selecting on blind data, rerunning blind evaluation, or changing Phase 14–18 evidence.
- Claiming performance improvement, running A100/GPU work, creating a checkpoint, or creating a tag/release/deploy.
- Committing, pushing, opening a PR, merging, or archiving automatically during apply.

## Decisions

### 1. The only primary query is the loaded prompt

Candidate construction will assign `query_text = task.prompt` directly after `load_tasks()` has performed its existing UTF-8 read and surrounding-whitespace normalization. The row will also set `query_text_policy="prompt_only"`, and `prompt_text_sha256` will be computed from the exact UTF-8 bytes of that same string.

Task ID, category, difficulty, and robustness tags remain available as structured inputs for validation, classification, split, and provenance. They must not be concatenated, serialized, or otherwise encoded into the primary query. Candidate rows will use an exact field contract and will not emit `composite_query_text`, `alternate_query_text`, a legacy query, or any other second query representation.

This direct assignment is preferred over modifying the generic `_task_text()` formatter because a formatter preserves ambiguity about which metadata is allowed. A configurable query policy is also rejected: the qualification pack has one primary production-aligned contract, not two selectable representations.

### 2. V2 schemas make the representation change explicit

Apply will use these identifiers:

- candidate row: `router-training-data-v2-candidate-v2`;
- qualification policy: `router-training-data-v2-qualification-v2`;
- report: `router-training-data-v2-qualification-report-v2`;
- manifest: `router-training-data-v2-manifest-v2`, with `artifact_version=2`.

Every candidate row adds only `query_text_policy="prompt_only"` to the existing row field set. Both the report and manifest will expose the same `query_contract` object:

```json
{
  "alternate_query_fields": [],
  "forbidden_primary_query_inputs": [
    "task_id",
    "category",
    "difficulty",
    "robustness_tags"
  ],
  "hash_algorithm": "sha256",
  "hash_field": "prompt_text_sha256",
  "normalization": "loader_normalized",
  "primary_query_field": "query_text",
  "query_text_policy": "prompt_only",
  "source_field": "task.prompt"
}
```

The identical object makes the policy inspectable without reading prose, while the exact row field-set test prevents a hidden legacy/composite query from coexisting. Emitting both v1 and v2 or retaining a compatibility query is rejected because downstream code could continue selecting the leaking field.

### 3. Metadata invariance is tested independently of natural prompt text

Tests will construct tasks whose prompt is unchanged while task ID, category, difficulty, and robustness tags vary within valid fixtures. Their generated `query_text` and `prompt_text_sha256` must remain identical. Separate tests will assert byte equality to the loader-normalized prompt, recompute SHA-256 from `query_text`, assert the exact v2 field set, and reject any second field whose semantics are a primary or composite query.

The metadata-invariance test does not forbid words that naturally occur inside a user's prompt. It proves source-field independence by changing structured metadata while holding the prompt constant, rather than by searching prompt text for category words.

### 4. Qualification semantics remain frozen and fail closed

Only the query representation and its versioned contract change. Candidate labels, types, dispositions, source splits, acceptance flags, counts, the eight sorted blocker codes, `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false` remain exactly as in the archived qualification change. Neither `training-pairs.jsonl` nor `training-pairs-v2.jsonl` is emitted.

Category remains a valid structured input to `_gold_category()` and to same-category versus cross-category classification. This does not make category part of the query.

### 5. Regeneration uses a fresh target and replaces only the bound pack

The apply phase first adds RED contract tests, then implements the minimal builder change. It regenerates into a fresh absent target, verifies exact v2 schemas, counts, query equality, output hashes, and a second-run byte comparison, and only then updates the three committed machine artifacts at `docs/demo/router-training-data-v2-qualification-pack/`.

All three committed hashes must differ from their v1 values: candidate bytes change through the prompt-only row contract, report bytes change through its v2 policy/schema/query contract, and manifest bytes change through its own v2 contract plus the bound candidate/report hashes. The pack README will carry the newly computed hashes rather than predetermined values.

Pointing the builder at the existing committed pack is rejected because its fresh-target guard is a safety property. Writing a second canonical pack path is also rejected because it would create competing current truth surfaces.

### 6. Documentation separates current v2 truth from historical v1 evidence

The proposal-status brief is `docs/human-briefs/2026-07-11-make-router-training-data-v2-primary-prompt-only.html` and remains visibly `PROPOSED` / `APPLY_NOT_STARTED`. Apply creates a distinct current brief at `docs/human-briefs/2026-07-11-make-router-training-data-v2-primary-prompt-only-apply.html` from fresh source, artifact, and validation evidence.

The pack README will point to the active v2 OpenSpec artifacts and current machine outputs. The earlier `2026-07-11-build-router-training-data-v2-qualification-pack.html` remains useful v1 evidence, but apply must visibly label it `HISTORICAL_V1_SNAPSHOT` and state that its old hashes/query contract are not the current pack contract. Human briefs are navigation/review aids and never replace OpenSpec, tests, or JSON/JSONL evidence.

### 7. Protected evidence is guarded at both test and Git boundaries

Existing blind-source preflight tests remain in force. Apply adds or retains guards showing that `benchmarks/blind-migration-tasks/**` is not read or changed and that Phase 14, 15, 16, 17, and 18 paths have the same Git blob identities as the apply baseline. Validation also checks that the diff is limited to the approved source, tests, current pack, README, Human Brief, and OpenSpec surfaces.

## Risks / Trade-offs

- **[Breaking schema identifiers can reject old consumers]** → Use explicit v2 identifiers, document the migration, and emit no ambiguous dual-schema representation.
- **[Future loader normalization could drift from the hash contract]** → Derive `query_text` and `prompt_text_sha256` from the same loaded string and test byte equality plus recomputed hashes.
- **[Metadata can leak through a second field]** → Enforce the exact candidate field set and `alternate_query_fields=[]` in the machine contract.
- **[Regeneration could accidentally change qualification semantics]** → Lock all canonical counts, dispositions, blocker codes, readiness values, and absence of trainer-ready files before replacing artifacts.
- **[The v1 brief can look current after in-place pack replacement]** → Add a visible historical marker and link readers to the v2 apply brief and current machine artifacts.
- **[A broad implementation could touch training or blind evidence]** → Keep the implementation surface surgical and enforce protected-path/blob and changed-path guards before review.

## Migration Plan

1. Add focused RED tests for prompt equality, prompt-hash equality, metadata invariance, exact v2 schemas/query contract, absence of alternate queries, canonical invariants, and fail-closed readiness.
2. Change only the qualification builder's primary query and v2 constants/contract surfaces; reach GREEN without refactoring training/runtime code.
3. Regenerate twice into fresh absent targets, require byte identity, verify all three hashes change from v1, then replace only the three committed machine artifacts.
4. Update README/current truth tests, create the apply Human Brief, and mark the previous v1 brief historical.
5. Run focused and full tests, Ruff, strict OpenSpec validation, release reproducibility, link checks, hash guards, protected-evidence guards, and a read-only diff review. Stop for user review without commit or publication.

Rollback is a clean revert of this apply diff to the v1 pack and builder. There is no database, external service, deployed model, or checkpoint migration.

## Open Questions

None. The primary prompt-only policy, v2 identifiers, query-contract shape, preserved canonical counts, and no-training boundary are fixed for this change.
