## Context

The complete active Goal in docs/goals is the design authority. This document only binds its implementation to inherited PR47 modules.

## Goals / Non-Goals

Implement Goal M0–M8 without changing historical evidence, legacy arms or native default. No merge/release or new paid resources.

## Decisions

Reuse SkillRouterOpen encoder and causal yes/no scoring, train LoRA on repair-family separated text preferences, then freeze complete R before N/F/R feedback collection. Use deterministic AST/TOML context and exact subset enumeration. Fit lightweight JSON action models on complete feedback with separate calibration. Both existing maintenance entrypoints share one policy function and the same sourced Agent context. Preserve existing isolated capture/rebuild/checks.

## Risks / Trade-offs

Small local study → PILOT and no generalized gain claim. Unknown outcomes → missing quality labels. Public historical repairs → pretraining contamination cannot be excluded. Missing resources → preserve attempts and explicit partial status. Late evaluation policy bug → retain original evidence and uniformly correct affected scope.
