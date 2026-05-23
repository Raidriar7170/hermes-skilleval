# Hermes SkillEval Router Comparison

| Router | Tasks | Recall@1 | Recall@3 | Recall@5 | Precision@5 | MRR | NDCG@5 | Negative Hit Rate | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| embedding-hashing | 30 | 0.717 | 0.933 | 0.967 | 0.213 | 0.873 | 0.882 | 0.100 | 0.394 |
| embedding-minilm | 30 | 0.867 | 1.000 | 1.000 | 0.227 | 0.967 | 0.973 | 0.033 | 28.115 |
| hybrid | 30 | 0.933 | 1.000 | 1.000 | 0.227 | 1.000 | 1.000 | 0.033 | 0.325 |
| keyword | 30 | 0.933 | 1.000 | 1.000 | 0.227 | 1.000 | 1.000 | 0.033 | 0.204 |
