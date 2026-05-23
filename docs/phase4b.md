# Phase 4B: Selective Verification-Gated Routing

Phase 4B adds selective output to the verification-gated router. The router can
now return fewer than `top_k` skills when verifier confidence is low, instead
of forcing weak cross-category filler candidates into the result list.

## What Changed

- Added selective mode to `VerificationGatedRouter`.
- Added CLI flags:
  - `--selective`
  - `--min-confidence`
- Added selective metrics to every JSONL result:
  - `accepted_count`
  - `coverage`
  - `selection_rate_at_5`
  - `abstention_rate`
  - `accepted_recall_at_5`
  - `negative_accepted_rate`
- Extended Markdown reports and comparison tables to show the selective
  metrics.
- Committed a Phase 4B benchmark under
  `docs/demo/phase4b-selective-routing`.

## Results

Warm-cache MiniLM comparison over 30 tasks and the generated 20-skill library:

| Router | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Coverage | Selection Rate@5 | Negative Accepted Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-minilm | 0.867 | 1.000 | 0.967 | 0.973 | 0.033 | 1.000 | 1.000 | 0.033 |
| gated-minilm-selective | 0.933 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 | 0.600 | 0.000 |
| hybrid | 0.933 | 1.000 | 1.000 | 1.000 | 0.033 | 1.000 | 1.000 | 0.033 |
| keyword | 0.933 | 1.000 | 1.000 | 1.000 | 0.033 | 1.000 | 1.000 | 0.033 |

Selective gating fixes all three MiniLM failure cases surfaced by Phase 3C:

- `coding-debugging-002`: removes the negative `ascii-art` candidate by
  returning only `systematic-debugging` and `test-driven-development`.
- `coding-debugging-009`: promotes `test-driven-development` above
  `systematic-debugging`.
- `data-mlops-006`: promotes `python-data-analysis` above broader
  `data-analysis`.

## Interpretation

The main trade-off is intentional: the selective router returns fewer skills
on average. In this run, `selection_rate_at_5` is `0.600`, meaning the router
accepts about three skills per task while preserving full Recall@5 and
eliminating accepted negative skills.

This is closer to production agent routing than fixed top-k output. A real
agent should prefer a smaller high-confidence skill set over a padded list that
includes unrelated tools.

## Reproduce

```bash
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
```

```bash
skilleval analyze-failures \
  --runs docs/demo/phase4b-selective-routing \
  --baseline embedding-minilm \
  --candidate gated-minilm-selective \
  --output docs/demo/phase4b-selective-routing/failure-analysis.md
```
