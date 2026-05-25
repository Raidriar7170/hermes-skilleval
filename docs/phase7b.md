# Phase 7B: Cross-Encoder Acceptance Calibration

Phase 7B adds a dev-split calibration layer on top of the Phase 7A rank-only cross-encoder reranker. The goal is to preserve the cross-encoder's stronger ranking while reducing same-category negative hits before the router is used as a selective acceptance policy.

## What Changed

- Added `src/hermes_skilleval/calibration.py` for fitting and applying cross-encoder acceptance thresholds from JSONL benchmark records.
- Added `calibrate-cross-encoder` to the CLI.
- Added `--cross-encoder-calibration`, `--cross-encoder-score-threshold`, and `--cross-encoder-margin-threshold` to `eval` and `compare`.
- Added router support for raw score thresholding plus a top-1/top-2 margin gate.
- Added committed Phase 7B artifacts in `docs/demo/phase7b-cross-encoder-calibration`.

This phase uses threshold calibration over raw cross-encoder scores. It does not yet train a Platt-scaling or isotonic probability model.

## Calibration Method

The fitter reads the Phase 7A rank-only cross-encoder run and uses only `split == "dev"` records:

1. collect candidate raw score thresholds from observed dev selected candidates;
2. collect candidate top-1/top-2 margin thresholds;
3. apply each threshold pair to dev records;
4. keep only pairs satisfying `max_negative_hit_rate`;
5. optionally cap `Selection Rate@5`;
6. choose the pair with the best Recall@5, MRR, and NDCG@5.

The selected thresholds are then frozen and applied to held-out `split == "test"` records.

## Commands

Strict calibration:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli calibrate-cross-encoder \
  --results docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only/results.jsonl \
  --output docs/demo/phase7b-cross-encoder-calibration/strict-calibration.json \
  --calibrated-output docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-strict-test/results.jsonl \
  --fit-split dev \
  --apply-split test \
  --max-negative-hit-rate 0.05 \
  --max-selection-rate-at-5 0.3
```

Balanced calibration:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli calibrate-cross-encoder \
  --results docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only/results.jsonl \
  --output docs/demo/phase7b-cross-encoder-calibration/balanced-calibration.json \
  --calibrated-output docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-balanced-test/results.jsonl \
  --fit-split dev \
  --apply-split test \
  --max-negative-hit-rate 0.05 \
  --max-selection-rate-at-5 0.4
```

Reports:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli report \
  --runs docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-strict-test

PYTHONPATH=src python -m hermes_skilleval.cli report \
  --runs docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-balanced-test
```

Same-test-split comparison:

```bash
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
```

## Results

The table below compares only the 30 held-out test records so the Phase 7B results are not mixed with Phase 7A full-benchmark metrics.

| Router | Tasks | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Selection Rate@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gated-minilm-contrastive-test | 30 | 0.850 | 0.950 | 1.000 | 0.959 | 0.100 | 0.360 |
| cross-encoder-rank-only-test | 30 | 0.850 | 1.000 | 1.000 | 0.987 | 0.333 | 1.000 |
| cross-encoder-calibrated-strict-test | 30 | 0.850 | 0.950 | 1.000 | 0.957 | 0.033 | 0.320 |
| cross-encoder-calibrated-balanced-test | 30 | 0.850 | 0.967 | 1.000 | 0.970 | 0.100 | 0.393 |

Fitted thresholds:

| Policy | Fit Split | Fitted Tasks | Score Threshold | Margin Threshold | Dev Negative Hit Rate | Dev Recall@5 | Dev Selection Rate@5 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| strict | dev | 50 | -3.992446 | 0.000000 | 0.000 | 0.910 | 0.288 |
| balanced | dev | 50 | -4.895247 | 0.000000 | 0.000 | 0.960 | 0.340 |

## Interpretation

Rank-only cross-encoder reranking is the best pure ranking signal on the held-out test split: it reaches Recall@5 `1.000` and NDCG@5 `0.987`. It is not a safe selective router by itself because Negative Hit Rate rises to `0.333`, concentrated in ambiguous same-category robustness tasks.

Strict calibration removes most of that risk. It lowers Negative Hit Rate from `0.333` to `0.033`, beating the contrastive gated test baseline's `0.100`, while keeping Recall@5 at `0.950`. This is the safest Phase 7B acceptance policy.

Balanced calibration keeps more of the rank-only recall gain. It reaches Recall@5 `0.967` and NDCG@5 `0.970`, but lets Negative Hit Rate rise back to `0.100`, matching the contrastive gated test baseline rather than improving it.

The learned margin threshold is `0.0` for both policies on this dev split. The useful calibration signal in this run is the raw score threshold plus a selection-rate cap. A future probability calibration step could add Platt scaling or isotonic regression, but the current evidence already supports the narrower conclusion: calibrated threshold acceptance improves cross-encoder routing while preserving low negative-hit behavior.

## Resume Value

Phase 7B turns the Phase 7A "cross-encoder needs calibration" conclusion into an implemented acceptance layer with dev/test isolation, reproducible threshold artifacts, CLI support, and held-out evidence for the recall-versus-negative-hit trade-off.
