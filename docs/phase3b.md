# Phase 3B: MiniLM Benchmark Run

Phase 3B turns the optional sentence-transformer backend into a committed,
resume-ready experiment.

## What Changed

- Added labeled compare specs so one run can compare multiple configurations of
  the same router:
  - `embedding-hashing=embedding:hashing`
  - `embedding-minilm=embedding:sentence-transformers`
- Added `scripts/generate_benchmark_skills.py`, which creates a 20-skill
  Hermes-style library under `benchmarks/skills`.
- Generated benchmark skills cover every gold and negative label in the 30-task
  benchmark corpus.
- Ran `sentence-transformers/all-MiniLM-L6-v2` locally on Mac CPU and committed
  the resulting comparison artifacts under `docs/demo/phase3b-real-embedding`.

## Benchmark Setup

- Tasks: 30 built-in benchmark tasks from `benchmarks/tasks`.
- Skills: 20 generated benchmark skills from `benchmarks/skills`.
- Top-k: 5.
- Model: `sentence-transformers/all-MiniLM-L6-v2`.
- Cache: warm skill-vector JSON cache outside the repository.
- Hardware: local Mac CPU.

## Results

| Router | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| keyword | 0.933 | 1.000 | 1.000 | 1.000 | 0.033 | 0.204 |
| hybrid | 0.933 | 1.000 | 1.000 | 1.000 | 0.033 | 0.325 |
| embedding-hashing | 0.717 | 0.967 | 0.873 | 0.882 | 0.100 | 0.394 |
| embedding-minilm | 0.867 | 1.000 | 0.967 | 0.973 | 0.033 | 28.115 |

Full artifacts:

- [`docs/demo/phase3b-real-embedding/comparison.md`](demo/phase3b-real-embedding/comparison.md)
- [`docs/demo/phase3b-real-embedding/embedding-minilm/report.md`](demo/phase3b-real-embedding/embedding-minilm/report.md)
- [`docs/demo/phase3b-real-embedding/embedding-hashing/report.md`](demo/phase3b-real-embedding/embedding-hashing/report.md)

## Interpretation

MiniLM materially improves the embedding route over the dependency-free hashing
baseline: Recall@1 rises from 0.717 to 0.867, Recall@5 reaches 1.000, MRR rises
from 0.873 to 0.967, and negative hit rate drops from 0.100 to 0.033.

Keyword and hybrid remain strongest on this generated benchmark because many
tasks and generated skill descriptions intentionally share clear domain terms.
That result is useful because it shows why a harness matters. Real agent
routing should compare cheap lexical baselines against neural retrieval instead
of assuming embeddings always win.

## Reproduce

Install the optional embedding backend:

```bash
python -m pip install -e ".[embedding]"
```

Regenerate the benchmark skills and run the four-way comparison:

```bash
python scripts/generate_benchmark_skills.py
skilleval index \
  --skills-path benchmarks/skills \
  --output docs/demo/phase3b-real-embedding/skills.json
skilleval compare \
  --index docs/demo/phase3b-real-embedding/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding-hashing=embedding:hashing,embedding-minilm=embedding:sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase3b-minilm-cache.json \
  --top-k 5 \
  --output-dir docs/demo/phase3b-real-embedding
```

If the environment uses a SOCKS proxy for Hugging Face downloads, the
`embedding` extra includes `socksio` so `httpx` can use that proxy.
