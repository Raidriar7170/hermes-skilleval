# Hermes SkillEval Report

- Router: keyword
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
| Average Latency (ms) | 0.215 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| academic-writing | 17 |
| research-paper-summary | 16 |
| wandb | 14 |
| systematic-debugging | 12 |
| mlflow | 9 |
| docker | 9 |
| songwriting-and-ai-music | 9 |
| literature-review | 9 |
| test-driven-development | 8 |
| apple-reminders | 7 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| coding-debugging-001 | 1.000 | 0.000 | 0.282 |
| coding-debugging-002 | 1.000 | 0.000 | 0.224 |
| coding-debugging-003 | 1.000 | 0.000 | 0.209 |
| coding-debugging-004 | 1.000 | 0.000 | 0.202 |
| coding-debugging-005 | 1.000 | 0.000 | 0.201 |
| coding-debugging-006 | 1.000 | 0.000 | 0.215 |
| coding-debugging-007 | 1.000 | 0.000 | 0.200 |
| coding-debugging-008 | 1.000 | 0.000 | 0.208 |
| coding-debugging-009 | 1.000 | 0.000 | 0.196 |
| coding-debugging-010 | 1.000 | 0.000 | 0.201 |
| creative-productivity-001 | 1.000 | 0.000 | 0.199 |
| creative-productivity-002 | 1.000 | 0.000 | 0.194 |
| creative-productivity-003 | 1.000 | 0.000 | 0.198 |
| data-mlops-001 | 1.000 | 0.000 | 0.198 |
| data-mlops-002 | 1.000 | 0.000 | 0.198 |
| data-mlops-003 | 1.000 | 0.000 | 0.197 |
| data-mlops-004 | 1.000 | 0.000 | 0.199 |
| data-mlops-005 | 1.000 | 0.000 | 0.206 |
| data-mlops-006 | 1.000 | 0.000 | 0.197 |
| productivity-001 | 1.000 | 1.000 | 0.197 |
| productivity-002 | 1.000 | 0.000 | 0.207 |
| productivity-003 | 1.000 | 0.000 | 0.501 |
| research-writing-001 | 1.000 | 0.000 | 0.209 |
| research-writing-002 | 1.000 | 0.000 | 0.202 |
| research-writing-003 | 1.000 | 0.000 | 0.209 |
| research-writing-004 | 1.000 | 0.000 | 0.198 |
| research-writing-005 | 1.000 | 0.000 | 0.200 |
| research-writing-006 | 1.000 | 0.000 | 0.204 |
| research-writing-007 | 1.000 | 0.000 | 0.197 |
| research-writing-008 | 1.000 | 0.000 | 0.197 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| productivity-001 | apple-reminders, literature-review, songwriting-and-ai-music, citation-checking, google-calendar | apple-reminders | 1.000 | 1.000 |
