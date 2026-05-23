# Phase 4A: Verification-Gated Reranker

Phase 4A adds a deterministic verifier-style reranking layer on top of
embedding retrieval. It targets the Phase 3C MiniLM failure pattern: the neural
retriever usually finds the right neighborhood, but still has top-choice
ambiguity between similar skills.

## What Changed

- Added `VerificationGatedRouter` in `routers/gated.py`.
- Added the `gated` CLI router:
  - `--router gated` for single-router evaluation.
  - `gated-minilm=gated:sentence-transformers` for multi-router comparison.
  - `--gated-pool-size` to control how many embedding candidates are reranked.
- The gated router:
  - calls an embedding router for candidate retrieval,
  - reranks candidates by category agreement, lexical task-skill evidence,
    exact skill-id mentions, and the base embedding score,
  - does not use `gold_skills` or `negative_skills` at routing time.
- Added unit and CLI smoke coverage for candidate-pool sizing, category
  demotion, same-category prompt evidence, and labeled gated backend specs.
- Committed the Phase 4A comparison and failure-analysis artifacts under
  `docs/demo/phase4a-gated-reranker`.

## Results

Warm-cache run over the 30-task benchmark and generated 20-skill library:

| Router | Recall@1 | Recall@3 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-hashing | 0.717 | 0.933 | 0.967 | 0.873 | 0.882 | 0.100 | 0.396 |
| embedding-minilm | 0.867 | 1.000 | 1.000 | 0.967 | 0.973 | 0.033 | 23.163 |
| gated-minilm | 0.933 | 1.000 | 1.000 | 1.000 | 1.000 | 0.033 | 8.202 |
| hybrid | 0.933 | 1.000 | 1.000 | 1.000 | 1.000 | 0.033 | 0.327 |
| keyword | 0.933 | 1.000 | 1.000 | 1.000 | 1.000 | 0.033 | 0.215 |

Compared with `embedding-minilm`, `gated-minilm` improves:

- Recall@1: `0.867 -> 0.933`
- MRR: `0.967 -> 1.000`
- NDCG@5: `0.973 -> 1.000`
- Top-choice failure count: `2 -> 0`

The observed latency is lower than the standalone MiniLM row in this run, but
that should be interpreted cautiously because local sentence-transformer
warmup and command ordering can affect per-query timing. The gated reranker's
own overhead is small and deterministic; the embedding model remains the main
cost.

## Fixed Failure Modes

The reranker fixes both MiniLM top-choice errors from Phase 3C:

- `coding-debugging-009`: promotes `test-driven-development` over
  `systematic-debugging` because the prompt mentions refactoring, preserving
  behavior, and tests.
- `data-mlops-006`: promotes `python-data-analysis` over broader
  `data-analysis` because the prompt evidence is more specific.

## Remaining Risk

`coding-debugging-002` still includes the negative `ascii-art` skill in the
top-5. The top skill is correct, but the benchmark asks for five results while
the generated benchmark library has only two `coding` skills. After the
category-matched skills are exhausted, the router must fill remaining slots
from other categories.

This points to two future extensions:

- add abstention or variable-k output when verifier confidence drops,
- add a stricter cross-category suppression policy for production routing,
  evaluated separately from the fixed top-5 benchmark metric.

Phase 4B implements the first extension as selective verification-gated
routing.

## Reproduce

```bash
skilleval compare \
  --index docs/demo/phase3b-real-embedding/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding-hashing=embedding:hashing,embedding-minilm=embedding:sentence-transformers,gated-minilm=gated:sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase4a-minilm-cache.json \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir docs/demo/phase4a-gated-reranker
```

```bash
skilleval analyze-failures \
  --runs docs/demo/phase4a-gated-reranker \
  --baseline embedding-minilm \
  --candidate gated-minilm \
  --output docs/demo/phase4a-gated-reranker/failure-analysis.md
```
