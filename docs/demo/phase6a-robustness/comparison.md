# Hermes SkillEval Router Comparison

| Router | Tasks | Recall@1 | Recall@3 | Recall@5 | Precision@5 | MRR | NDCG@5 | Negative Hit Rate | Coverage | Selection Rate@5 | Abstention Rate | Accepted Recall@5 | Negative Accepted Rate | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-hashing | 80 | 0.619 | 0.819 | 0.881 | 0.200 | 0.776 | 0.785 | 0.075 | 1.000 | 1.000 | 0.000 | 0.881 | 0.075 | 0.821 |
| embedding-minilm | 80 | 0.812 | 0.944 | 0.956 | 0.225 | 0.934 | 0.930 | 0.100 | 1.000 | 1.000 | 0.000 | 0.956 | 0.100 | 11.266 |
| gated-minilm-selective | 80 | 0.881 | 0.981 | 0.981 | 0.230 | 0.985 | 0.974 | 0.113 | 1.000 | 0.715 | 0.000 | 0.981 | 0.113 | 7.603 |
| hybrid | 80 | 0.869 | 0.975 | 0.994 | 0.235 | 0.978 | 0.974 | 0.138 | 1.000 | 1.000 | 0.000 | 0.994 | 0.138 | 0.525 |
| keyword | 80 | 0.869 | 0.969 | 0.988 | 0.233 | 0.978 | 0.969 | 0.138 | 1.000 | 1.000 | 0.000 | 0.988 | 0.138 | 0.398 |
