# Demo Run

This directory contains a committed demo run for Hermes SkillEval.

The demo uses the tiny fixture skill library in `tests/fixtures/skills` against
the 30 built-in benchmark tasks. It is intended to show the CLI/reporting
workflow, not to represent production routing performance.

Regenerate the demo from the repository root:

```bash
skilleval index --skills-path tests/fixtures/skills --output docs/demo/skills.json
skilleval eval --index docs/demo/skills.json --tasks benchmarks/tasks --router hybrid --top-k 5 --output-dir docs/demo/benchmark-hybrid
skilleval report --runs docs/demo/benchmark-hybrid
skilleval compare --index docs/demo/skills.json --tasks benchmarks/tasks --routers keyword,hybrid,embedding --top-k 5 --output-dir docs/demo/router-comparison
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
```

Artifacts:

- `skills.json`: parsed fixture skill index.
- `benchmark-hybrid/results.jsonl`: per-task routing records and metrics.
- `benchmark-hybrid/report.md`: Markdown summary report.
- `router-comparison/comparison.md`: keyword, hybrid, and embedding router
  comparison table.
- `router-comparison/*/report.md`: per-router Markdown reports.
- `phase3b-real-embedding/comparison.md`: four-way benchmark over the generated
  20-skill library, comparing keyword, hybrid, hashing embedding, and MiniLM
  sentence-transformer routing.
- `phase3b-real-embedding/*/report.md`: per-router reports for the Phase 3B
  real embedding experiment.
- `phase3b-real-embedding/failure-analysis.md`: Phase 3C failure-mode analysis
  comparing MiniLM against the hashing embedding baseline.
- `phase4a-gated-reranker/comparison.md`: Phase 4A comparison including the
  verification-gated MiniLM reranker.
- `phase4a-gated-reranker/*/report.md`: per-router reports for the gated
  reranker experiment.
- `phase4a-gated-reranker/failure-analysis.md`: MiniLM-vs-gated failure-mode
  analysis showing which top-choice errors the reranker fixes.
- `phase4b-selective-routing/comparison.md`: Phase 4B comparison including
  selective verification-gated MiniLM routing.
- `phase4b-selective-routing/*/report.md`: per-router reports with accepted
  output metrics.
- `phase4b-selective-routing/failure-analysis.md`: failure-mode analysis
  showing selective gating removes the remaining accepted negative skill.
