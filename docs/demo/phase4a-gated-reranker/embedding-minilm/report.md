# Hermes SkillEval Report

- Router: embedding-minilm
- Records: 30

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 0.867 |
| Recall@3 | 1.000 |
| Recall@5 | 1.000 |
| Precision@5 | 0.227 |
| MRR | 0.967 |
| NDCG@5 | 0.973 |
| Negative Hit Rate | 0.033 |
| Average Latency (ms) | 23.163 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| systematic-debugging | 17 |
| wandb | 17 |
| research-paper-summary | 12 |
| docker | 11 |
| literature-review | 11 |
| test-driven-development | 10 |
| mlflow | 10 |
| citation-checking | 9 |
| note-taking | 9 |
| academic-writing | 8 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| coding-debugging-001 | 1.000 | 0.000 | 105.240 |
| coding-debugging-002 | 1.000 | 1.000 | 33.150 |
| coding-debugging-003 | 1.000 | 0.000 | 34.834 |
| coding-debugging-004 | 1.000 | 0.000 | 34.284 |
| coding-debugging-005 | 1.000 | 0.000 | 32.467 |
| coding-debugging-006 | 1.000 | 0.000 | 6.586 |
| coding-debugging-007 | 1.000 | 0.000 | 34.232 |
| coding-debugging-008 | 1.000 | 0.000 | 6.848 |
| coding-debugging-009 | 1.000 | 0.000 | 35.431 |
| coding-debugging-010 | 1.000 | 0.000 | 33.122 |
| creative-productivity-001 | 1.000 | 0.000 | 6.409 |
| creative-productivity-002 | 1.000 | 0.000 | 33.551 |
| creative-productivity-003 | 1.000 | 0.000 | 5.992 |
| data-mlops-001 | 1.000 | 0.000 | 33.311 |
| data-mlops-002 | 1.000 | 0.000 | 7.356 |
| data-mlops-003 | 1.000 | 0.000 | 30.261 |
| data-mlops-004 | 1.000 | 0.000 | 32.760 |
| data-mlops-005 | 1.000 | 0.000 | 7.369 |
| data-mlops-006 | 1.000 | 0.000 | 5.921 |
| productivity-001 | 1.000 | 0.000 | 33.061 |
| productivity-002 | 1.000 | 0.000 | 32.972 |
| productivity-003 | 1.000 | 0.000 | 7.027 |
| research-writing-001 | 1.000 | 0.000 | 29.799 |
| research-writing-002 | 1.000 | 0.000 | 32.945 |
| research-writing-003 | 1.000 | 0.000 | 7.336 |
| research-writing-004 | 1.000 | 0.000 | 5.753 |
| research-writing-005 | 1.000 | 0.000 | 7.378 |
| research-writing-006 | 1.000 | 0.000 | 6.839 |
| research-writing-007 | 1.000 | 0.000 | 5.647 |
| research-writing-008 | 1.000 | 0.000 | 7.018 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| coding-debugging-002 | systematic-debugging, test-driven-development, songwriting-and-ai-music, ascii-art, docker | systematic-debugging | 1.000 | 1.000 |
