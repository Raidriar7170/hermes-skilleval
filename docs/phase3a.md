# Phase 3A: Real Embedding Router

Phase 3A upgrades the embedding router from a purely local hashing baseline to
a configurable backend that can run real sentence-transformer models.

## What Changed

- Added `SentenceTransformerEmbeddingModel`, a lazy optional wrapper around
  `sentence_transformers.SentenceTransformer`.
- Added `--embedding-backend` with two modes:
  - `hashing`: default, dependency-free, deterministic, Mac-friendly.
  - `sentence-transformers`: real neural embedding retrieval.
- Added `--embedding-model` for selecting a model such as
  `sentence-transformers/all-MiniLM-L6-v2`.
- Added `--embedding-cache` for storing skill vectors in JSON so repeated runs
  avoid recomputing the static skill library.
- Preserved the existing `EmbeddingRouter` interface so keyword, hybrid, and
  embedding comparisons still work through the same CLI flow.
- Added CLI error handling for missing optional dependencies with an install
  hint instead of a traceback.

## Installation

The default project remains lightweight:

```bash
python -m pip install -e ".[dev]"
```

Install the optional neural embedding backend when you want to run real models:

```bash
python -m pip install -e ".[dev,embedding]"
```

## Usage

Run one real embedding evaluation:

```bash
skilleval eval \
  --index docs/demo/skills.json \
  --tasks benchmarks/tasks \
  --router embedding \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache runs/embeddings/all-MiniLM-L6-v2.json \
  --top-k 5 \
  --output-dir runs/embedding-real
```

Compare the real embedding router against the lexical baselines:

```bash
skilleval compare \
  --index docs/demo/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache runs/embeddings/all-MiniLM-L6-v2.json \
  --top-k 5 \
  --output-dir runs/comparison-real-embedding
```

## Hardware Notes

This phase is still Mac-friendly. Small sentence-transformer encoders such as
`all-MiniLM-L6-v2` can run locally on CPU for a small skill library. The remote
8xA100 machine becomes useful later for large benchmark sweeps, embedding
fine-tuning, cross-encoder reranking, verifier execution at scale, and
self-improvement loops.

## Verification

The local development environment used for this phase did not have
`sentence_transformers` installed. The integration is covered by tests that
inject a fake `sentence_transformers` module and verify that:

- the configured model name is passed into `SentenceTransformer`;
- `encode(..., normalize_embeddings=True)` is used;
- embeddings are converted into plain Python float vectors;
- skill vectors are cached and reused across routes;
- missing optional dependencies return a clean CLI error.

The hashing backend remains the default path for CI and local smoke tests.
