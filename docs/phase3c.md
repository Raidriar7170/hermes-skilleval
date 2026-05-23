# Phase 3C: Failure Analysis

Phase 3C turns the Phase 3B benchmark from a score table into actionable error
diagnostics.

## What Changed

- Added `skilleval analyze-failures` for comparison directories.
- Added `failure_analysis.py`, which reads per-router `results.jsonl` files and
  writes a Markdown report.
- The report summarizes:
  - top-1 misses,
  - missing gold skills at top-5,
  - negative skill hits at top-5,
  - candidate-vs-baseline metric deltas,
  - per-task improvements, regressions, and trade-offs.
- Committed the Phase 3B failure analysis artifact at
  [`docs/demo/phase3b-real-embedding/failure-analysis.md`](demo/phase3b-real-embedding/failure-analysis.md).

## Key Findings

MiniLM substantially reduces embedding-router failures compared with the
hashing baseline:

| Router | Top-1 Misses | Missing Gold@5 | Negative Hits@5 | Any Failure |
| --- | ---: | ---: | ---: | ---: |
| embedding-hashing | 7 | 2 | 3 | 11 |
| embedding-minilm | 2 | 0 | 1 | 3 |
| hybrid | 0 | 0 | 1 | 1 |
| keyword | 0 | 0 | 1 | 1 |

Against `embedding-hashing`, `embedding-minilm` improves Recall@1 by `+0.150`,
Recall@5 by `+0.033`, MRR by `+0.093`, and NDCG@5 by `+0.091`. It also lowers
negative hit rate from `0.100` to `0.033`.

## Remaining MiniLM Failures

- `coding-debugging-002`: MiniLM ranks the gold skill first but still includes
  the negative `ascii-art` skill in top-5.
- `coding-debugging-009`: MiniLM puts `systematic-debugging` above the gold
  `test-driven-development`, a plausible coding-skill ambiguity.
- `data-mlops-006`: MiniLM ranks broader `data-analysis` above the gold
  `python-data-analysis`, showing a hierarchy/granularity issue.

## Interpretation

The failure pattern points to reranking and verification as the next useful
layer. MiniLM is good enough to retrieve the right region of the skill space,
but top-1 precision and negative-skill suppression still need help.

Concrete next improvements:

- Add a lightweight reranker that scores the top retrieved skills using task,
  skill description, trigger terms, and category agreement.
- Add a negative-skill guardrail that penalizes skills explicitly labeled as
  negative in benchmark/evaluation mode.
- Add hierarchy-aware metadata for near-duplicate skills such as
  `data-analysis` and `python-data-analysis`.
- Use failure cases to propose targeted skill description or trigger-term
  edits, then re-run the benchmark to measure improvement.

## Reproduce

```bash
skilleval analyze-failures \
  --runs docs/demo/phase3b-real-embedding \
  --baseline embedding-hashing \
  --candidate embedding-minilm \
  --output docs/demo/phase3b-real-embedding/failure-analysis.md
```
