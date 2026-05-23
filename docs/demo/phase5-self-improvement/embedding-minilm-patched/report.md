# Hermes SkillEval Report

- Router: embedding
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
| Average Latency (ms) | 27.319 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| systematic-debugging | 17 |
| wandb | 15 |
| mlflow | 11 |
| literature-review | 11 |
| test-driven-development | 10 |
| python-data-analysis | 10 |
| citation-checking | 10 |
| docker | 10 |
| note-taking | 9 |
| research-paper-summary | 9 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| coding-debugging-001 | 1.000 | 0.000 | 120.918 |
| coding-debugging-002 | 1.000 | 1.000 | 56.823 |
| coding-debugging-003 | 1.000 | 0.000 | 39.973 |
| coding-debugging-004 | 1.000 | 0.000 | 40.908 |
| coding-debugging-005 | 1.000 | 0.000 | 43.063 |
| coding-debugging-006 | 1.000 | 0.000 | 7.856 |
| coding-debugging-007 | 1.000 | 0.000 | 39.523 |
| coding-debugging-008 | 1.000 | 0.000 | 8.800 |
| coding-debugging-009 | 1.000 | 0.000 | 40.935 |
| coding-debugging-010 | 1.000 | 0.000 | 34.906 |
| creative-productivity-001 | 1.000 | 0.000 | 8.528 |
| creative-productivity-002 | 1.000 | 0.000 | 33.851 |
| creative-productivity-003 | 1.000 | 0.000 | 7.703 |
| data-mlops-001 | 1.000 | 0.000 | 39.668 |
| data-mlops-002 | 1.000 | 0.000 | 8.412 |
| data-mlops-003 | 1.000 | 0.000 | 34.898 |
| data-mlops-004 | 1.000 | 0.000 | 36.713 |
| data-mlops-005 | 1.000 | 0.000 | 7.017 |
| data-mlops-006 | 1.000 | 0.000 | 7.147 |
| productivity-001 | 1.000 | 0.000 | 35.589 |
| productivity-002 | 1.000 | 0.000 | 37.754 |
| productivity-003 | 1.000 | 0.000 | 7.856 |
| research-writing-001 | 1.000 | 0.000 | 37.587 |
| research-writing-002 | 1.000 | 0.000 | 36.777 |
| research-writing-003 | 1.000 | 0.000 | 8.981 |
| research-writing-004 | 1.000 | 0.000 | 8.584 |
| research-writing-005 | 1.000 | 0.000 | 8.314 |
| research-writing-006 | 1.000 | 0.000 | 7.360 |
| research-writing-007 | 1.000 | 0.000 | 6.907 |
| research-writing-008 | 1.000 | 0.000 | 6.225 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| coding-debugging-002 | systematic-debugging, test-driven-development, songwriting-and-ai-music, ascii-art, docker | systematic-debugging | 1.000 | 1.000 |
