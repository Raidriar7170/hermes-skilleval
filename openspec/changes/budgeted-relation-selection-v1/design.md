## Context

Active design authority is the complete Goal in docs/goals/Hermes_Budgeted_Anytime_Relation_Selection_Codex_Goal.md. Baseline is PR53 d1ed9ce, open/draft, verified at start. Its strict relation APIs and historical studies stay intact.

## Goals / Non-Goals

Implement the Goal sections 4–24 without redesign: final content-admission index, immediate MMR, sparse resumable relations, exact small-set bounds, finite P/C comparison. No training, promotion, merge, expanded task sampling or rewritten legacy evidence.

## Decisions

- New opt-in modules reuse legacy source/role validation semantics and Session. Persist full input identity and first accepted rows atomically; retry only transport/format failures.
- Enumerate <=4 of <=24 candidates with serialized token feasibility. A and D share the solver. Unknown bounds are [0,1]; fixed accepted labels are not semantic truth.
- Persist method-stage starts before work and elapsed in finally; resume does not reset budgets. Keep sparse stopping distinct from failure.
- Save M before A calls; keep N/M independent. P charges actual reusable component costs per method/repeat; C grants equal tails and discloses preparation separately.
- Freeze execution version before two new prefixes and 24 maximum tails. Preserve every attempt and reconstruct original candidates for trusted verification.

## Risks / Trade-offs

Model labels may be wrong → retain provenance checks and independent bounded review, separate functional verification. Tiny observed task set → raw counts only. Slow helper/setup/enumeration → measured deadlines and current-pack fallback. Missing resources → preserve smaller scope without substitute model or tasks.

## Verification scope

Read scope: intervention sources/tests, relevant scripts/configs/docs/OpenSpec and authorized local task/index/encoder/overlay assets. Write scope: new budgeted modules/tests/scripts/configs/artifacts/docs/OpenSpec; narrow Session integration if necessary. Frozen assets: exact task bases, public inputs, trusted overlays, encoder/index, model/runtime and algorithm identities at freeze. Final repository scope: full tracked delta from d1ed9ce; legacy studies and unrelated tracked content unchanged. Private runtime output uses sibling hermes-budgeted-relation-private and is not committed.
