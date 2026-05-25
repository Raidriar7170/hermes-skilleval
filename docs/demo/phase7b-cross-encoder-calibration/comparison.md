# Hermes SkillEval Router Comparison

| Router | Tasks | Recall@1 | Recall@3 | Recall@5 | Precision@5 | MRR | NDCG@5 | Negative Hit Rate | Coverage | Selection Rate@5 | Abstention Rate | Accepted Recall@5 | Negative Accepted Rate | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cross-encoder-calibrated-balanced-test | 30 | 0.850 | 0.950 | 0.967 | 0.247 | 1.000 | 0.970 | 0.100 | 1.000 | 0.393 | 0.000 | 0.967 | 0.100 | 18.222 |
| cross-encoder-calibrated-strict-test | 30 | 0.850 | 0.933 | 0.950 | 0.240 | 1.000 | 0.957 | 0.033 | 1.000 | 0.320 | 0.000 | 0.950 | 0.033 | 18.222 |
| cross-encoder-rank-only-test | 30 | 0.850 | 0.950 | 1.000 | 0.260 | 1.000 | 0.987 | 0.333 | 1.000 | 1.000 | 0.000 | 1.000 | 0.333 | 18.222 |
| gated-minilm-contrastive-test | 30 | 0.850 | 0.950 | 0.950 | 0.240 | 1.000 | 0.959 | 0.100 | 1.000 | 0.360 | 0.000 | 0.950 | 0.100 | 10.496 |
