## Context
The user-designated complete Goal is docs/goals/Hermes_ASI_v2_Functional_Gain_Same_State_Codex_Goal.md. Its sections 3–30 settle the design and acceptance contract; this is a lifecycle index, not a second design.

## Goals / Non-Goals
Implement the Goal's G0–G6, separating research execution, trained models and functional/mechanism claims. Preserve v1 and existing defaults. Exclude new agents, RL, skill generation, infrastructure platforms, purchases and release.

## Decisions
Use explicit v2 modules alongside v1. Functional labels require valid target and regression evidence and integrity; ordinary file-policy rejection is secondary. Shared frozen candidate payloads isolate representation. Myopic reuses full gain weights. Waiting continuations use their own actual future states and original remaining budget. Train/dev/test families stay disjoint and final feedback cannot drive selection.

## Risks / Trade-offs
Constant functional labels → retain all samples, report insufficient signal and PARTIAL_METHOD; do not learn policy/cost as a substitute. Missing execution/verifier evidence → UNKNOWN and complete planned denominators. Observable-prefix stochastic comparisons → mechanism-clustered descriptive uncertainty, no hidden-state cloning claim.

## Migration Plan
New branch and stacked Draft PR from v1, explicit v2 commands only. No promotion or migration of old records.
