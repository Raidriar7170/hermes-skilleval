# Hermes SkillEval

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-158%20passing-brightgreen.svg)](tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Benchmark](https://img.shields.io/badge/benchmark-80%20tasks%20%2F%2045%20skills-purple.svg)](benchmarks)
[![A100 Validated](https://img.shields.io/badge/A100-validated-orange.svg)](docs/phase7a.md)

**A verification-gated skill routing, dashboarding, and self-improvement harness for Hermes-style agent skills.**

面向 Hermes / Skill / Agent 工作流的离线评测系统：它能索引 `SKILL.md` 技能库，构建带负样本的 benchmark，比较 keyword、hybrid、embedding、verification-gated、cross-encoder 等路由策略，并输出可复现的指标、失败分析、自改进报告和静态 HTML dashboard。

---

## Motivation / 为什么需要这个项目

Modern agent frameworks increasingly rely on external skill libraries. The hard part is not only writing skills, but **routing the right skill at the right time while avoiding tempting negative skills**.

现代 Agent 框架越来越依赖外部 Skill 库。真正困难的不只是写 Skill，而是在相似技能很多、请求含糊、负样本诱导明显时，稳定地选中正确技能并拒绝错误技能。

| Scenario | Naive Router | Hermes SkillEval |
|---|:-:|:-:|
| Similar skills in one category | Often selects semantically close negatives | Measures negative hits and same-category confusion |
| Skill library grows over time | Hard to compare regressions | Produces comparable JSONL and Markdown reports |
| Embedding router misses edge cases | Failure reasons are opaque | Generates failure-mode analysis and candidate-vs-baseline diffs |
| Skill descriptions are weak | Manual patching is ad hoc | Proposes metadata patches and verifies before/after gains |
| Learned rerankers look promising | Hard to quantify trade-offs | Benchmarks cross-encoder ranking quality vs selective acceptance |

---

## Key Results / 核心效果

### Benchmark Scale

| Item | Value |
|---|---:|
| Benchmark tasks | 80 |
| Hermes-style benchmark skills | 45 |
| Router families | 5 |
| Test cases | 158 |
| Remote hardware validation | Single idle A100 GPU |

### Best Verified Routing Results

| Router / Setting | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Selection Rate@5 |
|---|---:|---:|---:|---:|---:|---:|
| MiniLM embedding | 0.812 | 0.956 | 0.934 | 0.930 | 0.100 | 1.000 |
| Contrastive gated MiniLM | **0.881** | 0.969 | **0.985** | 0.964 | **0.037** | 0.320 |
| Cross-encoder selective | 0.775 | 0.781 | 0.838 | 0.794 | **0.000** | 0.175 |
| Cross-encoder rank-only | **0.881** | **0.994** | **0.985** | **0.978** | 0.125 | 1.000 |

### Phase 7B Held-Out Calibration Check

| Router / Setting | Split | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Selection Rate@5 |
|---|---|---:|---:|---:|---:|---:|---:|
| Contrastive gated MiniLM | test | 0.850 | 0.950 | 1.000 | 0.959 | 0.100 | 0.360 |
| Cross-encoder rank-only | test | 0.850 | **1.000** | 1.000 | **0.987** | 0.333 | 1.000 |
| Cross-encoder calibrated strict | test | 0.850 | 0.950 | 1.000 | 0.957 | **0.033** | 0.320 |
| Cross-encoder calibrated balanced | test | 0.850 | 0.967 | 1.000 | 0.970 | 0.100 | 0.393 |

**Takeaway:** contrastive gated routing remains the strongest full-benchmark selective baseline, while Phase 7B shows that dev-split cross-encoder threshold calibration can turn the rank-only reranker into a safer acceptance policy. The strict calibrated policy cuts held-out test Negative Hit Rate from `0.333` to `0.033`; the balanced policy preserves more Recall@5 while matching the contrastive gated test negative-hit rate.

**结论:** Contrastive gated routing 仍然是最稳的全量 selective baseline；cross-encoder 排序能力更强，Phase 7B 通过 dev split 阈值校准把 held-out test 的 Negative Hit Rate 从 `0.333` 降到 `0.033`，说明它已经从“需要校准”推进到“可控接受层”的阶段。

---

## Architecture / 系统架构

```text
skills/**/SKILL.md                  benchmarks/tasks
        |                                  |
        v                                  v
  Skill parser                      Task loader
        |                                  |
        +---------------+------------------+
                        v
                   CLI evaluator
                        |
     +------------------+-------------------+------------------+
     v                  v                   v                  v
 Keyword router    Hybrid router      Embedding router    Gated router
                                           |                  |
                                           +--------+---------+
                                                    v
                                           Cross-encoder reranker
                                                    |
                                                    v
                                      metrics + JSONL traces
                                                    |
                       +----------------------------+-------------------+
                       v                                                v
             Markdown reports + static dashboard              Failure analysis
                       |                                                |
                       +----------------------------+-------------------+
                                                    v
                                      Skill metadata improvement loop
```

Core design principles:

- **Offline-first:** default keyword, hybrid, and hashing embedding workflows run without network access, Hermes Agent, or LLM API keys.
- **Verifier-aware:** reports track both gold skill recall and negative skill hits, so a router cannot hide unsafe selections behind high recall.
- **Failure-driven:** the harness turns missed gold skills and negative hits into concrete metadata patch proposals.
- **Extensible:** optional `sentence-transformers` and cross-encoder backends plug into the same evaluation surface.

---

## Project Structure / 项目结构

```text
hermes-skilleval/
├── benchmarks/
│   ├── skills/                         # 45 generated Hermes-style skills
│   └── tasks/                          # 80 labeled routing tasks
├── docs/
│   ├── demo/                           # committed benchmark outputs
│   ├── phase2.md ... phase7b.md        # implementation and experiment notes
│   └── resume.md                       # resume-ready project framing
├── scripts/
│   ├── generate_benchmark_skills.py    # reproducible skill corpus generator
│   └── generate_benchmark_tasks.py     # reproducible task corpus generator
├── src/hermes_skilleval/
│   ├── cli.py                          # index, eval, compare, analyze, improve
│   ├── calibration.py                  # cross-encoder acceptance thresholds
│   ├── metrics.py                      # Recall, Precision, MRR, NDCG, negatives
│   ├── failure_analysis.py             # failure-mode summaries
│   ├── self_improvement.py             # metadata patch proposals
│   └── routers/
│       ├── keyword.py                  # lexical baseline
│       ├── hybrid.py                   # category + lexical + explicit id boosts
│       ├── embedding.py                # hashing and sentence-transformers retrievers
│       ├── gated.py                    # verification-gated reranker
│       ├── verification.py             # shared selective evidence logic
│       └── cross_encoder.py            # pretrained pairwise reranker
├── tests/                              # 158 pytest cases
├── pyproject.toml
└── README.md
```

---

## Quick Start / 快速开始

### Installation

```bash
git clone https://github.com/Raidriar7170/hermes-skilleval.git
cd hermes-skilleval

python -m venv .venv
source .venv/bin/activate

python -m pip install -e ".[dev]"
```

Install optional neural routing backends:

```bash
python -m pip install -e ".[dev,embedding]"
```

### 1. Index a Hermes-style Skill Library

```bash
skilleval index \
  --skills-path benchmarks/skills \
  --output runs/skills.json
```

### 2. Run a Router Evaluation

```bash
skilleval eval \
  --index runs/skills.json \
  --tasks benchmarks/tasks \
  --router hybrid \
  --top-k 5 \
  --output-dir runs/hybrid
```

### 3. Compare Multiple Routers

```bash
skilleval compare \
  --index runs/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding-hashing=embedding:hashing \
  --top-k 5 \
  --output-dir runs/comparison
```

### 4. Analyze Failures

```bash
skilleval analyze-failures \
  --runs runs/comparison \
  --baseline hybrid \
  --candidate embedding-hashing \
  --output runs/comparison/failure-analysis.md
```

### 5. Run the Cross-Encoder Reranker

```bash
skilleval eval \
  --index runs/skills.json \
  --tasks benchmarks/tasks \
  --router cross-encoder \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache runs/embeddings/all-MiniLM-L6-v2.json \
  --cross-encoder-model cross-encoder/ms-marco-MiniLM-L-6-v2 \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir runs/cross-encoder
```

### 6. Calibrate Cross-Encoder Acceptance

```bash
skilleval calibrate-cross-encoder \
  --results docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only/results.jsonl \
  --output runs/cross-encoder-calibration.json \
  --calibrated-output runs/cross-encoder-calibrated-test/results.jsonl \
  --fit-split dev \
  --apply-split test \
  --max-negative-hit-rate 0.05 \
  --max-selection-rate-at-5 0.3
```

### Static Dashboard

```bash
skilleval dashboard \
  --runs docs/demo/phase7b-cross-encoder-calibration \
  --output docs/demo/phase8-static-dashboard/dashboard.html
```

The generated file is self-contained and can be opened directly in a browser for
interactive run filtering, failure inspection, score ranking, and raw JSON audit:
[`Live dashboard`](https://raidriar7170.github.io/hermes-skilleval/docs/demo/phase8-static-dashboard/dashboard.html).
The committed source artifact is also available at
[`docs/demo/phase8-static-dashboard/dashboard.html`](docs/demo/phase8-static-dashboard/dashboard.html).

### 7. Run Tests

```bash
pytest -q
```

Expected:

```text
158 passed
```

---

## Experiment Timeline / 实验演进

| Phase | Feature | Artifact |
|---|---|---|
| Phase 2 | Router comparison baseline | [`docs/phase2.md`](docs/phase2.md) |
| Phase 3A | Real embedding backend | [`docs/phase3a.md`](docs/phase3a.md) |
| Phase 3B | MiniLM embedding benchmark | [`docs/demo/phase3b-real-embedding/comparison.md`](docs/demo/phase3b-real-embedding/comparison.md) |
| Phase 3C | Failure analysis | [`docs/demo/phase3b-real-embedding/failure-analysis.md`](docs/demo/phase3b-real-embedding/failure-analysis.md) |
| Phase 4A | Verification-gated reranking | [`docs/demo/phase4a-gated-reranker/comparison.md`](docs/demo/phase4a-gated-reranker/comparison.md) |
| Phase 4B | Selective routing | [`docs/demo/phase4b-selective-routing/comparison.md`](docs/demo/phase4b-selective-routing/comparison.md) |
| Phase 5 | Failure-driven skill improvement | [`docs/demo/phase5-self-improvement/acceptance.md`](docs/demo/phase5-self-improvement/acceptance.md) |
| Phase 6A | 80-task robustness benchmark | [`docs/demo/phase6a-robustness/comparison.md`](docs/demo/phase6a-robustness/comparison.md) |
| Phase 6B | Contrastive selective gating | [`docs/demo/phase6b-contrastive-gating/comparison.md`](docs/demo/phase6b-contrastive-gating/comparison.md) |
| Phase 7A | A100 cross-encoder reranker | [`docs/phase7a.md`](docs/phase7a.md) |
| Phase 7B | Cross-encoder acceptance calibration | [`docs/phase7b.md`](docs/phase7b.md) |
| Phase 8 | Static failure inspection dashboard | [`docs/phase8.md`](docs/phase8.md) |

---

## Technical Details / 技术细节

### 1. Skill Parsing and Indexing

`skill_parser.py` discovers `skills/**/SKILL.md`, reads YAML frontmatter, infers categories from paths, extracts trigger terms, estimates token counts, and writes a portable JSON skill index.

### 2. Router Families

| Router | Role |
|---|---|
| `keyword` | Deterministic lexical baseline |
| `hybrid` | Lexical retrieval with category and explicit skill-id boosts |
| `embedding` | Hashing baseline or real `sentence-transformers` embedding retriever |
| `gated` | Verification-gated reranker with confidence and contrastive selective logic |
| `cross-encoder` | Learned pairwise reranker over embedding candidates |

### 3. Verification and Negative Controls

The benchmark includes both `gold_skills` and `negative_skills`. Reports track:

- `Recall@1`, `Recall@3`, `Recall@5`
- `Precision@5`
- `MRR`
- `NDCG@5`
- `Negative Hit Rate`
- selective accepted-output metrics
- per-task score traces and latency

### 4. Self-Improvement Harness

`improve-skills` proposes deterministic metadata patches from observed misses and negative hits. `judge-improvement` compares before/after runs and writes an acceptance report, turning routing failures into measurable skill-library edits.

### 5. A100 Deployment

Phase 7A staged MiniLM embedding and MS MARCO MiniLM cross-encoder models under the user-owned remote path, selected an idle A100 with `CUDA_VISIBLE_DEVICES=3`, and validated learned reranking on the full 80-task benchmark. Phase 7B then fitted dev-split cross-encoder acceptance thresholds and evaluated the frozen policies on the held-out test split. See [`docs/phase7a.md`](docs/phase7a.md) and [`docs/phase7b.md`](docs/phase7b.md).

---

## Tech Stack / 技术栈

| Component | Technology | Purpose |
|---|---|---|
| Core Runtime | Python 3.11 | CLI and benchmark harness |
| CLI | argparse | `skilleval` command suite |
| Data Models | dataclasses + PyYAML | Skill and task schemas |
| Retrieval | keyword, hybrid, hashing embeddings | Offline deterministic baselines |
| Neural Retrieval | sentence-transformers MiniLM | Real embedding router |
| Reranking | verification gate + cross-encoder | Selective and learned ranking |
| Reports | JSONL + Markdown + static HTML dashboard | Reproducible experiment artifacts |
| Testing | pytest | 158 unit and smoke tests |
| Hardware | Mac + A100 dev machine | Local development and remote model validation |

---

## Roadmap

- [x] Hermes-style `SKILL.md` parser and skill indexer
- [x] 80-task / 45-skill benchmark corpus with negative labels
- [x] Keyword, hybrid, hashing embedding, and real embedding routers
- [x] Verification-gated reranker and selective acceptance
- [x] Failure analysis reports and self-improvement acceptance gate
- [x] Contrastive gating for same-category ambiguous negatives
- [x] Cross-encoder reranker deployed on a single idle A100
- [x] Calibrated cross-encoder acceptance thresholds
- [x] Web dashboard for interactive failure inspection
- [ ] Learned skill metadata patch ranking
- [ ] Fine-tuned embedding router for domain-specific skill libraries

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Project Summary / 项目总结

> **For recruiters and hiring managers:**
>
> Hermes SkillEval demonstrates end-to-end agent evaluation engineering:
>
> - **Agent Systems:** designed a benchmark harness for Hermes-style skill routing, including parsing, indexing, routing, reporting, and failure-driven improvement.
> - **Retrieval and Ranking:** implemented keyword, hybrid, embedding, verification-gated, contrastive, and cross-encoder routing strategies.
> - **ML Evaluation:** built an 80-task benchmark with negative controls and ranking metrics such as Recall@k, MRR, NDCG, and Negative Hit Rate.
> - **Infrastructure:** validated neural reranking on shared A100 infrastructure while selecting idle GPUs and preserving user-owned storage paths.
> - **Engineering Quality:** shipped a typed Python CLI with 158 passing tests, reproducible benchmark artifacts, a static inspection dashboard, and resume-ready experiment documentation.
>
> **面向招聘者:**
>
> 这个项目展示了 Agent Skill 路由评测、检索排序、失败分析、自改进闭环和远端 GPU 部署能力。它不是一个单纯 demo，而是从 benchmark 构建、router 设计、metric 评估、cross-encoder 验证到简历材料整理的一套完整工程闭环。
