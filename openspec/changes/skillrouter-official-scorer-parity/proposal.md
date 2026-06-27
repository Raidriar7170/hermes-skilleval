# SkillRouter Official Scorer Parity

## Summary

Implement PR-2 scorer-only parity for SkillRouter official metrics on top of
the PR-1 external adapter/provenance surface.

## Motivation

PR-1 can validate and describe real-shaped SkillRouter Eval Core inputs, but it
does not compute official benchmark metrics. PR-2 needs a bounded scorer that
can consume ranked predictions and reproduce official metric definitions
without running routers, embeddings, rerankers, model inference, training, live
agents, or release promotion.

## Scope

- Compute nDCG@1/3/10, Hit@1, Precision@3, MRR@10, Recall@10/20/50, and
  FullCoverage@3/5/10.
- Aggregate metrics over all/single/multi and easy/hard slices.
- Implement official task filtering:
  - core mode drops `task_type == generic_only`;
  - core mode uses `core_gt_ids` with fallback to `gt_skill_ids`;
  - single mode uses `gt_skill_ids` and keeps only `len(gt_ids) == 1`;
  - tier relevance is filtered to the tier pool.
- Add hand-computable tiny fixture tests and an optional scorer CLI.

## Out Of Scope

- Running routers, embeddings, rerankers, model inference, training, or live
  agents.
- Release promotion or public readiness claims.
- Hermes Negative Hit Rate for SkillRouter unless explicit negative labels
  exist.
- PR-1 adapter/provenance API changes unless scorer tests prove a contract bug.

## Acceptance

- Focused scorer tests pass with hand-computable expected values.
- Full repository validation passes before opening PR-2.
- Scorer output clearly separates official SkillRouter metrics from Hermes
  diagnostics.
