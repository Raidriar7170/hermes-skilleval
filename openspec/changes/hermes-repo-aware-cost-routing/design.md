## Context

The complete active Goal in docs/goals is the design authority. This document only binds its implementation to inherited PR47 modules.

## Goals / Non-Goals

Implement Goal M0–M8 without changing historical evidence, legacy arms or native default. No merge/release or new paid resources.

## Decisions

Reuse SkillRouterOpen encoder and causal yes/no scoring, train LoRA on repair-family separated text preferences, then freeze complete R before N/F/R feedback collection. Use deterministic AST/TOML context and exact subset enumeration. Fit lightweight JSON action models on complete feedback with separate calibration. Both existing maintenance entrypoints share one policy function and the same sourced Agent context. Preserve existing isolated capture/rebuild/checks.

## Risks / Trade-offs

Small local study → PILOT and no generalized gain claim. Unknown outcomes → missing quality labels. Public historical repairs → pretraining contamination cannot be excluded. Missing resources → preserve attempts and explicit partial status. Late evaluation policy bug → retain original evidence and uniformly correct affected scope.

## R repair v1 continuation

The newly designated `docs/goals/Hermes_PR48_R_Support_Context_Repair_Codex_Goal.md`
authorizes M0–M5 as a separate repair on this Draft. The preceding design and
completed pilot remain historical. V2 source fragments and structured inputs,
absolute text labels and an independent affine support calibration replace the
experimental R semantics only under explicit `experimental_repair` configuration.
B2/C2 use the same frozen rank adapter and pool. Old Gate feedback is incompatible;
native remains default and no Gate training or original matrix rerun is authorized.

## Conditional applicability v1 continuation

The new designated Applicability Data Pointwise Learning Goal supersedes only the current research scope. Preserve prior records. Use independent group-disjoint fit/model-dev/cal/check, APPLICABLE versus explicit inapplicability and conditional specificity, a separately trained shared LoRA with two instructions, fit-only priors and cheap lexical comparisons. Reuse structured token handling and causal yes/no scorer. Runtime remains conditional on frozen nonzero support criteria; no Gate training, default promotion or archive.

## Decision alignment continuation

The active Decision Alignment Calibration Preflight Goal and `configs/decision-alignment-v1/protocol.json` define the current bounded change. Reuse six checkpoints and saved predictions; select A by applicability and directly supervised J by its raw product event loss on model-dev. Historical check remains retrospective. Add a thin CLI dispatcher, shared no-forward eligibility, and evidence-grounded context repair. Preserve all historical bound source modules where possible. No training, new Agent runs, default promotion, merge or archive.
