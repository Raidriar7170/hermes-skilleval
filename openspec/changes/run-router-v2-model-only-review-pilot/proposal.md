## Why

The frozen Router V2 v4 source snapshot needs a strict, reproducible Codex model audit without converting model opinions into human review evidence or weakening the existing human-only admission gate. A separate pilot contract is required so two model passes and model adjudication can be inspected internally while every release, promotion, preflight, and training decision remains fail-closed.

## What Changes

- Add an isolated `MODEL_ONLY_PILOT` artifact contract for two full model-opinion passes and one model adjudication over the exact 192-row frozen snapshot.
- Add deterministic validation for snapshot and commit binding, row identity and ordering, role-compatible opinions, pass isolation, canonical JSON, row hashes, adjudication bindings, and exact truth markers.
- Add a stable review rubric and a proposal-boundary Chinese Human Brief that explicitly state this is not human review and has no admission effect.
- Keep `review-decisions.csv`, qualification, training-input, preflight, model training, release, and router promotion outside this change. The existing `make-router-v2-training-ready` task 5.3 and tasks 6-10 remain blocked and unchanged.
- Do not fabricate model opinions or completed pilot artifacts during contract implementation; those artifacts are created only by later isolated review and adjudication tasks.

## Capabilities

### New Capabilities

- `router-v2-model-only-review-pilot`: Defines the non-admissible model-only review artifact and validation contract for the frozen Router V2 v4 snapshot.

### Modified Capabilities

None.

## Impact

- Adds a focused Python validator module, a thin validation CLI, tests, a stable rubric, and an L2 Human Brief.
- Adds future artifact paths under `artifacts/router-v2-v4/model-only-pilot/<pilot-id>/` without changing the frozen files under `data/router-v2-v4/`.
- Does not modify dependencies, public APIs, human review semantics, qualification inputs, training inputs, release state, or Router V2 baseline selection.
