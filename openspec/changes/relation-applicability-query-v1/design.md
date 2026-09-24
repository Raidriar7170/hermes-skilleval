## Context
Active Goal fixes the design; this document maps it to implementation, without a second research plan. Base is PR #54 at 342c7fe.

## Goals / Non-Goals
Implement the algorithm-query-source-audit chain. No new repair execution, training, default promotion, merge or release.

## Decisions
Reuse ExactSelector, RelationStore, CompleteEncoder and original objective. Add content scores independently of bound storage. Use complete public text and resolved paths/symbols, with typed literal cues. The separate study CLI exposes only the seven relation-study actions.

Use fixed seed 20260923, at most 48 stratified pairs per state, 256 online review pairs, two online repeats per method/state. Q and J are separate fresh contexts. Replay policy receives only public data and revealed Q records. J is read only after trajectories lock. All unknowns remain in denominators.

Measure cold and reused processes with fresh empty threads, batches 2/8 and two interleaved sequences per configuration. Conservative measured envelopes and 1.25 margin plus five-second cleanup reserve gate starts. Each independent online run pays setup. Freeze after development audits, before macro/cache Q/J and online acquisition.

## Scope boundaries
Read scope: current code/protocol/configs, prior public checkpoints/ledgers/candidate pools/index and base source; metadata for locating them. No reference patch, hidden acceptance or later agent trajectories as research input.
Write scope: new pair/planner/study modules, scoped tests, new configs/artifacts/research/goals and this OpenSpec change. Private relation calls in a new sibling study directory.
Frozen assets: four original states, candidate texts/domain/weights, MiniLM revision, prior results; freeze new panel identities before labels and algorithm/prompt/cost before checks.
Final repository scope: complete tracked delta against 342c7fe, plus declared new study evidence; legacy tracked assets unchanged.

## Risks / Trade-offs
Same-model audit correlated errors → label MODEL_ASSISTED_SOURCE_AUDIT_NOT_HUMAN_GOLD, human_reviewer_count=0. R-derived stratum favors R → report strata separately. Twelve runs and two timing repeats → raw observations, no reliable p95 or generalization claim. Availability failure → preserve partial outcome without substituting model or repair results.
