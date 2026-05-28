# Hermes SkillEval Router Comparison

| Router | Tasks | Recall@1 | Recall@3 | Recall@5 | Precision@5 | MRR | NDCG@5 | Negative Hit Rate | Coverage | Selection Rate@5 | Abstention Rate | Accepted Recall@5 | Negative Accepted Rate | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-hashing | 12 | 0.750 | 0.958 | 1.000 | 0.267 | 0.944 | 0.948 | 0.167 | 1.000 | 1.000 | 0.000 | 1.000 | 0.167 | 2.819 |
| gated-hashing-selective | 12 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 3.295 |
| hybrid | 12 | 0.750 | 1.000 | 1.000 | 0.267 | 0.944 | 0.958 | 0.250 | 1.000 | 1.000 | 0.000 | 1.000 | 0.250 | 0.607 |
