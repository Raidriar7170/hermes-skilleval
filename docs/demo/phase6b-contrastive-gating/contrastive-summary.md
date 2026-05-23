# Phase 6B Contrastive Gating Summary

## Router Summary

| Router | Tasks | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Selection Rate@5 | Ambiguous Negative Hit Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-minilm | 80 | 0.812 | 0.956 | 0.934 | 0.930 | 0.100 | 1.000 | 0.800 |
| gated-minilm-selective | 80 | 0.881 | 0.981 | 0.985 | 0.974 | 0.113 | 0.715 | 0.900 |
| gated-minilm-contrastive | 80 | 0.881 | 0.969 | 0.985 | 0.964 | 0.037 | 0.320 | 0.300 |

## Acceptance Check

- Full Negative Hit Rate delta: -0.075
- Ambiguous Negative Hit Rate delta: -0.600
- Recall@1 delta: +0.000
- Recall@5: 0.969
