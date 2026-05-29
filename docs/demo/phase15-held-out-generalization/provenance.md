# Phase 15 Held-Out Generalization Provenance

## Scope

This pack records how the Phase 14 fine-tuned embedding router was trained, which remote model files were produced, and how the committed held-out test-split judge result was generated. The model checkpoint is not committed.

## Training

- Pair count: 28
- Positive pairs: 16
- Hard-negative pairs: 12
- Leakage guard: PASS
- Loss: `MultipleNegativesRankingLoss+ContrastiveLoss`
- Epochs: 3

## Remote Run

- Device: `cuda:0`
- Optimizer steps: 6
- Hard-negative optimizer steps: 3
- Final loss: 0.2228596806526184

## Held-Out Evaluation

- Evaluated split: `test`
- Source task count: 12
- Baseline source task count: 12
- Candidate source task count: 12
- Held-out task count: 4
- Guard status: `PASS`
- Regression count: 0

| Metric | Delta |
|---|---:|
| mrr | +0.000000 |
| ndcg_at_5 | +0.000000 |
| negative_accepted_rate | +0.000000 |
| negative_hit_rate | +0.000000 |
| recall_at_5 | +0.000000 |
| selection_rate_at_5 | +0.000000 |

## Model Manifest

- Model directory: `/mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router`
- File count: 8
- Total size bytes: 91578176

## Limitations

This is a self-built Hermes-style skill-routing benchmark, not a standard external benchmark. It supports regression-aware project evidence; it does not establish SOTA or production readiness.
