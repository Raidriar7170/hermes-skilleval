# Phase 6A Robustness Benchmark Design

## Goal

Phase 6A makes Hermes SkillEval more credible by expanding the benchmark from
a small demo corpus into a first robustness pack.

## Scope

- Increase generated benchmark tasks from 30 to 80.
- Increase generated benchmark skills from 20 to 45.
- Add task metadata:
  - `split`: `dev` or `test`
  - `robustness_tags`: one or more tags describing the challenge type.
- Keep router implementations unchanged.
- Keep the existing 30-task benchmark behavior available inside the expanded
  corpus, but treat it as part of the dev split.

## Task Mix

New tasks emphasize ambiguous agent-routing cases:

- coding: debugging vs test-driven development vs packaging
- research: summary vs literature review vs citation checking
- data/mlops: Python analysis vs broader data analysis vs MLflow/W&B/Docker
- agent workflows: skill routing, verifier gates, self-improvement harnesses,
  context management, tool planning
- retrieval/evaluation: RAG, vector search, cross-encoder reranking, LLM judge
  design, dataset curation
- multimodal: ASR evaluation, audio preprocessing, multimodal alignment,
  captioning
- infrastructure: CI, model serving, distributed training, CUDA profiling

## Validation

- Tests assert generated task count is 80.
- Tests assert generated skill count is 45.
- Tests assert every task has `split` and non-empty `robustness_tags`.
- Tests assert both `dev` and `test` splits exist.
- Tests assert generated skills cover every gold and negative task label.
- Demo artifacts live under `docs/demo/phase6a-robustness`.

## Non-Goals

- No model training or fine-tuning.
- No dashboard.
- No new router algorithm.
- No source `SKILL.md` human-review workflow.
