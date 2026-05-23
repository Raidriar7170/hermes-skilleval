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
| Average Latency (ms) | 0.204 |

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
| coding-debugging-001 | 1.000 | 0.000 | 0.277 |
| coding-debugging-002 | 1.000 | 0.000 | 0.239 |
| coding-debugging-003 | 1.000 | 0.000 | 0.221 |
| coding-debugging-004 | 1.000 | 0.000 | 0.212 |
| coding-debugging-005 | 1.000 | 0.000 | 0.201 |
| coding-debugging-006 | 1.000 | 0.000 | 0.203 |
| coding-debugging-007 | 1.000 | 0.000 | 0.199 |
| coding-debugging-008 | 1.000 | 0.000 | 0.202 |
| coding-debugging-009 | 1.000 | 0.000 | 0.195 |
| coding-debugging-010 | 1.000 | 0.000 | 0.197 |
| creative-productivity-001 | 1.000 | 0.000 | 0.194 |
| creative-productivity-002 | 1.000 | 0.000 | 0.194 |
| creative-productivity-003 | 1.000 | 0.000 | 0.201 |
| data-mlops-001 | 1.000 | 0.000 | 0.200 |
| data-mlops-002 | 1.000 | 0.000 | 0.198 |
| data-mlops-003 | 1.000 | 0.000 | 0.197 |
| data-mlops-004 | 1.000 | 0.000 | 0.197 |
| data-mlops-005 | 1.000 | 0.000 | 0.203 |
| data-mlops-006 | 1.000 | 0.000 | 0.208 |
| productivity-001 | 1.000 | 1.000 | 0.197 |
| productivity-002 | 1.000 | 0.000 | 0.211 |
| productivity-003 | 1.000 | 0.000 | 0.197 |
| research-writing-001 | 1.000 | 0.000 | 0.199 |
| research-writing-002 | 1.000 | 0.000 | 0.197 |
| research-writing-003 | 1.000 | 0.000 | 0.197 |
| research-writing-004 | 1.000 | 0.000 | 0.196 |
| research-writing-005 | 1.000 | 0.000 | 0.197 |
| research-writing-006 | 1.000 | 0.000 | 0.197 |
| research-writing-007 | 1.000 | 0.000 | 0.197 |
| research-writing-008 | 1.000 | 0.000 | 0.196 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| productivity-001 | apple-reminders, literature-review, songwriting-and-ai-music, citation-checking, google-calendar | apple-reminders | 1.000 | 1.000 |
