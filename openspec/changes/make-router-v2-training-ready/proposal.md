## Why

Router V2 now has a fail-closed v3 admission contract but no reviewed, family-disjoint training package, no safe same-skill batching, and no side-effect-free way to prove that a real run is ready. This change supplies only the minimum reviewed-data and runtime prerequisites needed to reach `TRAINING_READY_PRECHECK=PASS` while preserving `KEEP_BASELINE` and stopping before GPU training.

## What Changes

- Add one additive `data/router-v2-v4/` source snapshot containing 64 train positives, 16 calibration positives, 16 non-blind-test positives, 64 same-category hard-negative candidates, and 32 calibration/test no-skill candidates across all 16 canonical skills.
- Freeze source candidates before review, emit a human-editable review queue, and fail closed until explicit human decisions with non-empty reviewer and reason fields are imported. No decision, reviewer, or acceptance may be inferred or model-generated.
- Add a v4 reviewed-data package whose accepted training rows remain bound to the immutable source snapshot and whose calibration, non-blind-test, and no-skill rows are excluded from embedding training.
- Extend the training-input contract to reject invalid Unicode deterministically, carry `skill_id` through the sealed handoff, and bind the v4 source, split, qualification, accepted-pair, and manifest hashes.
- Add deterministic skill-unique positive batching, complete training lineage, and a `--preflight-only` path that validates and plans batches without importing model frameworks, accessing a GPU, creating output directories, loading a model, or writing checkpoints.
- Preserve the historical v3 artifacts, Phase 14-18 trees, blind trees, and release decision byte-for-byte. Do not run blind-v2, full training, threshold selection, tag, release, or deployment.
- Stop after the source-snapshot commit if human review decisions are absent or incomplete. The final change may report `TRAINING_READY_PRECHECK=PASS` only after every v4 gate passes; it still must not start training or claim model improvement.

## Capabilities

### New Capabilities

- `router-v2-reviewed-data-source`: Defines the immutable v4 candidate snapshot, family-disjoint splits, human review queue and decision import, accepted-pair package, and review/provenance gates.
- `router-v2-training-preflight`: Defines skill-unique deterministic batching, full training lineage, and the framework/GPU/output-free `TRAINING_READY_PRECHECK` contract.

### Modified Capabilities

- `router-training-data-v2-qualification-pack`: Adds the reviewed v4 qualification report without changing the canonical v3 artifacts or `KEEP_BASELINE` decision.
- `router-training-input-gate`: Adds v4 package admission, stable Unicode rejection, sealed `skill_id`, and source/split lineage while retaining fail-closed v3 behavior.

## Impact

- Additive reviewed-data files under `data/router-v2-v4/` and one narrow source/review/package builder.
- Focused changes to `src/hermes_skilleval/training_input.py`, embedding-training lineage, and `scripts/train_embedding_router.py` after human review is supplied.
- Focused source-snapshot, admission, sampler, lineage, Unicode, and preflight tests only.
- No Human Brief, dashboard, release evidence, phase numbering, unrelated test expansion, GPU/A100 execution, checkpoint, blind-v2 access, or performance claim.

## Dependency and Lifecycle Order

- This change depends on the completed but still active
  `harden-router-v2-pretraining-contracts` change, which currently owns the
  unsynced base deltas for `router-training-input-gate` and
  `router-training-data-v2-qualification-pack`.
- Source commit A does not sync or archive either change. Applying this
  change's additive source slice is safe because the merged runtime code is
  already at the recorded baseline, but the lower change remains the
  authoritative OpenSpec base until it is separately synced and archived.
- Before this change is ever synced or archived, recover the lower change,
  review it first, and sync/archive it under separate authorization. Then
  revalidate this change against the resulting main specs. Never archive this
  upper change first or let its deltas silently replace the lower layer.
