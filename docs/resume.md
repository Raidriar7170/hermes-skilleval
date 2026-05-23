# Hermes SkillEval Resume Notes

## One-Line Pitch

Built an offline evaluation harness for Hermes-style agent skill routing,
turning Markdown skill libraries into measurable retrieval benchmarks with
validated CLI runs and Markdown reports.

## Resume Bullets

- Built `Hermes SkillEval`, a Python CLI harness for benchmarking agent skill
  routing over Hermes-style `SKILL.md` libraries, including skill parsing,
  benchmark loading, keyword/hybrid/embedding routers, and JSONL plus Markdown
  reporting.
- Implemented ranking metrics for agent skill selection, including Recall@K,
  Precision@5, MRR, NDCG@5, Negative Hit Rate, latency tracking, top-skill
  analysis, and failure-case reporting over a 30-task benchmark corpus.
- Added a dependency-free hashing embedding router and multi-router comparison
  command to benchmark keyword, hybrid, and embedding strategies from one CLI
  run.
- Hardened the evaluation pipeline with schema validation, deterministic
  benchmark generation, clean CLI error handling, Markdown table escaping, and
  88 pytest tests covering parser, loader, router, metric, report, and CLI edge
  cases.
- Designed the system as an offline MVP that runs locally on a Mac while leaving
  clear extension points for embedding retrieval, LLM reranking, verifier-gated
  routing, and self-improving skill patches on larger GPU infrastructure.

## Short Resume Version

Built a Python evaluation harness for Hermes-style agent skill routing, with
Markdown skill indexing, 30 labeled benchmark tasks, keyword/hybrid/embedding
routers, Recall@K/MRR/NDCG/negative-hit metrics, CLI comparison reports, and
88-test validation.

## Interview Talking Points

- Motivation: agent systems often add many skills, but routing quality is hard
  to measure. This project turns skill selection into a repeatable retrieval
  benchmark.
- System design: skill parser and task loader feed a router interface; routers
  emit scored selections; metrics and report generation produce JSONL and
  Markdown artifacts for analysis.
- Phase 2: a local hashing embedding router gives a no-download semantic-ish
  retrieval baseline, and `skilleval compare` writes side-by-side router
  metrics for experiment tracking.
- Engineering depth: the MVP handles malformed YAML/frontmatter, invalid task
  labels, nonpositive top-k, duplicate selected skills, malformed JSONL,
  Markdown escaping, and repeatable benchmark generation.
- Agent relevance: the harness can be extended from offline lexical routing to
  embedding retrieval, LLM reranking, verification-gated execution, and
  self-improvement loops.
- Hardware story: the current MVP runs on a local Mac. A remote 8xA100 machine
  becomes useful for future embedding index experiments, LLM reranker training,
  large-scale benchmark sweeps, and verifier/self-improvement runs.

## Suggested GitHub Description

Offline CLI benchmark harness for evaluating Hermes-style agent skill routing
with labeled tasks, ranking metrics, failure reports, and reproducible benchmark
generation.

## Future Extension Bullets

- Replace the local hashing embedding baseline with cached sentence-transformer
  indexes and compare neural retrieval against keyword/hybrid baselines.
- Add verifier-gated routing where selected skills must pass executable or
  rubric-based checks before being counted as successful.
- Add self-improvement harness that proposes skill metadata patches from failure
  cases and re-runs the benchmark to measure improvement.
- Add a lightweight dashboard for comparing router runs across benchmark
  versions.
