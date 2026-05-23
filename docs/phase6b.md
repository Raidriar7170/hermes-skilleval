# Phase 6B: Contrastive Selective Gating

Phase 6B adds an ambiguity-aware selective gate to the verification-gated MiniLM router. It targets the same-category negative skills exposed by the Phase 6A robustness benchmark without adding training, cross-encoders, or LLM judges.

## What Changed

- Added `--contrastive-selective` to gated routing.
- Added `--contrastive-margin` and `--min-evidence` thresholds.
- Kept existing `--selective --min-confidence` behavior backward compatible.
- Added a committed benchmark run in `docs/demo/phase6b-contrastive-gating`.

## Result

The committed run compares `embedding-minilm`, `gated-minilm-selective`, and `gated-minilm-contrastive`.

| Router | Tasks | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Selection Rate@5 | Ambiguous Negative Hit Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-minilm | 80 | 0.812 | 0.956 | 0.934 | 0.930 | 0.100 | 1.000 | 0.800 |
| gated-minilm-selective | 80 | 0.881 | 0.981 | 0.985 | 0.974 | 0.113 | 0.715 | 0.900 |
| gated-minilm-contrastive | 80 | 0.881 | 0.969 | 0.985 | 0.964 | 0.037 | 0.320 | 0.300 |

## Interpretation

Contrastive selective gating keeps the high-confidence top choice from the Phase 6A gated router, then rejects later same-category candidates when their prompt evidence is too weak relative to the best accepted candidate. This lowers full-benchmark Negative Hit Rate from 0.113 to 0.037 and held-out ambiguous-pair Negative Hit Rate from 0.900 to 0.300, while preserving Recall@1 at 0.881 and keeping Recall@5 at 0.969.

The trade-off is intentional: Selection Rate@5 falls from 0.715 to 0.320 because the router abstains from weak follow-on skills rather than padding the output with near-neighbor candidates.

## Reproduce

Run the commands in `docs/superpowers/plans/2026-05-23-phase6b-contrastive-gating.md`, Task 3.
