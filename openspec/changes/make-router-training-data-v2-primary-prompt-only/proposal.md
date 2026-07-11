## Why

The current Router Training Data V2 candidate rows build `query_text` from task ID, category, difficulty, prompt, and robustness tags, even though production routing sees only the user prompt. Those benchmark-only fields create a training-leakage risk, so the primary qualification contract must become prompt-only before any pair can be reviewed or any future training can be authorized.

## What Changes

- Make the primary candidate query exactly the loader-normalized `task.prompt`, byte-for-byte, and require `sha256(query_text) == prompt_text_sha256` for every row.
- Add `query_text_policy="prompt_only"` and a machine-readable query contract to the candidate matrix, qualification report, and provenance manifest.
- **BREAKING**: advance the candidate, qualification-report, manifest, and qualification-policy identifiers from v1 to v2 and deterministically regenerate all three machine artifacts at the existing qualification-pack path.
- Forbid task ID, category, difficulty, and robustness tags from being concatenated or serialized into the primary query; retain them only as structured validation, classification, split, or provenance inputs. Category may still classify same-category versus cross-category candidates.
- Forbid a second composite or alternate query field in candidate rows, so consumers cannot silently select the metadata-enriched representation.
- Preserve the canonical qualification snapshot exactly: 12 tasks × 16 skills = 192 candidates, 16 positives, 32 unreviewed same-category negative candidates, 144 cross-category easy negatives, 64 reserved source-test rows, 32 train-policy candidates, 0 accepted pairs, 11/16 train-positive skill coverage, 0 reviewed reject/no-skill examples, the existing eight blocker codes, `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`.
- Update the current pack README, truth-surface tests, and a new apply Human Brief for the v2 contract. Mark the existing 2026-07-11 qualification brief as historical wherever its v1 hashes or evidence could otherwise appear current.
- Preserve blind preflight behavior and the blob identities of Phase 14–18 protected evidence.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `router-training-data-v2-qualification-pack`: Replace the metadata-enriched primary query with an explicit prompt-only v2 candidate contract and advance the report/manifest policy surfaces while preserving all qualification counts, blockers, readiness, provenance, and protected-evidence boundaries.

## Impact

- Implementation surface: `src/hermes_skilleval/router_training_data_v2.py` only; this change does not refactor `embedding_training`, runtime routers, or training code.
- Artifact surface: regenerate `docs/demo/router-training-data-v2-qualification-pack/{candidate-pairs.jsonl,qualification-report.json,manifest.json}` at the same path, with all three hashes expected to change because their schemas, policy/query contracts, or bound output hashes change.
- Documentation and tests: update the pack README and current truth tests, create a proposal/apply Human Brief as appropriate, and make the earlier 2026-07-11 qualification brief explicitly historical where it reports v1 hashes/evidence.
- Compatibility: consumers that require v1 candidate/report/manifest schema or policy identifiers must explicitly migrate to v2; no dual-schema output or compatibility query is emitted.
- Lifecycle: this proposal branch is stacked on local archive truth-fix commit `4f995c2595a6314ae86111a54409af9f7243b51a`, which is not yet integrated into `main`. Apply must stop for user review and must not commit, push, create a PR, merge, archive, release, or deploy automatically.
- Explicitly out of scope: manual review of the 32 same-category candidates; accepted pairs; missing positive coverage; reject/no-skill data; task-family or calibration split work; `training-pairs-v2.jsonl`; training/`embedding_training`/runtime-router refactors; MiniLM or cross-encoder training; threshold tuning; Phase 16 blind mining, calibration, or evaluation; Phase 14–18 mutation; performance claims; A100/GPU jobs; checkpoints; tags or releases.
