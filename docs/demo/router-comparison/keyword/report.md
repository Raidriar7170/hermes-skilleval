# Hermes SkillEval Report

- Router: keyword
- Records: 30

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 0.300 |
| Recall@3 | 0.367 |
| Recall@5 | 0.367 |
| Precision@5 | 0.087 |
| MRR | 0.350 |
| NDCG@5 | 0.354 |
| Negative Hit Rate | 0.400 |
| Average Latency (ms) | 0.031 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| test-driven-development | 30 |
| systematic-debugging | 30 |
| songwriting-and-ai-music | 30 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| coding-debugging-001 | 1.000 | 1.000 | 0.071 |
| coding-debugging-002 | 1.000 | 0.000 | 0.037 |
| coding-debugging-003 | 1.000 | 1.000 | 0.032 |
| coding-debugging-004 | 1.000 | 0.000 | 0.031 |
| coding-debugging-005 | 1.000 | 0.000 | 0.030 |
| coding-debugging-006 | 1.000 | 1.000 | 0.031 |
| coding-debugging-007 | 1.000 | 0.000 | 0.030 |
| coding-debugging-008 | 1.000 | 0.000 | 0.029 |
| coding-debugging-009 | 1.000 | 1.000 | 0.030 |
| coding-debugging-010 | 1.000 | 0.000 | 0.032 |
| creative-productivity-001 | 0.000 | 1.000 | 0.028 |
| creative-productivity-002 | 0.000 | 0.000 | 0.027 |
| creative-productivity-003 | 1.000 | 1.000 | 0.029 |
| data-mlops-001 | 0.000 | 1.000 | 0.028 |
| data-mlops-002 | 0.000 | 0.000 | 0.031 |
| data-mlops-003 | 0.000 | 0.000 | 0.029 |
| data-mlops-004 | 0.000 | 1.000 | 0.028 |
| data-mlops-005 | 0.000 | 0.000 | 0.028 |
| data-mlops-006 | 0.000 | 0.000 | 0.028 |
| productivity-001 | 0.000 | 0.000 | 0.027 |
| productivity-002 | 0.000 | 0.000 | 0.027 |
| productivity-003 | 0.000 | 0.000 | 0.027 |
| research-writing-001 | 0.000 | 1.000 | 0.028 |
| research-writing-002 | 0.000 | 1.000 | 0.027 |
| research-writing-003 | 0.000 | 0.000 | 0.028 |
| research-writing-004 | 0.000 | 0.000 | 0.028 |
| research-writing-005 | 0.000 | 1.000 | 0.028 |
| research-writing-006 | 0.000 | 1.000 | 0.029 |
| research-writing-007 | 0.000 | 0.000 | 0.028 |
| research-writing-008 | 0.000 | 0.000 | 0.028 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| coding-debugging-001 | test-driven-development, systematic-debugging, songwriting-and-ai-music | systematic-debugging, test-driven-development | 1.000 | 1.000 |
| coding-debugging-003 | test-driven-development, systematic-debugging, songwriting-and-ai-music | test-driven-development | 1.000 | 1.000 |
| coding-debugging-006 | test-driven-development, systematic-debugging, songwriting-and-ai-music | systematic-debugging | 1.000 | 1.000 |
| coding-debugging-009 | test-driven-development, systematic-debugging, songwriting-and-ai-music | test-driven-development | 1.000 | 1.000 |
| creative-productivity-001 | songwriting-and-ai-music, systematic-debugging, test-driven-development | ascii-art | 0.000 | 1.000 |
| creative-productivity-002 | songwriting-and-ai-music, systematic-debugging, test-driven-development | baoyu-comic | 0.000 | 0.000 |
| creative-productivity-003 | songwriting-and-ai-music, systematic-debugging, test-driven-development | songwriting-and-ai-music | 1.000 | 1.000 |
| data-mlops-001 | systematic-debugging, test-driven-development, songwriting-and-ai-music | data-analysis | 0.000 | 1.000 |
| data-mlops-002 | songwriting-and-ai-music, systematic-debugging, test-driven-development | mlflow | 0.000 | 0.000 |
| data-mlops-003 | systematic-debugging, test-driven-development, songwriting-and-ai-music | wandb | 0.000 | 0.000 |
| data-mlops-004 | songwriting-and-ai-music, systematic-debugging, test-driven-development | python-data-analysis | 0.000 | 1.000 |
| data-mlops-005 | songwriting-and-ai-music, systematic-debugging, test-driven-development | docker, mlflow | 0.000 | 0.000 |
| data-mlops-006 | systematic-debugging, test-driven-development, songwriting-and-ai-music | python-data-analysis | 0.000 | 0.000 |
| productivity-001 | songwriting-and-ai-music, systematic-debugging, test-driven-development | apple-reminders | 0.000 | 0.000 |
| productivity-002 | songwriting-and-ai-music, systematic-debugging, test-driven-development | google-calendar | 0.000 | 0.000 |
| productivity-003 | songwriting-and-ai-music, systematic-debugging, test-driven-development | note-taking | 0.000 | 0.000 |
| research-writing-001 | songwriting-and-ai-music, systematic-debugging, test-driven-development | research-paper-summary | 0.000 | 1.000 |
| research-writing-002 | songwriting-and-ai-music, systematic-debugging, test-driven-development | literature-review | 0.000 | 1.000 |
| research-writing-003 | systematic-debugging, test-driven-development, songwriting-and-ai-music | citation-checking | 0.000 | 0.000 |
| research-writing-004 | systematic-debugging, test-driven-development, songwriting-and-ai-music | academic-writing | 0.000 | 0.000 |
| research-writing-005 | songwriting-and-ai-music, systematic-debugging, test-driven-development | literature-review, citation-checking | 0.000 | 1.000 |
| research-writing-006 | systematic-debugging, test-driven-development, songwriting-and-ai-music | research-paper-summary | 0.000 | 1.000 |
| research-writing-007 | systematic-debugging, test-driven-development, songwriting-and-ai-music | academic-writing | 0.000 | 0.000 |
| research-writing-008 | songwriting-and-ai-music, systematic-debugging, test-driven-development | citation-checking | 0.000 | 0.000 |
