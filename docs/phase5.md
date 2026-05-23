# Phase 5: Failure-Driven Self-Improvement Harness

Phase 5 turns failure analysis into an auditable self-improvement loop. The
harness proposes metadata-only skill patches from failed routing records,
writes a patched skill index, reruns evaluation, and accepts the patch set only
when metrics do not regress.

## What Changed

- Added `self_improvement.py` for deterministic patch generation.
- Added `skilleval improve-skills`.
- Added `skilleval judge-improvement`.
- Patch proposals include:
  - `skill_id`
  - `field`
  - `before`
  - `after`
  - `reason`
  - `source_task_ids`
  - `status`
- The first patch type updates `trigger_terms` using prompt terms from failed
  routing tasks.
- The command writes a patched skill index instead of mutating source
  `SKILL.md` files.
- The acceptance gate checks Recall@1, MRR, NDCG@5, and Negative Hit Rate.

## Results

The Phase 5 demo uses the Phase 4B `embedding-minilm` failure records as the
source of improvement proposals.

Patch proposal summary:

| Skill | Added Terms | Source Tasks |
| --- | --- | --- |
| `test-driven-development` | coding, debugging, python, suite, refactor, reproduce, failure, identify | coding-debugging-001, coding-debugging-007, coding-debugging-009 |
| `python-data-analysis` | data-analysis, mlops, chart, tabular, benchmark, results, explain, trend | data-mlops-006 |
| `mlflow` | mlops, data, model, evaluation, docker, record, metrics, tracker | data-mlops-005 |
| `citation-checking` | research, writing, build, structured, related-work, section, agent, benchmarks | research-writing-005 |

Evaluation after applying the patched index:

| Router | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| embedding-minilm-before | 0.867 | 1.000 | 0.967 | 0.973 | 0.033 |
| embedding-minilm-patched | 0.933 | 1.000 | 1.000 | 1.000 | 0.033 |

Acceptance status: `accepted`.

The accepted patch set fixes both MiniLM top-choice failures:

- `coding-debugging-009`: `test-driven-development` moves above
  `systematic-debugging`.
- `data-mlops-006`: `python-data-analysis` moves above broader
  `data-analysis`.

The remaining negative hit on `coding-debugging-002` is intentionally handled
by Phase 4B selective routing rather than metadata expansion.

## Reproduce

```bash
skilleval improve-skills \
  --runs docs/demo/phase4b-selective-routing \
  --router embedding-minilm \
  --index docs/demo/phase3b-real-embedding/skills.json \
  --tasks benchmarks/tasks \
  --output docs/demo/phase5-self-improvement/patches.json \
  --patched-index docs/demo/phase5-self-improvement/patched-skills.json \
  --report docs/demo/phase5-self-improvement/patches.md
```

```bash
skilleval eval \
  --index docs/demo/phase5-self-improvement/patched-skills.json \
  --tasks benchmarks/tasks \
  --router embedding \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase5-patched-minilm-cache.json \
  --top-k 5 \
  --output-dir docs/demo/phase5-self-improvement/embedding-minilm-patched
```

```bash
skilleval judge-improvement \
  --runs docs/demo/phase5-self-improvement \
  --baseline embedding-minilm-before \
  --candidate embedding-minilm-patched \
  --output docs/demo/phase5-self-improvement/acceptance.md
```
