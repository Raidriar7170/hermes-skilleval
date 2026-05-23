# Hermes SkillEval Report

- Router: embedding-hashing
- Records: 30

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 0.717 |
| Recall@3 | 0.933 |
| Recall@5 | 0.967 |
| Precision@5 | 0.213 |
| MRR | 0.873 |
| NDCG@5 | 0.882 |
| Negative Hit Rate | 0.100 |
| Average Latency (ms) | 0.396 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| mlflow | 15 |
| academic-writing | 14 |
| research-paper-summary | 14 |
| wandb | 12 |
| data-analysis | 11 |
| songwriting-and-ai-music | 11 |
| systematic-debugging | 10 |
| docker | 8 |
| literature-review | 8 |
| test-driven-development | 6 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| coding-debugging-001 | 1.000 | 0.000 | 0.524 |
| coding-debugging-002 | 1.000 | 0.000 | 0.415 |
| coding-debugging-003 | 1.000 | 0.000 | 0.400 |
| coding-debugging-004 | 1.000 | 0.000 | 0.393 |
| coding-debugging-005 | 1.000 | 0.000 | 0.385 |
| coding-debugging-006 | 1.000 | 1.000 | 0.387 |
| coding-debugging-007 | 0.500 | 0.000 | 0.396 |
| coding-debugging-008 | 1.000 | 0.000 | 0.386 |
| coding-debugging-009 | 1.000 | 1.000 | 0.381 |
| coding-debugging-010 | 1.000 | 0.000 | 0.388 |
| creative-productivity-001 | 1.000 | 0.000 | 0.384 |
| creative-productivity-002 | 1.000 | 0.000 | 0.466 |
| creative-productivity-003 | 1.000 | 0.000 | 0.400 |
| data-mlops-001 | 1.000 | 0.000 | 0.400 |
| data-mlops-002 | 1.000 | 0.000 | 0.389 |
| data-mlops-003 | 1.000 | 0.000 | 0.387 |
| data-mlops-004 | 1.000 | 0.000 | 0.383 |
| data-mlops-005 | 1.000 | 0.000 | 0.381 |
| data-mlops-006 | 1.000 | 0.000 | 0.379 |
| productivity-001 | 1.000 | 0.000 | 0.423 |
| productivity-002 | 1.000 | 0.000 | 0.418 |
| productivity-003 | 1.000 | 1.000 | 0.390 |
| research-writing-001 | 1.000 | 0.000 | 0.380 |
| research-writing-002 | 1.000 | 0.000 | 0.378 |
| research-writing-003 | 1.000 | 0.000 | 0.383 |
| research-writing-004 | 1.000 | 0.000 | 0.373 |
| research-writing-005 | 0.500 | 0.000 | 0.371 |
| research-writing-006 | 1.000 | 0.000 | 0.385 |
| research-writing-007 | 1.000 | 0.000 | 0.385 |
| research-writing-008 | 1.000 | 0.000 | 0.382 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| coding-debugging-006 | systematic-debugging, academic-writing, songwriting-and-ai-music, citation-checking, apple-reminders | systematic-debugging | 1.000 | 1.000 |
| coding-debugging-009 | test-driven-development, systematic-debugging, songwriting-and-ai-music, baoyu-comic, data-analysis | test-driven-development | 1.000 | 1.000 |
| productivity-003 | note-taking, docker, creative-ideation, google-calendar, baoyu-comic | note-taking | 1.000 | 1.000 |
