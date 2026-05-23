# Phase 6A: Robustness Benchmark Pack

Phase 6A expands Hermes SkillEval from a small routing demo into a first
robustness benchmark pack. The goal is not to add new router behavior; it is to
make the evaluation corpus large and varied enough that future routing changes
have a more credible target.

## What Changed

- Expanded `benchmarks/tasks` from 30 to 80 tasks.
- Expanded `benchmarks/skills` from 20 to 45 generated Hermes-style skills.
- Added optional task metadata:
  - `split`: `dev` or `test`
  - `robustness_tags`: challenge labels such as `agent-routing`,
    `ambiguous-skill-pair`, `heldout-generalization`, `asr`, and
    `negative-suppression`
- Kept legacy task loading backward compatible by defaulting missing metadata
  to `split: dev` and `robustness_tags: ["legacy"]`.
- Added `split` and `robustness_tags` to JSONL result records so downstream
  diagnostics can slice benchmark runs by robustness group.

## Corpus Shape

| Item | Count |
| --- | ---: |
| Tasks | 80 |
| Skills | 45 |
| Dev tasks | 50 |
| Test tasks | 30 |

The added tasks cover agent routing, verifier-gated routing, self-improvement
harnesses, retrieval, evaluation, ASR and multimodal workflows, model-serving
infrastructure, and deliberately ambiguous same-category skill pairs.

## Benchmark Result

The committed Phase 6A run is in
[`docs/demo/phase6a-robustness`](demo/phase6a-robustness).

| Router | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Selection Rate@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-hashing | 0.619 | 0.881 | 0.776 | 0.785 | 0.075 | 1.000 |
| embedding-minilm | 0.812 | 0.956 | 0.934 | 0.930 | 0.100 | 1.000 |
| gated-minilm-selective | 0.881 | 0.981 | 0.985 | 0.974 | 0.113 | 0.715 |
| hybrid | 0.869 | 0.994 | 0.978 | 0.974 | 0.138 | 1.000 |
| keyword | 0.869 | 0.988 | 0.978 | 0.969 | 0.138 | 1.000 |

The expanded benchmark is intentionally harder than the earlier 30-task demo.
MiniLM remains stronger than the dependency-free hashing embedding baseline,
and selective gated routing improves top-choice accuracy, MRR, and NDCG@5.
The new held-out ambiguous tasks expose a real remaining weakness: same-category
negative skills are still hard to suppress.

## Split Diagnostics

| Router | Split | Tasks | Recall@1 | Negative Hit Rate | Selection Rate@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| embedding-minilm | dev | 50 | 0.840 | 0.000 | 1.000 |
| embedding-minilm | test | 30 | 0.767 | 0.267 | 1.000 |
| gated-minilm-selective | dev | 50 | 0.900 | 0.000 | 0.700 |
| gated-minilm-selective | test | 30 | 0.850 | 0.300 | 0.740 |

This gives the project a useful next-step target: improve robust negative
suppression on held-out same-category skill pairs without giving up Recall@5.

## Reproduce

```bash
python scripts/generate_benchmark_tasks.py
python scripts/generate_benchmark_skills.py
skilleval index \
  --skills-path benchmarks/skills \
  --output docs/demo/phase6a-robustness/skills.json
skilleval compare \
  --index docs/demo/phase6a-robustness/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding-hashing=embedding:hashing,embedding-minilm=embedding:sentence-transformers,gated-minilm-selective=gated:sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase6a-minilm-cache.json \
  --selective \
  --min-confidence 0.5 \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir docs/demo/phase6a-robustness
skilleval analyze-failures \
  --runs docs/demo/phase6a-robustness \
  --baseline embedding-minilm \
  --candidate gated-minilm-selective \
  --output docs/demo/phase6a-robustness/failure-analysis.md
```

## Hardware Notes

Phase 6A still runs on a local Mac because it uses a compact MiniLM embedding
model and caches skill vectors. The 8xA100 development machine becomes useful
for future phases such as embedding fine-tuning, cross-encoder reranking,
LLM-judge sweeps, or larger benchmark generation.
