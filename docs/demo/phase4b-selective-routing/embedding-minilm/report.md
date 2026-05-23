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
| Accepted Count | 5.000 |
| Coverage | 1.000 |
| Selection Rate@5 | 1.000 |
| Abstention Rate | 0.000 |
| Accepted Recall@5 | 1.000 |
| Negative Accepted Rate | 0.033 |
| Average Latency (ms) | 29.598 |

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
| coding-debugging-001 | 1.000 | 0.000 | 121.539 |
| coding-debugging-002 | 1.000 | 1.000 | 40.841 |
| coding-debugging-003 | 1.000 | 0.000 | 41.578 |
| coding-debugging-004 | 1.000 | 0.000 | 41.856 |
| coding-debugging-005 | 1.000 | 0.000 | 41.134 |
| coding-debugging-006 | 1.000 | 0.000 | 10.362 |
| coding-debugging-007 | 1.000 | 0.000 | 41.270 |
| coding-debugging-008 | 1.000 | 0.000 | 9.521 |
| coding-debugging-009 | 1.000 | 0.000 | 46.655 |
| coding-debugging-010 | 1.000 | 0.000 | 43.306 |
| creative-productivity-001 | 1.000 | 0.000 | 10.184 |
| creative-productivity-002 | 1.000 | 0.000 | 46.634 |
| creative-productivity-003 | 1.000 | 0.000 | 9.826 |
| data-mlops-001 | 1.000 | 0.000 | 39.570 |
| data-mlops-002 | 1.000 | 0.000 | 10.215 |
| data-mlops-003 | 1.000 | 0.000 | 40.663 |
| data-mlops-004 | 1.000 | 0.000 | 41.271 |
| data-mlops-005 | 1.000 | 0.000 | 10.426 |
| data-mlops-006 | 1.000 | 0.000 | 14.892 |
| productivity-001 | 1.000 | 0.000 | 40.923 |
| productivity-002 | 1.000 | 0.000 | 41.807 |
| productivity-003 | 1.000 | 0.000 | 8.845 |
| research-writing-001 | 1.000 | 0.000 | 40.774 |
| research-writing-002 | 1.000 | 0.000 | 42.322 |
| research-writing-003 | 1.000 | 0.000 | 10.079 |
| research-writing-004 | 1.000 | 0.000 | 8.449 |
| research-writing-005 | 1.000 | 0.000 | 8.399 |
| research-writing-006 | 1.000 | 0.000 | 8.282 |
| research-writing-007 | 1.000 | 0.000 | 8.148 |
| research-writing-008 | 1.000 | 0.000 | 8.164 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| coding-debugging-002 | systematic-debugging, test-driven-development, songwriting-and-ai-music, ascii-art, docker | systematic-debugging | 1.000 | 1.000 |
