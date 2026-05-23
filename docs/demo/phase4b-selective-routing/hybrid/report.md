# Hermes SkillEval Report

- Router: hybrid
- Records: 30

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 0.933 |
| Recall@3 | 1.000 |
| Recall@5 | 1.000 |
| Precision@5 | 0.227 |
| MRR | 1.000 |
| NDCG@5 | 1.000 |
| Negative Hit Rate | 0.033 |
| Accepted Count | 5.000 |
| Coverage | 1.000 |
| Selection Rate@5 | 1.000 |
| Abstention Rate | 0.000 |
| Accepted Recall@5 | 1.000 |
| Negative Accepted Rate | 0.033 |
| Average Latency (ms) | 0.328 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| academic-writing | 17 |
| research-paper-summary | 16 |
| wandb | 14 |
| systematic-debugging | 11 |
| literature-review | 10 |
| test-driven-development | 9 |
| songwriting-and-ai-music | 9 |
| mlflow | 8 |
| citation-checking | 8 |
| docker | 7 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| coding-debugging-001 | 1.000 | 0.000 | 2.997 |
| coding-debugging-002 | 1.000 | 0.000 | 0.302 |
| coding-debugging-003 | 1.000 | 0.000 | 0.247 |
| coding-debugging-004 | 1.000 | 0.000 | 0.243 |
| coding-debugging-005 | 1.000 | 0.000 | 0.236 |
| coding-debugging-006 | 1.000 | 0.000 | 0.236 |
| coding-debugging-007 | 1.000 | 0.000 | 0.234 |
| coding-debugging-008 | 1.000 | 0.000 | 0.237 |
| coding-debugging-009 | 1.000 | 0.000 | 0.223 |
| coding-debugging-010 | 1.000 | 0.000 | 0.230 |
| creative-productivity-001 | 1.000 | 0.000 | 0.224 |
| creative-productivity-002 | 1.000 | 0.000 | 0.214 |
| creative-productivity-003 | 1.000 | 0.000 | 0.216 |
| data-mlops-001 | 1.000 | 0.000 | 0.222 |
| data-mlops-002 | 1.000 | 0.000 | 0.217 |
| data-mlops-003 | 1.000 | 0.000 | 0.224 |
| data-mlops-004 | 1.000 | 0.000 | 0.224 |
| data-mlops-005 | 1.000 | 0.000 | 0.223 |
| data-mlops-006 | 1.000 | 0.000 | 0.217 |
| productivity-001 | 1.000 | 1.000 | 0.213 |
| productivity-002 | 1.000 | 0.000 | 0.218 |
| productivity-003 | 1.000 | 0.000 | 0.218 |
| research-writing-001 | 1.000 | 0.000 | 0.223 |
| research-writing-002 | 1.000 | 0.000 | 0.317 |
| research-writing-003 | 1.000 | 0.000 | 0.239 |
| research-writing-004 | 1.000 | 0.000 | 0.234 |
| research-writing-005 | 1.000 | 0.000 | 0.230 |
| research-writing-006 | 1.000 | 0.000 | 0.252 |
| research-writing-007 | 1.000 | 0.000 | 0.270 |
| research-writing-008 | 1.000 | 0.000 | 0.248 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| productivity-001 | apple-reminders, google-calendar, literature-review, songwriting-and-ai-music, citation-checking | apple-reminders | 1.000 | 1.000 |
