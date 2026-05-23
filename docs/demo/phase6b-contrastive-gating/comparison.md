# Hermes SkillEval Router Comparison

| Router | Tasks | Recall@1 | Recall@3 | Recall@5 | Precision@5 | MRR | NDCG@5 | Negative Hit Rate | Coverage | Selection Rate@5 | Abstention Rate | Accepted Recall@5 | Negative Accepted Rate | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-minilm | 80 | 0.812 | 0.944 | 0.956 | 0.225 | 0.934 | 0.930 | 0.100 | 1.000 | 1.000 | 0.000 | 0.956 | 0.100 | 13.788 |
| gated-minilm-contrastive | 80 | 0.881 | 0.969 | 0.969 | 0.225 | 0.985 | 0.964 | 0.037 | 1.000 | 0.320 | 0.000 | 0.969 | 0.037 | 13.249 |
| gated-minilm-selective | 80 | 0.881 | 0.981 | 0.981 | 0.230 | 0.985 | 0.974 | 0.113 | 1.000 | 0.715 | 0.000 | 0.981 | 0.113 | 7.968 |
