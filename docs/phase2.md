# Phase 2: Embedding Router and Router Comparison

Phase 2 extends the MVP from single-router evaluation to repeatable router
comparison experiments.

## What Changed

- Added a dependency-free `EmbeddingRouter` backed by a deterministic hashing
  embedding model.
- Added `skilleval eval --router embedding`.
- Added `skilleval compare` to run multiple routers against the same task set
  and write:
  - one `results.jsonl` per router,
  - one `report.md` per router,
  - one aggregate `comparison.md`.
- Added tests for embedding ranking, validation, CLI smoke flows, and comparison
  report generation.
- Regenerated demo comparison artifacts under `docs/demo/router-comparison`.

## Why The Embedding Router Is Local

The current router is intentionally dependency-free so the project remains easy
to run on a Mac and in CI. It uses hashed token and bigram features to produce
normalized sparse vectors and cosine similarity scores.

This gives the project a stable embedding-style baseline and a clean extension
point for later sentence-transformer, BGE, E5, or reranker models.

Phase 3A uses that extension point to add an optional real
`sentence-transformers` backend while keeping this local hashing router as the
default. See [`phase3a.md`](phase3a.md).

## Demo Command

```bash
skilleval compare \
  --index docs/demo/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding \
  --top-k 5 \
  --output-dir docs/demo/router-comparison
```

The comparison report is at
[`docs/demo/router-comparison/comparison.md`](demo/router-comparison/comparison.md).
