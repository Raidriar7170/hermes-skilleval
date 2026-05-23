# Hermes SkillEval Report

- Router: gated-minilm
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
| Average Latency (ms) | 8.202 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| wandb | 17 |
| systematic-debugging | 16 |
| research-paper-summary | 15 |
| test-driven-development | 10 |
| academic-writing | 10 |
| mlflow | 10 |
| docker | 9 |
| literature-review | 9 |
| citation-checking | 8 |
| python-data-analysis | 7 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| coding-debugging-001 | 1.000 | 0.000 | 17.232 |
| coding-debugging-002 | 1.000 | 1.000 | 12.335 |
| coding-debugging-003 | 1.000 | 0.000 | 10.703 |
| coding-debugging-004 | 1.000 | 0.000 | 9.426 |
| coding-debugging-005 | 1.000 | 0.000 | 8.667 |
| coding-debugging-006 | 1.000 | 0.000 | 7.276 |
| coding-debugging-007 | 1.000 | 0.000 | 8.168 |
| coding-debugging-008 | 1.000 | 0.000 | 6.704 |
| coding-debugging-009 | 1.000 | 0.000 | 7.709 |
| coding-debugging-010 | 1.000 | 0.000 | 7.839 |
| creative-productivity-001 | 1.000 | 0.000 | 6.388 |
| creative-productivity-002 | 1.000 | 0.000 | 7.409 |
| creative-productivity-003 | 1.000 | 0.000 | 5.883 |
| data-mlops-001 | 1.000 | 0.000 | 7.724 |
| data-mlops-002 | 1.000 | 0.000 | 6.194 |
| data-mlops-003 | 1.000 | 0.000 | 7.062 |
| data-mlops-004 | 1.000 | 0.000 | 8.599 |
| data-mlops-005 | 1.000 | 0.000 | 6.717 |
| data-mlops-006 | 1.000 | 0.000 | 5.886 |
| productivity-001 | 1.000 | 0.000 | 7.458 |
| productivity-002 | 1.000 | 0.000 | 7.682 |
| productivity-003 | 1.000 | 0.000 | 5.793 |
| research-writing-001 | 1.000 | 0.000 | 8.527 |
| research-writing-002 | 1.000 | 0.000 | 8.962 |
| research-writing-003 | 1.000 | 0.000 | 6.558 |
| research-writing-004 | 1.000 | 0.000 | 8.730 |
| research-writing-005 | 1.000 | 0.000 | 10.945 |
| research-writing-006 | 1.000 | 0.000 | 9.494 |
| research-writing-007 | 1.000 | 0.000 | 7.217 |
| research-writing-008 | 1.000 | 0.000 | 6.765 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| coding-debugging-002 | systematic-debugging, test-driven-development, mlflow, wandb, ascii-art | systematic-debugging | 1.000 | 1.000 |
