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
| Average Latency (ms) | 28.115 |

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
| coding-debugging-001 | 1.000 | 0.000 | 128.661 |
| coding-debugging-002 | 1.000 | 1.000 | 40.090 |
| coding-debugging-003 | 1.000 | 0.000 | 43.596 |
| coding-debugging-004 | 1.000 | 0.000 | 41.746 |
| coding-debugging-005 | 1.000 | 0.000 | 41.916 |
| coding-debugging-006 | 1.000 | 0.000 | 8.457 |
| coding-debugging-007 | 1.000 | 0.000 | 39.883 |
| coding-debugging-008 | 1.000 | 0.000 | 9.636 |
| coding-debugging-009 | 1.000 | 0.000 | 33.751 |
| coding-debugging-010 | 1.000 | 0.000 | 32.213 |
| creative-productivity-001 | 1.000 | 0.000 | 8.737 |
| creative-productivity-002 | 1.000 | 0.000 | 39.598 |
| creative-productivity-003 | 1.000 | 0.000 | 8.557 |
| data-mlops-001 | 1.000 | 0.000 | 35.316 |
| data-mlops-002 | 1.000 | 0.000 | 8.560 |
| data-mlops-003 | 1.000 | 0.000 | 41.391 |
| data-mlops-004 | 1.000 | 0.000 | 46.890 |
| data-mlops-005 | 1.000 | 0.000 | 7.194 |
| data-mlops-006 | 1.000 | 0.000 | 7.046 |
| productivity-001 | 1.000 | 0.000 | 40.491 |
| productivity-002 | 1.000 | 0.000 | 38.996 |
| productivity-003 | 1.000 | 0.000 | 8.518 |
| research-writing-001 | 1.000 | 0.000 | 40.890 |
| research-writing-002 | 1.000 | 0.000 | 43.345 |
| research-writing-003 | 1.000 | 0.000 | 8.413 |
| research-writing-004 | 1.000 | 0.000 | 8.263 |
| research-writing-005 | 1.000 | 0.000 | 8.216 |
| research-writing-006 | 1.000 | 0.000 | 7.705 |
| research-writing-007 | 1.000 | 0.000 | 7.614 |
| research-writing-008 | 1.000 | 0.000 | 7.745 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| coding-debugging-002 | systematic-debugging, test-driven-development, songwriting-and-ai-music, ascii-art, docker | systematic-debugging | 1.000 | 1.000 |
