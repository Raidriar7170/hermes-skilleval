# Design

## Inputs

The scorer consumes:

- a SkillRouter data root accepted by the PR-1 adapter;
- a predictions JSON/JSONL file mapping `task_id` to ranked `skill_ids`.

Predictions are already-ranked IDs. The scorer does not call a router or model.

## Metric Semantics

For each eligible task, the scorer builds a tier-filtered relevance map:

- Start from the PR-1 task graded relevance map.
- Keep only skills present in that task tier's skill pool.
- Select ground-truth IDs by mode:
  - `core`: `core_gt_ids` if non-empty, otherwise `gt_skill_ids`;
  - `single`: `gt_skill_ids`, only tasks where `len(gt_skill_ids) == 1`.
- Drop `generic_only` tasks in core mode.
- Do not infer negative labels and do not compute Hermes Negative Hit Rate.

Per-task official metrics:

- `nDCG@k`: graded DCG divided by ideal graded DCG at `k`.
- `Hit@1`: 1 when the first predicted skill is in the selected GT set.
- `Precision@3`: relevant selected GT hits in top 3 divided by 3.
- `MRR@10`: reciprocal rank of first selected GT hit in top 10.
- `Recall@k`: selected GT hits in top `k` divided by selected GT count.
- `FullCoverage@k`: 1 when all selected GT IDs appear in top `k`.

Tasks missing from the predictions file are skipped, matching partial
submission scoring. Aggregate `single` and `multi` slices are based on selected
GT cardinality, not task label strings.

## Output

The scorer returns JSON with schema, benchmark, mode, task counts, per-slice
aggregates, and optional per-task rows for auditability. Slices are keyed by
`all`, `single`, `multi`, `easy`, and `hard`.

## Boundaries

The scorer is deterministic and local. It must not download data, import model
libraries, run inference, or promote release artifacts.
