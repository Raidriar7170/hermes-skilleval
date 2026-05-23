# Phase 6A Robustness Summary

## Corpus

| Item | Count |
| --- | ---: |
| Tasks | 80 |
| Skills | 45 |
| Dev tasks | 50 |
| Test tasks | 30 |

## Router Summary

| Router | Recall@1 | Recall@5 | MRR | NDCG@5 | Negative Hit Rate | Selection Rate@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-hashing | 0.619 | 0.881 | 0.776 | 0.785 | 0.075 | 1.000 |
| embedding-minilm | 0.812 | 0.956 | 0.934 | 0.930 | 0.100 | 1.000 |
| gated-minilm-selective | 0.881 | 0.981 | 0.985 | 0.974 | 0.113 | 0.715 |
| hybrid | 0.869 | 0.994 | 0.978 | 0.974 | 0.138 | 1.000 |
| keyword | 0.869 | 0.988 | 0.978 | 0.969 | 0.138 | 1.000 |

## Split Diagnostics

| Router | Split | Tasks | Recall@1 | Negative Hit Rate | Selection Rate@5 |
| --- | --- | ---: | ---: | ---: | ---: |
| embedding-minilm | dev | 50 | 0.840 | 0.000 | 1.000 |
| embedding-minilm | test | 30 | 0.767 | 0.267 | 1.000 |
| gated-minilm-selective | dev | 50 | 0.900 | 0.000 | 0.700 |
| gated-minilm-selective | test | 30 | 0.850 | 0.300 | 0.740 |

## Interpretation

The expanded benchmark is meaningfully harder than the 30-task demo corpus.
MiniLM still beats the hashing embedding baseline, and selective gated routing
improves top-choice accuracy, MRR, and NDCG@5. The new test split also exposes
a real robustness gap: same-category negative skills remain hard, especially
inside the held-out ambiguous-pair tasks.

This is the intended Phase 6A outcome. The benchmark is no longer saturated,
so future work can evaluate cross-encoder reranking, stricter selective
thresholding, LLM judges, or fine-tuned embeddings on a more credible corpus.
