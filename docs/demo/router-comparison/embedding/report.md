# Hermes SkillEval Report

- Router: embedding
- Records: 30

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 0.233 |
| Recall@3 | 0.367 |
| Recall@5 | 0.367 |
| Precision@5 | 0.087 |
| MRR | 0.317 |
| NDCG@5 | 0.327 |
| Negative Hit Rate | 0.400 |
| Average Latency (ms) | 0.168 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| test-driven-development | 30 |
| systematic-debugging | 30 |
| songwriting-and-ai-music | 30 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| coding-debugging-001 | 1.000 | 1.000 | 0.214 |
| coding-debugging-002 | 1.000 | 0.000 | 0.191 |
| coding-debugging-003 | 1.000 | 1.000 | 0.178 |
| coding-debugging-004 | 1.000 | 0.000 | 0.179 |
| coding-debugging-005 | 1.000 | 0.000 | 0.172 |
| coding-debugging-006 | 1.000 | 1.000 | 0.187 |
| coding-debugging-007 | 1.000 | 0.000 | 0.172 |
| coding-debugging-008 | 1.000 | 0.000 | 0.174 |
| coding-debugging-009 | 1.000 | 1.000 | 0.163 |
| coding-debugging-010 | 1.000 | 0.000 | 0.169 |
| creative-productivity-001 | 0.000 | 1.000 | 0.161 |
| creative-productivity-002 | 0.000 | 0.000 | 0.162 |
| creative-productivity-003 | 1.000 | 1.000 | 0.164 |
| data-mlops-001 | 0.000 | 1.000 | 0.167 |
| data-mlops-002 | 0.000 | 0.000 | 0.167 |
| data-mlops-003 | 0.000 | 0.000 | 0.167 |
| data-mlops-004 | 0.000 | 1.000 | 0.164 |
| data-mlops-005 | 0.000 | 0.000 | 0.163 |
| data-mlops-006 | 0.000 | 0.000 | 0.165 |
| productivity-001 | 0.000 | 0.000 | 0.158 |
| productivity-002 | 0.000 | 0.000 | 0.164 |
| productivity-003 | 0.000 | 0.000 | 0.162 |
| research-writing-001 | 0.000 | 1.000 | 0.160 |
| research-writing-002 | 0.000 | 1.000 | 0.158 |
| research-writing-003 | 0.000 | 0.000 | 0.159 |
| research-writing-004 | 0.000 | 0.000 | 0.161 |
| research-writing-005 | 0.000 | 1.000 | 0.159 |
| research-writing-006 | 0.000 | 1.000 | 0.159 |
| research-writing-007 | 0.000 | 0.000 | 0.159 |
| research-writing-008 | 0.000 | 0.000 | 0.160 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| coding-debugging-001 | test-driven-development, systematic-debugging, songwriting-and-ai-music | systematic-debugging, test-driven-development | 1.000 | 1.000 |
| coding-debugging-003 | test-driven-development, systematic-debugging, songwriting-and-ai-music | test-driven-development | 1.000 | 1.000 |
| coding-debugging-006 | systematic-debugging, test-driven-development, songwriting-and-ai-music | systematic-debugging | 1.000 | 1.000 |
| coding-debugging-009 | systematic-debugging, test-driven-development, songwriting-and-ai-music | test-driven-development | 1.000 | 1.000 |
| creative-productivity-001 | songwriting-and-ai-music, test-driven-development, systematic-debugging | ascii-art | 0.000 | 1.000 |
| creative-productivity-002 | songwriting-and-ai-music, systematic-debugging, test-driven-development | baoyu-comic | 0.000 | 0.000 |
| creative-productivity-003 | test-driven-development, songwriting-and-ai-music, systematic-debugging | songwriting-and-ai-music | 1.000 | 1.000 |
| data-mlops-001 | songwriting-and-ai-music, systematic-debugging, test-driven-development | data-analysis | 0.000 | 1.000 |
| data-mlops-002 | test-driven-development, songwriting-and-ai-music, systematic-debugging | mlflow | 0.000 | 0.000 |
| data-mlops-003 | test-driven-development, songwriting-and-ai-music, systematic-debugging | wandb | 0.000 | 0.000 |
| data-mlops-004 | songwriting-and-ai-music, systematic-debugging, test-driven-development | python-data-analysis | 0.000 | 1.000 |
| data-mlops-005 | songwriting-and-ai-music, systematic-debugging, test-driven-development | docker, mlflow | 0.000 | 0.000 |
| data-mlops-006 | songwriting-and-ai-music, systematic-debugging, test-driven-development | python-data-analysis | 0.000 | 0.000 |
| productivity-001 | songwriting-and-ai-music, systematic-debugging, test-driven-development | apple-reminders | 0.000 | 0.000 |
| productivity-002 | systematic-debugging, test-driven-development, songwriting-and-ai-music | google-calendar | 0.000 | 0.000 |
| productivity-003 | test-driven-development, songwriting-and-ai-music, systematic-debugging | note-taking | 0.000 | 0.000 |
| research-writing-001 | songwriting-and-ai-music, test-driven-development, systematic-debugging | research-paper-summary | 0.000 | 1.000 |
| research-writing-002 | songwriting-and-ai-music, systematic-debugging, test-driven-development | literature-review | 0.000 | 1.000 |
| research-writing-003 | songwriting-and-ai-music, systematic-debugging, test-driven-development | citation-checking | 0.000 | 0.000 |
| research-writing-004 | songwriting-and-ai-music, systematic-debugging, test-driven-development | academic-writing | 0.000 | 0.000 |
| research-writing-005 | songwriting-and-ai-music, systematic-debugging, test-driven-development | literature-review, citation-checking | 0.000 | 1.000 |
| research-writing-006 | systematic-debugging, songwriting-and-ai-music, test-driven-development | research-paper-summary | 0.000 | 1.000 |
| research-writing-007 | systematic-debugging, test-driven-development, songwriting-and-ai-music | academic-writing | 0.000 | 0.000 |
| research-writing-008 | systematic-debugging, songwriting-and-ai-music, test-driven-development | citation-checking | 0.000 | 0.000 |
