# Phase 7B Cross-Encoder Calibration Design

## Goal

Phase 7B adds a calibrated acceptance layer for the Phase 7A cross-encoder reranker. The cross-encoder remains the learned ranking stage; calibration decides how many reranked candidates are safe to accept.

## Context

Phase 7A showed two opposing behaviors:

- Rank-only cross-encoder reranking improves ranking quality, especially Recall@5 and NDCG@5.
- Direct selective acceptance over cross-encoder logits is too conservative, while rank-only output admits too many same-category negatives.

The accepted next step is to calibrate cross-encoder acceptance on the dev split, then evaluate the frozen policy on the test split.

## Approach

Use a small threshold calibration layer instead of retraining the cross-encoder:

- Fit only on records from `split == "dev"`.
- Search raw cross-encoder score thresholds and top-1/top-2 margin thresholds from observed dev scores.
- Reject a task when the top score is below the score threshold.
- Reject a task when the top-1/top-2 margin is below the margin threshold.
- Keep all candidates above the score threshold, capped by `top_k`.
- Optimize Recall@5, MRR, and NDCG@5 under a maximum Negative Hit Rate constraint.
- Optionally cap Selection Rate@5 to produce stricter or more balanced acceptance policies.

This keeps the policy simple, reproducible, and independent of test labels.

## CLI Surface

Add `calibrate-cross-encoder`:

```bash
python -m hermes_skilleval.cli calibrate-cross-encoder \
  --results docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only/results.jsonl \
  --output docs/demo/phase7b-cross-encoder-calibration/balanced-calibration.json \
  --calibrated-output docs/demo/phase7b-cross-encoder-calibration/cross-encoder-calibrated-balanced-test/results.jsonl \
  --fit-split dev \
  --apply-split test \
  --max-negative-hit-rate 0.05 \
  --max-selection-rate-at-5 0.4
```

Also allow `eval` and `compare` to load a calibration JSON through `--cross-encoder-calibration`, with explicit threshold flags taking precedence when provided.

## Reporting

Phase 7B should preserve:

- Calibration JSON files for the fitted thresholds and fit-split metrics.
- Test-split calibrated `results.jsonl` files.
- Markdown reports for strict and balanced test policies.
- A Phase 7B summary that compares Phase 6B contrastive gating, Phase 7A rank-only cross-encoder, and Phase 7B calibrated cross-encoder on the same test split.

## Acceptance Criteria

- Tests cover dev-only fitting, negative-hit constraints, score thresholding, margin thresholding, CLI calibration output, and router calibration-file loading.
- Strict calibration keeps test Negative Hit Rate at or below the Phase 6B contrastive-gated baseline while preserving most rank-only Recall@5.
- Balanced calibration demonstrates the trade-off between higher Recall@5 and higher negative-hit risk.
- Documentation clearly states that the current implementation is threshold calibration over raw cross-encoder scores, not a learned Platt or isotonic probability model.
