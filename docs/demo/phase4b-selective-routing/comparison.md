# Hermes SkillEval Router Comparison

| Router | Tasks | Recall@1 | Recall@3 | Recall@5 | Precision@5 | MRR | NDCG@5 | Negative Hit Rate | Coverage | Selection Rate@5 | Abstention Rate | Accepted Recall@5 | Negative Accepted Rate | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-minilm | 30 | 0.867 | 1.000 | 1.000 | 0.227 | 0.967 | 0.973 | 0.033 | 1.000 | 1.000 | 0.000 | 1.000 | 0.033 | 29.598 |
| gated-minilm-selective | 30 | 0.933 | 1.000 | 1.000 | 0.227 | 1.000 | 1.000 | 0.000 | 1.000 | 0.600 | 0.000 | 1.000 | 0.000 | 9.995 |
| hybrid | 30 | 0.933 | 1.000 | 1.000 | 0.227 | 1.000 | 1.000 | 0.033 | 1.000 | 1.000 | 0.000 | 1.000 | 0.033 | 0.328 |
| keyword | 30 | 0.933 | 1.000 | 1.000 | 0.227 | 1.000 | 1.000 | 0.033 | 1.000 | 1.000 | 0.000 | 1.000 | 0.033 | 0.209 |
