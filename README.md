# Hermes SkillEval

Hermes SkillEval is an offline CLI harness for evaluating skill routing in
Hermes-style agent skill libraries.

The project indexes `skills/**/SKILL.md`, loads labeled benchmark tasks,
compares routing strategies, and writes JSONL records plus Markdown reports
with deterministic routing metrics and latency metadata. The default workflows
do not require Hermes Agent, network access, or an LLM API key.

## Highlights

- Parses Hermes-style skill files with YAML frontmatter, fallback metadata,
  category inference, trigger terms, and token estimates.
- Evaluates keyword, hybrid, embedding, and verification-gated skill routers
  with deterministic ranking, top-k validation, score traces, latency tracking,
  and an optional `sentence-transformers` backend with a JSON skill-embedding
  cache.
- Reports Recall@1, Recall@3, Recall@5, Precision@5, MRR, NDCG@5,
  Negative Hit Rate, selective accepted-output metrics, top selected skills,
  and failure cases.
- Includes a 30-task benchmark corpus and a reproducible generator that keeps
  the committed benchmark directory in sync with its source list.
- Includes a generated 20-skill benchmark library so every benchmark gold and
  negative label has a corresponding Hermes-style `SKILL.md`.
- Provides robust CLI error handling, schema validation, Markdown escaping,
  and pytest coverage for parser, loader, router, metrics, report, and CLI
  edge cases.
- Compares multiple routers in one command and writes a Markdown comparison
  table for experiment tracking.
- Analyzes failed routes by failure mode, including top-1 misses, missing gold
  skills, negative hits, and candidate-vs-baseline trade-offs.
- Proposes failure-driven skill metadata patches, writes patched skill indexes,
  and verifies before/after runs with an acceptance gate.

## Quickstart

Install in editable mode:

```bash
python -m pip install -e ".[dev]"
```

Install the optional neural embedding backend:

```bash
python -m pip install -e ".[dev,embedding]"
```

Index a skills directory:

```bash
skilleval index --skills-path /path/to/hermes/skills --output index/skills.json
```

Run an evaluation:

```bash
skilleval eval \
  --index index/skills.json \
  --tasks benchmarks/tasks \
  --router hybrid \
  --top-k 5 \
  --output-dir runs/latest
```

Generate a report:

```bash
skilleval report --runs runs/latest
```

Compare routers:

```bash
skilleval compare \
  --index index/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding \
  --top-k 5 \
  --output-dir runs/comparison
```

Analyze comparison failures:

```bash
skilleval analyze-failures \
  --runs runs/comparison \
  --baseline embedding-hashing \
  --candidate embedding-minilm
```

Propose and verify skill metadata improvements:

```bash
skilleval improve-skills \
  --runs runs/comparison \
  --router embedding-minilm \
  --index index/skills.json \
  --tasks benchmarks/tasks \
  --output runs/improvement/patches.json \
  --patched-index runs/improvement/patched-skills.json \
  --report runs/improvement/patches.md

skilleval judge-improvement \
  --runs runs/improvement \
  --baseline embedding-minilm-before \
  --candidate embedding-minilm-patched \
  --output runs/improvement/acceptance.md
```

Run the real embedding router with a cached sentence-transformer model:

```bash
skilleval eval \
  --index index/skills.json \
  --tasks benchmarks/tasks \
  --router embedding \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache runs/embeddings/all-MiniLM-L6-v2.json \
  --top-k 5 \
  --output-dir runs/embedding-real
```

Run the verification-gated reranker on top of a cached sentence-transformer
retriever:

```bash
skilleval eval \
  --index index/skills.json \
  --tasks benchmarks/tasks \
  --router gated \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache runs/embeddings/all-MiniLM-L6-v2.json \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir runs/gated-real
```

Enable selective routing to suppress low-confidence candidates:

```bash
skilleval eval \
  --index index/skills.json \
  --tasks benchmarks/tasks \
  --router gated \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache runs/embeddings/all-MiniLM-L6-v2.json \
  --selective \
  --min-confidence 0.5 \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir runs/gated-selective
```

Run tests:

```bash
pytest -v
```

## Demo

A committed demo run is available at
[`docs/demo/benchmark-hybrid/report.md`](docs/demo/benchmark-hybrid/report.md).
It was generated with the tiny fixture skill library in `tests/fixtures/skills`
against the 30 built-in benchmark tasks, so it is a smoke/demo artifact rather
than a production routing score.

Phase 2 also includes a committed router comparison at
[`docs/demo/router-comparison/comparison.md`](docs/demo/router-comparison/comparison.md).
The implementation notes are in [`docs/phase2.md`](docs/phase2.md).
Phase 3A adds the optional real embedding backend documented in
[`docs/phase3a.md`](docs/phase3a.md).
Phase 3B adds a committed MiniLM comparison run at
[`docs/demo/phase3b-real-embedding/comparison.md`](docs/demo/phase3b-real-embedding/comparison.md)
with implementation notes in [`docs/phase3b.md`](docs/phase3b.md).
Phase 3C adds failure analysis for that run at
[`docs/demo/phase3b-real-embedding/failure-analysis.md`](docs/demo/phase3b-real-embedding/failure-analysis.md)
with notes in [`docs/phase3c.md`](docs/phase3c.md).
Phase 4A adds a verification-gated reranker over MiniLM retrieval at
[`docs/demo/phase4a-gated-reranker/comparison.md`](docs/demo/phase4a-gated-reranker/comparison.md)
with notes in [`docs/phase4a.md`](docs/phase4a.md).
Phase 4B adds selective verification-gated routing at
[`docs/demo/phase4b-selective-routing/comparison.md`](docs/demo/phase4b-selective-routing/comparison.md)
with notes in [`docs/phase4b.md`](docs/phase4b.md).
Phase 5 adds a failure-driven self-improvement loop at
[`docs/demo/phase5-self-improvement/comparison.md`](docs/demo/phase5-self-improvement/comparison.md)
with notes in [`docs/phase5.md`](docs/phase5.md).

To regenerate it:

```bash
skilleval index --skills-path tests/fixtures/skills --output docs/demo/skills.json
skilleval eval --index docs/demo/skills.json --tasks benchmarks/tasks --router hybrid --top-k 5 --output-dir docs/demo/benchmark-hybrid
skilleval report --runs docs/demo/benchmark-hybrid
skilleval compare --index docs/demo/skills.json --tasks benchmarks/tasks --routers keyword,hybrid,embedding --top-k 5 --output-dir docs/demo/router-comparison
python scripts/generate_benchmark_skills.py
skilleval index --skills-path benchmarks/skills --output docs/demo/phase3b-real-embedding/skills.json
skilleval compare \
  --index docs/demo/phase3b-real-embedding/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding-hashing=embedding:hashing,embedding-minilm=embedding:sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase3b-minilm-cache.json \
  --top-k 5 \
  --output-dir docs/demo/phase3b-real-embedding
skilleval analyze-failures \
  --runs docs/demo/phase3b-real-embedding \
  --baseline embedding-hashing \
  --candidate embedding-minilm \
  --output docs/demo/phase3b-real-embedding/failure-analysis.md
skilleval compare \
  --index docs/demo/phase3b-real-embedding/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding-hashing=embedding:hashing,embedding-minilm=embedding:sentence-transformers,gated-minilm=gated:sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase4a-minilm-cache.json \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir docs/demo/phase4a-gated-reranker
skilleval analyze-failures \
  --runs docs/demo/phase4a-gated-reranker \
  --baseline embedding-minilm \
  --candidate gated-minilm \
  --output docs/demo/phase4a-gated-reranker/failure-analysis.md
skilleval compare \
  --index docs/demo/phase3b-real-embedding/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding-minilm=embedding:sentence-transformers,gated-minilm-selective=gated:sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase4b-minilm-cache.json \
  --selective \
  --min-confidence 0.5 \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir docs/demo/phase4b-selective-routing
skilleval analyze-failures \
  --runs docs/demo/phase4b-selective-routing \
  --baseline embedding-minilm \
  --candidate gated-minilm-selective \
  --output docs/demo/phase4b-selective-routing/failure-analysis.md
skilleval improve-skills \
  --runs docs/demo/phase4b-selective-routing \
  --router embedding-minilm \
  --index docs/demo/phase3b-real-embedding/skills.json \
  --tasks benchmarks/tasks \
  --output docs/demo/phase5-self-improvement/patches.json \
  --patched-index docs/demo/phase5-self-improvement/patched-skills.json \
  --report docs/demo/phase5-self-improvement/patches.md
skilleval eval \
  --index docs/demo/phase5-self-improvement/patched-skills.json \
  --tasks benchmarks/tasks \
  --router embedding \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase5-patched-minilm-cache.json \
  --top-k 5 \
  --output-dir docs/demo/phase5-self-improvement/embedding-minilm-patched
skilleval judge-improvement \
  --runs docs/demo/phase5-self-improvement \
  --baseline embedding-minilm-before \
  --candidate embedding-minilm-patched \
  --output docs/demo/phase5-self-improvement/acceptance.md
```

## Benchmark Corpus

The built-in benchmark suite lives in `benchmarks/tasks`. Each task directory
contains:

- `task.yaml`: task id, category, difficulty, gold skill labels, negative skill
  labels, and verifier type.
- `prompt.md`: the user request to route.

Regenerate the corpus from its source list:

```bash
python scripts/generate_benchmark_tasks.py
```

The companion benchmark skill library lives in `benchmarks/skills` and covers
all labels used by the task corpus. Regenerate it with:

```bash
python scripts/generate_benchmark_skills.py
```

## Architecture

```text
skills/**/SKILL.md      benchmarks/tasks
        |                       |
        v                       v
  skill_parser.py        task_loader.py
        |                       |
        +----------+------------+
                   v
             CLI eval command
                   |
       +-----------+-----------+-----------+
       v                       v           v
 keyword router           hybrid router   embedding router
       |                       |           |
       |                       |           v
       |                       |    gated reranker
       |                       |           |
       +-----------+-----------+-----------+
                   v
          metrics + JSONL results
                   |
          +--------+--------+
          v                 v
    Markdown report   comparison report
```

Core modules:

- `skill_parser.py`: Hermes-style skill discovery and parsing.
- `task_loader.py`: benchmark task loading and validation.
- `routers/keyword.py`: deterministic lexical baseline.
- `routers/hybrid.py`: offline hybrid router with category and explicit skill-id
  boosts.
- `routers/embedding.py`: dependency-free local hashing router plus optional
  `sentence-transformers` embedding router with a disk cache for skill vectors.
- `routers/gated.py`: verification-gated reranker that reranks embedding
  candidates with category agreement, lexical evidence, and base retriever
  scores.
- `metrics.py`: ranking metrics and negative-skill checks.
- `report.py`: validated JSONL-to-Markdown reporting.
- `comparison.py`: aggregate router comparison reports.
- `failure_analysis.py`: failure-mode summaries and candidate-vs-baseline
  diagnostics for comparison runs.
- `self_improvement.py`: deterministic failure-driven metadata patch proposals
  and improvement acceptance reports.
- `cli.py`: `index`, `eval`, `report`, `compare`, `analyze-failures`,
  `improve-skills`, and `judge-improvement` commands.

## Scope

This MVP evaluates skill selection only. Real Hermes execution, LLM judges,
embedding fine-tuning, cross-encoder reranking, source `SKILL.md` editing, and
web dashboards are planned future extensions.

## Portfolio Notes

Resume-ready project framing and interview talking points are in
[`docs/resume.md`](docs/resume.md).
