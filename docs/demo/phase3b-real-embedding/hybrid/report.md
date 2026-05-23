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
| Average Latency (ms) | 0.325 |

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
| coding-debugging-001 | 1.000 | 0.000 | 2.919 |
| coding-debugging-002 | 1.000 | 0.000 | 0.296 |
| coding-debugging-003 | 1.000 | 0.000 | 0.264 |
| coding-debugging-004 | 1.000 | 0.000 | 0.260 |
| coding-debugging-005 | 1.000 | 0.000 | 0.241 |
| coding-debugging-006 | 1.000 | 0.000 | 0.248 |
| coding-debugging-007 | 1.000 | 0.000 | 0.241 |
| coding-debugging-008 | 1.000 | 0.000 | 0.251 |
| coding-debugging-009 | 1.000 | 0.000 | 0.243 |
| coding-debugging-010 | 1.000 | 0.000 | 0.241 |
| creative-productivity-001 | 1.000 | 0.000 | 0.229 |
| creative-productivity-002 | 1.000 | 0.000 | 0.232 |
| creative-productivity-003 | 1.000 | 0.000 | 0.231 |
| data-mlops-001 | 1.000 | 0.000 | 0.236 |
| data-mlops-002 | 1.000 | 0.000 | 0.235 |
| data-mlops-003 | 1.000 | 0.000 | 0.235 |
| data-mlops-004 | 1.000 | 0.000 | 0.218 |
| data-mlops-005 | 1.000 | 0.000 | 0.220 |
| data-mlops-006 | 1.000 | 0.000 | 0.221 |
| productivity-001 | 1.000 | 1.000 | 0.218 |
| productivity-002 | 1.000 | 0.000 | 0.244 |
| productivity-003 | 1.000 | 0.000 | 0.235 |
| research-writing-001 | 1.000 | 0.000 | 0.230 |
| research-writing-002 | 1.000 | 0.000 | 0.229 |
| research-writing-003 | 1.000 | 0.000 | 0.226 |
| research-writing-004 | 1.000 | 0.000 | 0.230 |
| research-writing-005 | 1.000 | 0.000 | 0.221 |
| research-writing-006 | 1.000 | 0.000 | 0.218 |
| research-writing-007 | 1.000 | 0.000 | 0.220 |
| research-writing-008 | 1.000 | 0.000 | 0.220 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| productivity-001 | apple-reminders, google-calendar, literature-review, songwriting-and-ai-music, citation-checking | apple-reminders | 1.000 | 1.000 |
