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
  analysis, and failure-case reporting over an 80-task benchmark corpus.
- Added a dependency-free hashing embedding router and multi-router comparison
  command to benchmark keyword, hybrid, and embedding strategies from one CLI
  run.
- Added an optional `sentence-transformers` embedding backend with configurable
  model names and a JSON skill-vector cache, while keeping the hashing backend
  as the default Mac-friendly path.
- Ran a real MiniLM embedding benchmark on a generated 20-skill Hermes-style
  library, improving embedding Recall@1 from 0.717 to 0.867 and MRR from 0.873
  to 0.967 versus the hashing embedding baseline.
- Added failure-mode analysis for router experiments, surfacing top-1 misses,
  missing gold skills, negative hits, and MiniLM-vs-hashing trade-offs; reduced
  embedding-router failure cases from 11 to 3 in the Phase 3B benchmark.
- Built a verification-gated reranker on top of MiniLM retrieval, improving
  embedding Recall@1 from 0.867 to 0.933 and eliminating top-choice misses
  without using benchmark gold or negative labels at routing time.
- Added selective confidence gating so the router can return fewer skills
  instead of padding low-confidence results, reducing accepted negative-skill
  rate from 0.033 to 0.000 while preserving Recall@5 at 1.000.
- Built a failure-driven self-improvement harness that proposes metadata
  patches from routing failures, writes a patched skill index, reruns
  evaluation, and accepts the patch set only when Recall@1/MRR/NDCG improve
  without negative-hit regression.
- Expanded the benchmark into an 80-task, 45-skill robustness pack with
  dev/test split metadata and challenge tags, then measured selective gated
  MiniLM at 0.881 Recall@1, 0.981 Recall@5, and 0.985 MRR.
- Added contrastive selective gating for ambiguous same-category skills,
  reducing full-benchmark Negative Hit Rate from 0.113 to 0.037 and held-out
  ambiguous-pair Negative Hit Rate from 0.900 to 0.300 while preserving
  Recall@1 at 0.881 and Recall@5 at 0.969.
- Added a pretrained cross-encoder reranker deployed on a single idle A100,
  improving rank-only Recall@5 from 0.969 to 0.994 and NDCG@5 from 0.964 to
  0.978 versus contrastive gating, while revealing the precision/recall trade
  off of applying selective acceptance directly to cross-encoder logits.
- Added a dev-split calibrated cross-encoder acceptance layer, reducing held-out
  test Negative Hit Rate from 0.333 to 0.033 in strict mode while preserving
  Recall@5 at 0.950, and documenting a balanced 0.967 Recall@5 / 0.100
  Negative Hit Rate trade-off.
- Phase 8: a static self-contained dashboard makes committed benchmark runs
  inspectable in a browser with filters, sortable task rows, failure tags, score
  rankings, and raw JSON audit views.
- Hardened the evaluation pipeline with schema validation, deterministic
  benchmark generation, clean CLI error handling, Markdown table escaping, and
  145 pytest tests covering parser, loader, router, metric, report, and CLI
  edge cases.
- Designed the system as an offline MVP that runs locally on a Mac while
  supporting controlled single-GPU experiments on shared A100 infrastructure.

## Short Resume Version

Built a Python evaluation harness for Hermes-style agent skill routing, with
Markdown skill indexing, an 80-task/45-skill robustness benchmark,
keyword/hybrid/embedding routers, optional `sentence-transformers` retrieval,
verification-gated reranking, pretrained cross-encoder reranking, calibrated
cross-encoder acceptance, selective confidence gating, Recall@K, MRR, NDCG,
negative-hit metrics, failure-driven metadata patching, CLI comparison/failure
reports, static dashboard, and 145-test validation.

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
- Phase 3A: the embedding router can switch from hashing to a real
  `sentence-transformers` model, cache skill vectors on disk, and keep query
  encoding live for each task.
- Phase 3B: a generated 20-skill benchmark library covers all 30 task labels,
  and the real MiniLM run reaches Recall@5 1.000 and MRR 0.967 with warm
  skill-vector caching on a local Mac CPU.
- Phase 3C: failure analysis shows MiniLM cuts embedding-router failures from
  11 to 3 versus hashing, with remaining errors concentrated in top-1 ambiguity
  and negative-skill suppression.
- Phase 4A: a verification-gated reranker uses category agreement and
  prompt-skill lexical evidence to resolve MiniLM top-choice ambiguity,
  improving Recall@1 from 0.867 to 0.933 and reducing top-choice failures from
  2 to 0.
- Phase 4B: selective confidence gating suppresses weak cross-category filler
  skills, dropping accepted negative-skill rate from 0.033 to 0.000 while
  keeping benchmark coverage at 1.000.
- Phase 5: failure-driven metadata patching improves MiniLM Recall@1 from
  0.867 to 0.933 and MRR from 0.967 to 1.000, with an acceptance gate that
  rejects metric regressions.
- Phase 6A: the robustness pack expands the benchmark from 30 to 80 tasks and
  20 to 45 skills, adds dev/test splits plus challenge tags, and surfaces
  held-out ambiguous-pair weaknesses for future reranking work.
- Phase 6B: contrastive selective gating reduces same-category negative hits
  by comparing each accepted candidate's prompt evidence against the strongest
  accepted skill, cutting full Negative Hit Rate to 0.037.
- Phase 7A: a pretrained MS MARCO MiniLM cross-encoder reranker improves
  rank-only Recall@5 to 0.994 and NDCG@5 to 0.978 on the 80-task benchmark,
  but needs a calibrated acceptance layer because rank-only reranking raises
  Negative Hit Rate to 0.125 and direct selective gating is too conservative.
- Phase 7B: a dev-split calibrated threshold layer turns the rank-only
  cross-encoder into an acceptance policy; on the held-out test split, strict
  calibration lowers Negative Hit Rate from 0.333 to 0.033, while balanced
  calibration keeps Recall@5 at 0.967 with Negative Hit Rate at 0.100.
- Engineering depth: the MVP handles malformed YAML/frontmatter, invalid task
  labels, nonpositive top-k, duplicate selected skills, malformed JSONL,
  Markdown escaping, and repeatable benchmark generation.
- Agent relevance: the harness now covers offline lexical routing, embedding
  retrieval, verifier-gated reranking, cross-encoder reranking, selective and
  contrastive acceptance, and failure-driven self-improvement loops.
- Hardware story: the main harness runs on a local Mac, while Phase 7A staged
  local model snapshots under `/mnt/data/minghongsun`, selected an idle A100
  with `nvidia-smi`, and ran the benchmark with `CUDA_VISIBLE_DEVICES=3`
  without killing or resetting any existing GPU process.

## Suggested GitHub Description

Offline CLI benchmark harness for evaluating Hermes-style agent skill routing
with labeled tasks, ranking metrics, failure reports, and reproducible benchmark
generation.

## Future Extension Bullets

- Add Platt scaling or isotonic probability calibration on top of the current
  cross-encoder threshold layer.
- Extend failure-driven patching from generated skill indexes to source
  `SKILL.md` editing with human review.
- Fine-tune or distill the embedding model on benchmark failures and measure
  retrieval gains against the hashing and off-the-shelf baselines.
- Add variable-k abstention where low-confidence selected skills are suppressed
  instead of forcing exactly five results.
- Add an LLM-assisted patch proposer and compare it with the deterministic
  trigger-term proposer.
- Add a lightweight dashboard for comparing router runs across benchmark
  versions.
