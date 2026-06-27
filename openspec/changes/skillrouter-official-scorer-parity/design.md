# Design

## Inputs

The scorer consumes:

- a SkillRouter data root accepted by the PR-1 adapter;
- a predictions JSON/JSONL file mapping `task_id` to ranked `skill_ids`.

Predictions are already-ranked IDs. The scorer does not call a router or model.

## Metric Semantics

For each selected evaluation tier, the scorer loads that tier's candidate skill
pool and scores all eligible tasks against that pool. Easy/Hard are candidate
pool tiers, not task difficulty groups. For each eligible task, the scorer
builds a tier-filtered relevance map:

- Start from the PR-1 task graded relevance map.
- Keep only skills present in the selected candidate skill pool tier.
- Select ground-truth IDs by mode:
  - `core`: `core_gt_ids` as-is when the key is present, otherwise
    `gt_skill_ids`;
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

For a single tier, the scorer returns JSON with schema, benchmark, mode, tier,
task counts, `all`/`single`/`multi` aggregates, and optional per-task rows for
auditability. For combined tier reports, the output uses `by_tier.easy` and
`by_tier.hard`.

## Boundaries

The scorer is deterministic and local. It must not download data, import model
libraries, run inference, or promote release artifacts.
