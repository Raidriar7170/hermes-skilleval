# Hermes SkillEval CLI Usage

This page keeps the longer command walkthrough out of the README front door.
For the current release conclusion and reviewer evidence, start from
[`docs/release-handoff.md`](release-handoff.md).

## Installation

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

## 1. Index a Hermes-style Skill Library

```bash
skilleval index \
  --skills-path benchmarks/skills \
  --output runs/skills.json
```

## 2. Run a Router Evaluation

```bash
skilleval eval \
  --index runs/skills.json \
  --tasks benchmarks/tasks \
  --router hybrid \
  --top-k 5 \
  --output-dir runs/hybrid
```

## 3. Compare Multiple Routers

```bash
skilleval compare \
  --index runs/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding-hashing=embedding:hashing \
  --top-k 5 \
  --output-dir runs/comparison
```

## 4. Analyze Failures

```bash
skilleval analyze-failures \
  --runs runs/comparison \
  --baseline hybrid \
  --candidate embedding-hashing \
  --output runs/comparison/failure-analysis.md
```

## 5. Run the Cross-Encoder Reranker

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

## 6. Calibrate Cross-Encoder Acceptance

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

## 7. Run Agent-in-the-loop Migration Evaluation

```bash
skilleval run-agent-loop \
  --routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --condition routed-skill \
  --output-dir runs/phase10-agent-loop/hybrid
```

The command writes dashboard-compatible `results.jsonl`,
`agent-traces.jsonl`, `agent-loop-summary.json`, and `report.md` artifacts.
Use `--condition no-skill` and `--condition oracle-skill` for the control runs.

## 8. Judge Agent-loop Evidence

```bash
skilleval judge-agent-loop \
  --traces docs/demo/phase10-agent-in-the-loop/agent-loop-hybrid/agent-traces.jsonl \
  --output-dir runs/phase11-evidence-judge/hybrid \
  --run-label judge-agent-loop-hybrid
```

The committed Phase 11 judge uses an offline `deterministic-rubric`; it does
not require API keys, network access, or live LLM judging.

## 9. Rank Offline Skill Metadata Patch Candidates

```bash
skilleval rank-skill-patches \
  --judge-results docs/demo/phase11-evidence-judge-calibration/judge-agent-loop-hybrid/judge-results.jsonl \
  --routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --output-dir docs/demo/phase12-skill-patch-ranking
```

Phase 12 joins Phase 11 routed-skill judge failures, Phase 9 routes, migration
task metadata, and the migrated skills index to rank offline deterministic
metadata patch candidates. It does not modify source `SKILL.md` files or write
a patched skills index.

## 10. Simulate Ranked Skill Patches

```bash
skilleval simulate-skill-patches \
  --ranked-patches docs/demo/phase12-skill-patch-ranking/ranked-patches.jsonl \
  --baseline-routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --router hybrid \
  --top-k 5 \
  --max-patches 5 \
  --output-dir docs/demo/phase13-patch-simulation
```

Phase 13 applies ranked metadata candidates to copied `Skill` records only,
writes a shadow skill index, and compares shadow routing against the Phase 9
baseline. It is an offline deterministic regression guard, not fine-tuning or
learned training, and it does not modify source `SKILL.md` files or overwrite
the original `skills.json`.

## 11. Export Fine-Tuned Embedding Router Training Data

```bash
skilleval export-embedding-training-data \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --output-dir docs/demo/phase14-finetuned-embedding-router
```

Phase 14 exports supervised task-skill pairs and a remote-ready training config
for a domain-specific embedding router. It does not commit model checkpoints,
embedding caches, or downloaded models. Fine-tuned evaluation artifacts are
added only after a real model path is evaluated:

```bash
skilleval judge-finetuned-embedding \
  --baseline-results docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl \
  --candidate-results docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl \
  --output-dir docs/demo/phase14-finetuned-embedding-router \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router
```

## 12. Build Held-Out Fine-Tuned Provenance Pack

```bash
skilleval judge-finetuned-embedding \
  --baseline-results docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl \
  --candidate-results docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl \
  --output-dir docs/demo/phase15-held-out-generalization \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --apply-split test \
  --write-filtered-results

skilleval write-finetuned-provenance \
  --training-summary docs/demo/phase14-finetuned-embedding-router/training-summary.json \
  --train-config docs/demo/phase14-finetuned-embedding-router/train-config.json \
  --train-run-summary docs/demo/phase15-held-out-generalization/train-run-summary.json \
  --model-manifest docs/demo/phase15-held-out-generalization/model-manifest.json \
  --regression-summary docs/demo/phase15-held-out-generalization/regression-summary.json \
  --output-dir docs/demo/phase15-held-out-generalization
```

Phase 15 filters the Phase 14 result files to the strict held-out `test` split
and adds a sanitized provenance pack. It records file hashes and training
summaries while keeping model checkpoints out of the repository.

## 13. Run Blind Validation and Release Gate

```bash
skilleval write-blind-validation \
  --baseline-results docs/demo/phase16-blind-validation/baseline-minilm/results.jsonl \
  --candidate-results docs/demo/phase16-blind-validation/finetuned-embedding/results.jsonl \
  --output-dir docs/demo/phase16-blind-validation \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --task-root benchmarks/blind-migration-tasks

skilleval verify-release \
  --public-root README.md \
  --public-root docs/phase9.md \
  --public-root docs/phase10.md \
  --public-root docs/phase11.md \
  --public-root docs/phase12.md \
  --public-root docs/phase13.md \
  --public-root docs/phase14.md \
  --public-root docs/phase15.md \
  --public-root docs/phase16.md \
  --public-root docs/release-handoff.md \
  --public-root docs/demo/phase16-blind-validation \
  --public-root benchmarks/blind-migration-tasks \
  --required-path docs/demo/phase16-blind-validation/regression-summary.json \
  --required-path docs/release-handoff.md \
  --summary-output docs/demo/phase16-blind-validation/release-check-summary.json
```

Phase 16 adds a blind `test` task pack and a release verification gate. The
committed blind result is `REVIEW_REQUIRED`: the fine-tuned router preserves
Recall@5 but increases negative-skill selection on the blind pack, so it should
not replace the baseline without calibration or rollback logic.

## 14. Select the Default Release Router

```bash
skilleval select-release-router \
  --regression-summary docs/demo/phase16-blind-validation/regression-summary.json \
  --route-diffs docs/demo/phase16-blind-validation/route-diffs.jsonl \
  --output-dir docs/demo/phase17-calibrated-release-selector
```

Phase 17 turns the Phase 16 blind-validation evidence into an explicit release
decision:
[`docs/demo/phase17-calibrated-release-selector/release-decision.json`](demo/phase17-calibrated-release-selector/release-decision.json).
The current selector result is `KEEP_BASELINE`: the default router remains
`baseline-minilm`, and `finetuned-embedding` is not approved as the default.
See [`docs/phase17.md`](phase17.md) and
[`docs/release-handoff.md`](release-handoff.md).

## 15. Reproduce the Release Pack in CI Shape

```bash
skilleval release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
```

Phase 18 reruns the release selector and public release guard, then records a
deterministic manifest at
[`docs/demo/phase18-ci-release-reproducibility/release-manifest.json`](demo/phase18-ci-release-reproducibility/release-manifest.json).
The current reproducible release reading remains `KEEP_BASELINE`.

## 16. Static Dashboard

```bash
skilleval dashboard \
  --runs docs/demo/phase7b-cross-encoder-calibration \
  --output docs/demo/phase8-static-dashboard/dashboard.html
```

The generated file is self-contained and can be opened directly in a browser
for interactive run filtering, failure inspection, score ranking, and raw JSON
audit:
[`Live dashboard`](https://raidriar7170.github.io/hermes-skilleval/docs/demo/phase8-static-dashboard/dashboard.html).
The committed source artifact is also available at
[`docs/demo/phase8-static-dashboard/dashboard.html`](demo/phase8-static-dashboard/dashboard.html).

## 17. Run Tests

```bash
pytest -q
```

Expected:

```text
314 passed
```
