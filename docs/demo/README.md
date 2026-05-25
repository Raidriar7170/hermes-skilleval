# Demo Run

This directory contains committed demo runs for Hermes SkillEval.

The original `benchmark-hybrid` and `router-comparison` artifacts use the tiny
fixture skill library in `tests/fixtures/skills` and are smoke/demo artifacts
for CLI reporting. The main current benchmark artifacts are the Phase 6A
robustness run, the Phase 6B contrastive gating run, the Phase 7A
cross-encoder reranker run, and the Phase 7B cross-encoder calibration run over
the generated 80-task, 45-skill corpus.

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
skilleval index \
  --skills-path benchmarks/skills \
  --output docs/demo/phase6b-contrastive-gating/skills.json
skilleval compare \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --routers embedding-minilm=embedding:sentence-transformers,gated-minilm-selective=gated:sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase6b-minilm-cache.json \
  --selective \
  --min-confidence 0.5 \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir docs/demo/phase6b-contrastive-gating
skilleval eval \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --router gated \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase6b-minilm-cache.json \
  --selective \
  --contrastive-selective \
  --contrastive-margin 6.0 \
  --min-evidence 2.0 \
  --min-confidence 0.5 \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir docs/demo/phase6b-contrastive-gating/gated-minilm-contrastive
skilleval report \
  --runs docs/demo/phase6b-contrastive-gating/gated-minilm-contrastive
skilleval analyze-failures \
  --runs docs/demo/phase6b-contrastive-gating \
  --baseline gated-minilm-selective \
  --candidate gated-minilm-contrastive \
  --output docs/demo/phase6b-contrastive-gating/failure-analysis.md
skilleval compare \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --routers embedding-minilm=embedding:sentence-transformers,gated-minilm-contrastive=gated:sentence-transformers,cross-encoder-minilm=cross-encoder:sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase7a-minilm-cache.json \
  --cross-encoder-model cross-encoder/ms-marco-MiniLM-L-6-v2 \
  --gated-pool-size 10 \
  --selective \
  --contrastive-selective \
  --output-dir docs/demo/phase7a-cross-encoder
skilleval analyze-failures \
  --runs docs/demo/phase7a-cross-encoder \
  --baseline gated-minilm-contrastive \
  --candidate cross-encoder-minilm \
  --output docs/demo/phase7a-cross-encoder/failure-analysis.md
skilleval eval \
  --index docs/demo/phase6b-contrastive-gating/skills.json \
  --tasks benchmarks/tasks \
  --router cross-encoder \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache /tmp/skilleval-phase7a-minilm-cache.json \
  --cross-encoder-model cross-encoder/ms-marco-MiniLM-L-6-v2 \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only
skilleval calibrate-cross-encoder \
  --results docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only/results.jsonl \
  --output docs/demo/phase7b-cross-encoder-calibration/strict-calibration.json \
  --calibrated-output docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-strict-test/results.jsonl \
  --fit-split dev \
  --apply-split test \
  --max-negative-hit-rate 0.05 \
  --max-selection-rate-at-5 0.3
skilleval report \
  --runs docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-strict-test
skilleval calibrate-cross-encoder \
  --results docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only/results.jsonl \
  --output docs/demo/phase7b-cross-encoder-calibration/balanced-calibration.json \
  --calibrated-output docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-balanced-test/results.jsonl \
  --fit-split dev \
  --apply-split test \
  --max-negative-hit-rate 0.05 \
  --max-selection-rate-at-5 0.4
skilleval report \
  --runs docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-balanced-test
PYTHONPATH=src python - <<'PY'
import json
from pathlib import Path
from hermes_skilleval.comparison import write_comparison_report
from hermes_skilleval.report import write_markdown_report

root = Path("docs/demo/phase7b-cross-encoder-calibration")
sources = {
    "gated-minilm-contrastive-test": Path(
        "docs/demo/phase7a-cross-encoder/gated-minilm-contrastive/results.jsonl"
    ),
    "cross-encoder-rank-only-test": Path(
        "docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only/results.jsonl"
    ),
}
result_paths = {}
for label, source in sources.items():
    out_dir = root / label
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "results.jsonl"
    records = [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    test_records = [record for record in records if record.get("split") == "test"]
    out_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in test_records),
        encoding="utf-8",
    )
    write_markdown_report(out_path, out_dir / "report.md")
    result_paths[label] = out_path

result_paths.update(
    {
        "cross-encoder-calibrated-balanced-test": root
        / "cross-encoder-calibrated-balanced-test"
        / "results.jsonl",
        "cross-encoder-calibrated-strict-test": root
        / "cross-encoder-calibrated-strict-test"
        / "results.jsonl",
    }
)
write_comparison_report(result_paths, root / "comparison.md")
PY
skilleval dashboard \
  --runs docs/demo/phase7b-cross-encoder-calibration \
  --output docs/demo/phase8-static-dashboard/dashboard.html
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
- `phase5-self-improvement/patches.json`: deterministic metadata patch
  proposals generated from failed routing records.
- `phase5-self-improvement/patched-skills.json`: patched skill index used for
  before/after evaluation.
- `phase5-self-improvement/comparison.md`: before/after comparison for the
  patched MiniLM embedding run.
- `phase5-self-improvement/acceptance.md`: verification gate result for the
  patch set.
- `phase6a-robustness/comparison.md`: Phase 6A comparison across keyword,
  hybrid, hashing embedding, MiniLM embedding, and selective gated MiniLM over
  the 80-task benchmark.
- `phase6a-robustness/robustness-summary.md`: corpus counts plus split-level
  diagnostics for the expanded benchmark.
- `phase6a-robustness/failure-analysis.md`: failure-mode analysis comparing
  MiniLM against selective gated MiniLM on the robustness pack.
- `phase6b-contrastive-gating/comparison.md`: Phase 6B comparison for MiniLM,
  selective gated MiniLM, and contrastive gated MiniLM over the 80-task
  robustness benchmark.
- `phase6b-contrastive-gating/contrastive-summary.md`: acceptance-check
  summary for negative-hit, ambiguous-pair, Recall@1, and Recall@5 deltas.
- `phase6b-contrastive-gating/failure-analysis.md`: failure-mode comparison
  between standard selective gating and contrastive selective gating.
- `phase7a-cross-encoder/comparison.md`: Phase 7A comparison for MiniLM
  embedding, contrastive gated MiniLM, and selective cross-encoder MiniLM.
- `phase7a-cross-encoder/cross-encoder-minilm-rank-only/report.md`: rank-only
  cross-encoder run used to separate reranking gains from acceptance filtering.
- `phase7a-cross-encoder/failure-analysis.md`: failure-mode comparison between
  contrastive gated MiniLM and selective cross-encoder MiniLM.
- `phase7b-cross-encoder-calibration/strict-calibration.json`: dev-split fitted
  thresholds for the safer calibrated acceptance policy.
- `phase7b-cross-encoder-calibration/balanced-calibration.json`: dev-split
  fitted thresholds for the higher-recall calibrated acceptance policy.
- `phase7b-cross-encoder-calibration/cross-encoder-calibrated-*-test/report.md`:
  held-out test reports for strict and balanced calibrated policies.
- `phase7b-cross-encoder-calibration/comparison.md`: same-test-split comparison
  across contrastive gated, rank-only cross-encoder, and calibrated
  cross-encoder policies.
- `phase8-static-dashboard/dashboard.html`: self-contained interactive dashboard
  for filtering Phase 7B runs, inspecting failures, viewing score rankings, and
  auditing raw task records.
