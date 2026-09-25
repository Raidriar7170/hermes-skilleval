## Context

The user-designated Goal in docs/goals is the complete execution contract. Inherited baseline is b6d9316d6edd84d1a70543f290aaf3f00f7f5b90 (open Draft PR #55). This document only maps that contract to existing code.

## Goals / Non-Goals

Implement its A–F sequence. Preserve historical records and defaults; no training, new algorithm, hidden-answer inputs, resampling or release.

## Decisions

Reuse relation_query_study R requests, CostEnvelope, RelationStore and ExactSelector through a public-input-only adapter. Reuse session checkpoints, run_once and repair_checks. Separate independent repeated acquisition records from shared measured candidate preparation. One plan fixes N/M/R, two repeats, 600 seconds and seed 20260924. Qualification emits only eligibility to task selection; acceptance labels remain sealed until all attempts end. Replay reads saved records only.

Read scope: repository implementation/protocols and discovered existing legal local task assets; trusted checks/reference material only for qualification and acceptance. Write scope: new functional-closeout module/tests, necessary declared integration fixes, docs/goals, this OpenSpec change and configs/artifacts/docs/research under repair-knowledge-functional-closeout-v1. Private execution output is a new sibling hermes-functional-closeout-private directory. Frozen asset scope: selected task bases/requests, overlays, skills, encoder, image, cost envelope and method sources identified by plan. Final repository scope: entire tracked delta from inherited baseline; no historical artifact edits.

## Risks / Trade-offs

- Correlated tiny sample → task-weighted counts and missing bounds, no generalization claim.
- Same package/fallback → retain denominator and all preparation charges.
- Resume/capture ambiguity → retain attempt and UNKNOWN, no fresh substitute.
- Hidden test leakage → retain existing isolated runner and separate trusted acceptance.
