# Hermes SkillEval

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Validate](https://github.com/Raidriar7170/hermes-skilleval/actions/workflows/validate.yml/badge.svg)](https://github.com/Raidriar7170/hermes-skilleval/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Benchmark](https://img.shields.io/badge/benchmark-80%20tasks%20%2F%2045%20skills-purple.svg)](benchmarks)
[![A100 Validated](https://img.shields.io/badge/A100-validated-orange.svg)](docs/phase7a.md)

**A reproducible evaluation and release-gate harness for Hermes-style agent skill routing.**

面向 Hermes / Skill / Agent 工作流的离线评测系统：它能索引 `SKILL.md`
技能库，构建带负样本的 benchmark，比较 keyword、hybrid、embedding、
verification-gated、cross-encoder 等路由策略，并输出可复现的指标、
失败分析、自改进报告、静态 HTML dashboard 和发布门禁证据。

---

## For Recruiters / 3-minute review path

**One-line positioning:** Hermes SkillEval turns agent skill routing into a
reproducible offline evaluation and release-gate workflow: it measures whether
a router selects the right skill, avoids tempting negative skills, and refuses
to promote regressions as defaults.

**Core capabilities:**

- Builds an 80-task / 45-skill Hermes-style benchmark with gold and negative
  skill labels.
- Compares keyword, hybrid, embedding, verification-gated, contrastive, and
  cross-encoder routers with Recall@K, MRR, NDCG, and Negative Hit Rate.
- Converts blind-validation regressions into an explicit `KEEP_BASELINE`
  release decision and a CI-reproducible release manifest.

**High-signal evidence:**

- [`docs/demo/phase16-blind-validation/comparison.md`](docs/demo/phase16-blind-validation/comparison.md)
  shows the blind validation regression that blocked the fine-tuned router.
- [`docs/demo/phase17-calibrated-release-selector/release-decision.md`](docs/demo/phase17-calibrated-release-selector/release-decision.md)
  records `KEEP_BASELINE` and `approved_for_default: False`.
- [`docs/demo/phase18-ci-release-reproducibility/release-manifest.md`](docs/demo/phase18-ci-release-reproducibility/release-manifest.md)
  records the reproducible release check and artifact hashes.

For the full evidence chain, start from
[`docs/release-handoff.md`](docs/release-handoff.md).
For concrete reviewer examples of blocked regressions and diagnostic risks, use
[`docs/failure-gallery.md`](docs/failure-gallery.md).
For interview prep, use
[`docs/interview-project-overview.html`](docs/interview-project-overview.html)
and [`docs/resume.md`](docs/resume.md).

**Minimal reproduction command:**

```bash
PYTHONPATH=src python -m hermes_skilleval.cli release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
```

---

## Motivation / 为什么需要这个项目

Modern agent frameworks increasingly rely on external skill libraries. The hard
part is not only writing skills, but **routing the right skill at the right time
while avoiding tempting negative skills**.

现代 Agent 框架越来越依赖外部 Skill 库。真正困难的不只是写 Skill，
而是在相似技能很多、请求含糊、负样本诱导明显时，稳定地选中正确技能
并拒绝错误技能。

| Scenario | Naive Router | Hermes SkillEval |
|---|:-:|:-:|
| Similar skills in one category | Often selects semantically close negatives | Measures negative hits and same-category confusion |
| Skill library grows over time | Hard to compare regressions | Produces comparable JSONL and Markdown reports |
| Embedding router misses edge cases | Failure reasons are opaque | Generates failure-mode analysis and candidate-vs-baseline diffs |
| Skill descriptions are weak | Manual patching is ad hoc | Proposes metadata patches and verifies before/after gains |
| Learned rerankers look promising | Hard to quantify trade-offs | Benchmarks cross-encoder ranking quality vs selective acceptance |

---

## Key Results / 核心效果

### Current Release Evidence

The latest release reading comes from Phase 16-18, not from the earlier Phase 8
dashboard. Phase 16 blind validation found that the fine-tuned embedding router
preserved Recall@5 but worsened ranking and negative-skill behavior. Phase 17
therefore keeps `baseline-minilm` as the default, and Phase 18 makes that
release gate reproducible.

| Evidence | Result | Link |
|---|---|---|
| Phase 16 blind validation | `REVIEW_REQUIRED`; two regressions and worse negative-hit behavior | [`docs`](docs/phase16.md), [`comparison.md`](docs/demo/phase16-blind-validation/comparison.md), [`dashboard.html`](docs/demo/phase16-blind-validation/dashboard.html) |
| Phase 17 release selector | `KEEP_BASELINE`; `finetuned-embedding` not approved as default | [`docs`](docs/phase17.md), [`release-decision.md`](docs/demo/phase17-calibrated-release-selector/release-decision.md) |
| Phase 18 reproducibility pack | `PASS`; release decision remains `KEEP_BASELINE` | [`docs`](docs/phase18.md), [`release-manifest.md`](docs/demo/phase18-ci-release-reproducibility/release-manifest.md) |

### Example Failure Caught by the Release Gate

Phase 16 includes a concrete blind-validation case that explains why negative
controls matter:

| Field | Value |
|---|---|
| Blind task | `blind-claude-mcp-routing` |
| Gold skill | `mcp-tool-routing` |
| Tempting negative skill | `slash-command-workflow` |
| Baseline top-5 | Kept the gold skill and did not select the negative skill |
| Fine-tuned candidate top-5 | Kept the gold skill but newly selected the negative skill |
| Guard flags | `negative_hit_rate_increased`, `negative_accepted_rate_increased`, `new_negative_skill_selected` |
| Release result | Phase 17 records `KEEP_BASELINE`; Phase 18 reproduces the decision |

This is the core project story: the release gate rejected a plausible learned
router because it introduced a new negative-skill regression despite unchanged
Recall@5. The exact diff is committed in
[`route-diffs.jsonl`](docs/demo/phase16-blind-validation/route-diffs.jsonl).

### Live Dashboard

Explore the committed Phase 8 dashboard:
[`Open Hermes SkillEval Dashboard`](https://raidriar7170.github.io/hermes-skilleval/docs/demo/phase8-static-dashboard/dashboard.html).

The dashboard supports run filtering, failure inspection, score ranking, and
raw JSON audit over the Phase 7B comparison artifacts. It remains useful for
inspection, while the current release evidence is the Phase 16-18 blind
validation and release-gate chain above. The committed HTML artifact is also
available at
[`docs/demo/phase8-static-dashboard/dashboard.html`](docs/demo/phase8-static-dashboard/dashboard.html).

Preview generated from the committed Phase 8 dashboard payload:

![Dashboard screenshot](docs/assets/dashboard-screenshot.png)

### Benchmark Scale

| Item | Value |
|---|---:|
| Benchmark tasks | 80 |
| Hermes-style benchmark skills | 45 |
| Router families | 5 |
| Test cases | 392 |
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

**Takeaway:** contrastive gated routing remains the strongest full-benchmark
selective baseline, while Phase 7B shows that dev-split cross-encoder threshold
calibration can turn the rank-only reranker into a safer acceptance policy.
The strict calibrated policy cuts held-out test Negative Hit Rate from `0.333`
to `0.033`; the balanced policy preserves more Recall@5 while matching the
contrastive gated test negative-hit rate.

**结论:** Contrastive gated routing 仍然是最稳的全量 selective baseline；
cross-encoder 排序能力更强，Phase 7B 通过 dev split 阈值校准把 held-out
test 的 Negative Hit Rate 从 `0.333` 降到 `0.033`，说明它已经从
“需要校准”推进到“可控接受层”的阶段。

---

## Limitations / Boundaries

- This is a self-built Hermes-style benchmark, not a standard public benchmark
  or model-leadership claim.
- The strongest evidence is the evaluation, artifact, and release-gate workflow,
  not absolute model superiority.
- The fine-tuned router is not promoted as the default; the current release
  decision remains `KEEP_BASELINE`.
- Model checkpoints, embedding caches, and private remote-machine details are
  intentionally not committed.
- Future work: add third-party skill libraries, external blind task packs, and
  more cross-domain reviewer traces.

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

- **Offline-first:** default keyword, hybrid, and hashing embedding workflows
  run without network access, Hermes Agent, or LLM API keys.
- **Verifier-aware:** reports track both gold skill recall and negative skill
  hits, so a router cannot hide unsafe selections behind high recall.
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
│   ├── phase2.md ... phase18.md        # implementation and experiment notes
│   └── resume.md                       # resume-ready project framing
├── scripts/
│   ├── generate_benchmark_skills.py    # reproducible skill corpus generator
│   └── generate_benchmark_tasks.py     # reproducible task corpus generator
├── src/hermes_skilleval/
│   ├── cli.py                          # index, eval, compare, analyze, improve, simulate
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
├── tests/                              # 392 pytest cases
├── pyproject.toml
└── README.md
```

---

## Quick Start / 快速开始

Clone and install the development extras:

```bash
git clone https://github.com/Raidriar7170/hermes-skilleval.git
cd hermes-skilleval
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the main local checks:

```bash
pytest -q

skilleval release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
```

Expected: `392 passed` and
`Release reproducibility PASS:
docs/demo/phase18-ci-release-reproducibility/release-manifest.json`.

For full CLI usage, see [`docs/usage.md`](docs/usage.md).
For reviewer navigation across release, diagnostic, external validation, CI,
OpenSpec, and Human Brief evidence, see
[`docs/evidence-map.md`](docs/evidence-map.md). It is a navigation layer, not a
second source of truth, and not release approval.

---

## Diagnostic Onboarding / 零标签诊断入口

For the committed scan -> lint -> inspect -> route -> dashboard demo evidence
pack, see
[`docs/demo/diagnostic-onboarding/`](docs/demo/diagnostic-onboarding/).
The demo also includes `ci-gate-report.json`, `ci-gate-report.md`,
`pr-review-packet.json`, and `pr-review-packet.md`. The CI gate report is
produced by `skilleval diagnostic-ci-gate` as artifact-based CI validation over
already generated diagnostic artifacts; the PR review packet is a local
reviewer-facing summary generated from that gate report. Use
`skilleval diagnostic-artifact-drift-check` to compare committed and
regenerated diagnostic demo artifacts while ignoring approved volatile fields
such as `generated_at`. The GitHub Actions validate workflow now regenerates
the diagnostic onboarding demo into `$RUNNER_TEMP` and runs the same drift
check with JSON and Markdown reports kept outside the repository checkout.

Boundary: this is not GitHub API integration, not a Marketplace Action, not a
PR annotation system, not SaaS, not a runtime MCP router, and not a headline
performance claim. Full regeneration, drift-check, gate, and review packet
commands live in [`docs/usage.md`](docs/usage.md).

### External Skill Library Validation Pack

[`docs/demo/external-skill-library-validation/`](docs/demo/external-skill-library-validation/)
extends the diagnostic evidence path to external-style source shapes. It has
two committed source tracks: Markdown `SKILL.md` folders under
`source/markdown-skills/` and an MCP-style tool schema at
`source/mcp-tool-schema/tools.json`. Each track includes regenerated scan,
lint, inspect, route, dashboard, CI gate, and local PR review packet artifacts.

Local simulation writes regenerated artifacts outside the checkout and compares
them back to the committed pack. The snippet below is the drift-check closeout;
the full regeneration commands live in the pack README:

```bash
ROOT=docs/demo/external-skill-library-validation
TMP_ROOT="${TMPDIR:-/tmp}/external-skill-library-validation"
# Regenerate both tracks with the commands in "$ROOT/README.md", then:
skilleval diagnostic-artifact-drift-check \
  --expected "$ROOT" \
  --actual "$TMP_ROOT" \
  --output "$TMP_ROOT/drift-report.json" \
  --markdown-output "$TMP_ROOT/drift-report.md"
```

Boundary: this is local diagnostic evidence only, not a Marketplace Action, not
GitHub API PR comments, not PR annotations, not SaaS, not a runtime MCP router,
not a SOTA claim, not benchmark status, not production readiness, and not
release approval.

### PR-facing CI Summary

`skilleval ci-summary` writes a local/GitHub Actions summary from explicit
check outcomes, changed files, committed report paths, and an overclaim scan.
The validate workflow appends the Markdown to `$GITHUB_STEP_SUMMARY` and then
enforces the JSON decision as `ALLOW_MERGE` or `BLOCK_MERGE`. The external
validation pack is passed as an explicit `external-pack` check outcome.

Boundary: this is not a GitHub API comment bot, not a PR annotation system,
not a Marketplace Action, not SaaS, not a runtime MCP router, not a SOTA claim,
and not release approval. It summarizes local validation artifacts; it does
not approve a release or merge by itself.

### GitHub Actions Node 24 Preflight

The Validate workflow includes a GitHub Actions Node 24 preflight by setting
`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` at workflow level. This exercises existing
JavaScript actions such as checkout, setup-python, and artifact upload under
the upcoming runtime while preserving the same pytest, OpenSpec, release-check,
diagnostic gate, diagnostic drift, external pack, CI summary, artifact upload,
and final decision enforcement checks. The migration knob follows GitHub's
[Node 20 deprecation changelog](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/).

Local simulation checklist:

```bash
python -m pytest -q
OPENSPEC_TELEMETRY=0 openspec validate --all --strict
skilleval release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
# Then run the diagnostic/external pack regeneration flows from docs/usage.md
# and simulate skilleval ci-summary with explicit check outcomes.
```

Boundary: this is not a Marketplace Action, not GitHub API PR comments, not PR
annotations, not SaaS, not a runtime MCP router, not a SOTA claim, not
benchmark status, not production readiness, not release approval, not automatic
merge approval, and not a permanent compatibility guarantee.

### Reusable GitHub Action RC

The repository now includes a root `action.yml` composite action scaffold for
external maintainers who want to run a small SkillEval gate in their own
repository. The action delegates to `skilleval github-action-gate`, accepts
`skill-path`, `benchmark-path`, `min-recall-at-k`, `max-negative-hit-rate`, and
`upload-artifacts`, writes deterministic gate JSON/Markdown plus CI summary
artifacts, and can optionally upload those artifacts with
`actions/upload-artifact@v4`.

Example usage stays on `@main` or a commit SHA while this remains a release
candidate:

```yaml
- uses: Raidriar7170/hermes-skilleval@main
  with:
    skill-path: examples/github-action/skills
    benchmark-path: examples/github-action/benchmark
    min-recall-at-k: "1.0"
    max-negative-hit-rate: "0.0"
    upload-artifacts: 'true'
```

The public-safe fixture lives in
[`examples/github-action/`](examples/github-action/). It is a Reusable GitHub
Action RC, not a Marketplace Action release, not GitHub API PR comments, not PR
annotations, not SaaS, not a runtime MCP router, not a SOTA claim, not
benchmark status, not production readiness, not release approval, not automatic
merge approval, and not a v0.2.0 release.

---

## Experiment Timeline / 实验演进

For the full phase-by-phase experiment history, see
[`docs/experiment-timeline.md`](docs/experiment-timeline.md). The README keeps
the current problem, release evidence, dashboard preview, commands, and
architecture on the front door.

---

## Technical Details / 技术细节

### 1. Skill Parsing and Indexing

`skill_parser.py` discovers `skills/**/SKILL.md`, reads YAML frontmatter,
infers categories from paths, extracts trigger terms, estimates token counts,
and writes a portable JSON skill index.

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

`improve-skills` proposes deterministic metadata patches from observed misses
and negative hits. `judge-improvement` compares before/after runs and writes an
acceptance report, turning routing failures into measurable skill-library edits.

### 5. A100 Deployment

Phase 7A staged MiniLM embedding and MS MARCO MiniLM cross-encoder models under
the user-owned remote path, selected an idle A100 with `CUDA_VISIBLE_DEVICES=3`,
and validated learned reranking on the full 80-task benchmark. Phase 7B then
fitted dev-split cross-encoder acceptance thresholds and evaluated the frozen
policies on the held-out test split. See [`docs/phase7a.md`](docs/phase7a.md)
and [`docs/phase7b.md`](docs/phase7b.md).

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
| Testing | pytest | 392 pytest cases |
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
- [x] Real skill-library migration test protocol
      ([docs](docs/phase9.md), [protocol](docs/skill-library-migration-protocol.md))
- [x] Agent-in-the-loop skill routing evaluation
      ([docs](docs/phase10.md), [demo](docs/demo/phase10-agent-in-the-loop/dashboard.html))
- [x] Evidence judge calibration for agent-loop traces
      ([docs](docs/phase11.md), [demo](docs/demo/phase11-evidence-judge-calibration/dashboard.html))
- [x] Offline skill metadata patch ranking
      ([docs](docs/phase12.md), [demo](docs/demo/phase12-skill-patch-ranking/ranked-patches.md))
- [x] Patch simulation regression guard
      ([docs](docs/phase13.md), [demo](docs/demo/phase13-patch-simulation/regression-report.md))
- [x] Fine-tuned embedding router for domain-specific skill libraries
      ([docs](docs/phase14.md), [training data](docs/demo/phase14-finetuned-embedding-router/training-summary.json))
- [x] Held-out fine-tuned provenance pack
      ([docs](docs/phase15.md), [demo](docs/demo/phase15-held-out-generalization/provenance.md))
- [x] Blind validation and release handoff gate
      ([docs](docs/phase16.md), [handoff](docs/release-handoff.md))
- [x] Calibrated default-router release selector
      ([docs](docs/phase17.md), [decision](docs/demo/phase17-calibrated-release-selector/release-decision.json))
- [x] CI-backed release reproducibility pack
      ([docs](docs/phase18.md), [manifest](docs/demo/phase18-ci-release-reproducibility/release-manifest.json))

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Project Summary / 项目总结

> **For recruiters and hiring managers:**
>
> Hermes SkillEval demonstrates end-to-end agent evaluation engineering:
>
> - **Agent Systems:** designed a benchmark harness for Hermes-style skill
>   routing, including parsing, indexing, routing, reporting, and
>   failure-driven improvement.
> - **Retrieval and Ranking:** implemented keyword, hybrid, embedding,
>   verification-gated, contrastive, and cross-encoder routing strategies.
> - **ML Evaluation:** built an 80-task benchmark with negative controls and
>   ranking metrics such as Recall@k, MRR, NDCG, and Negative Hit Rate.
> - **Infrastructure:** validated neural reranking on shared A100 infrastructure
>   while selecting idle GPUs and preserving user-owned storage paths.
> - **Engineering Quality:** shipped a typed Python CLI with 392 passing tests,
>   reproducible benchmark artifacts, a static inspection dashboard, and a
>   release gate that keeps `baseline-minilm` when blind validation finds a
>   fine-tuned-router regression.
>
> **面向招聘者:**
>
> 这个项目展示了 Agent Skill 路由评测、检索排序、失败分析、自改进闭环
> 和远端 GPU 部署能力。它不是一个单纯 demo，而是从 benchmark 构建、
> router 设计、metric 评估、cross-encoder 验证到简历材料整理的一套
> 完整工程闭环。
