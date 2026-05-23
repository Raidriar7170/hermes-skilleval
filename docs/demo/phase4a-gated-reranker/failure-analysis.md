# Hermes SkillEval Failure Analysis

## Failure Summary

| Router | Tasks | Top-1 Misses | Missing Gold@5 | Negative Hits@5 | Any Failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| embedding-hashing | 30 | 7 | 2 | 3 | 11 |
| embedding-minilm | 30 | 2 | 0 | 1 | 3 |
| gated-minilm | 30 | 0 | 0 | 1 | 1 |
| hybrid | 30 | 0 | 0 | 1 | 1 |
| keyword | 30 | 0 | 0 | 1 | 1 |

## Candidate vs Baseline

- Baseline: `embedding-minilm`
- Candidate: `gated-minilm`

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Recall@1 | 0.867 | 0.933 | +0.067 |
| Recall@5 | 1.000 | 1.000 | +0.000 |
| MRR | 0.967 | 1.000 | +0.033 |
| NDCG@5 | 0.973 | 1.000 | +0.027 |
| Negative Hit Rate | 0.033 | 0.033 | -0.000 |
| Avg Latency ms | 23.163 | 8.202 | +14.962 |

## Candidate Task Changes

| Task ID | Change | Baseline Issues | Candidate Issues | Baseline Selected@5 | Candidate Selected@5 |
| --- | --- | --- | --- | --- | --- |
| coding-debugging-009 | improved | top1-miss | ok | systematic-debugging, test-driven-development, wandb, citation-checking, docker | test-driven-development, systematic-debugging, wandb, citation-checking, docker |
| data-mlops-006 | improved | top1-miss | ok | data-analysis, python-data-analysis, wandb, systematic-debugging, research-paper-summary | python-data-analysis, data-analysis, wandb, research-paper-summary, systematic-debugging |

## Failure Cases By Task

| Task ID | Category | Router | Issues | Gold Skills | Negative Skills | Selected@5 |
| --- | --- | --- | --- | --- | --- | --- |
| coding-debugging-002 | coding | embedding-hashing | top1-miss | systematic-debugging | ascii-art | test-driven-development, systematic-debugging, mlflow, academic-writing, wandb |
| coding-debugging-004 | coding | embedding-hashing | top1-miss | systematic-debugging | creative-ideation | wandb, academic-writing, citation-checking, mlflow, systematic-debugging |
| coding-debugging-005 | coding | embedding-hashing | top1-miss | test-driven-development | baoyu-comic | systematic-debugging, test-driven-development, data-analysis, research-paper-summary, note-taking |
| coding-debugging-006 | coding | embedding-hashing | negative-hit@5: songwriting-and-ai-music | systematic-debugging | songwriting-and-ai-music | systematic-debugging, academic-writing, songwriting-and-ai-music, citation-checking, apple-reminders |
| coding-debugging-007 | coding | embedding-hashing | missing-gold@5: systematic-debugging | test-driven-development, systematic-debugging | ascii-art | test-driven-development, research-paper-summary, wandb, citation-checking, songwriting-and-ai-music |
| coding-debugging-008 | coding | embedding-hashing | top1-miss | systematic-debugging | popular-web-designs | mlflow, systematic-debugging, docker, citation-checking, wandb |
| coding-debugging-009 | coding | embedding-hashing | negative-hit@5: songwriting-and-ai-music | test-driven-development | songwriting-and-ai-music | test-driven-development, systematic-debugging, songwriting-and-ai-music, baoyu-comic, data-analysis |
| creative-productivity-003 | creative | embedding-hashing | top1-miss | songwriting-and-ai-music | test-driven-development | creative-ideation, songwriting-and-ai-music, docker, systematic-debugging, apple-reminders |
| data-mlops-006 | data-analysis | embedding-hashing | top1-miss | python-data-analysis | macos-computer-use | data-analysis, python-data-analysis, songwriting-and-ai-music, academic-writing, mlflow |
| productivity-003 | productivity | embedding-hashing | negative-hit@5: docker | note-taking | docker | note-taking, docker, creative-ideation, google-calendar, baoyu-comic |
| research-writing-005 | research | embedding-hashing | missing-gold@5: citation-checking; top1-miss | literature-review, citation-checking | songwriting-and-ai-music | academic-writing, literature-review, note-taking, google-calendar, apple-reminders |
| coding-debugging-002 | coding | embedding-minilm | negative-hit@5: ascii-art | systematic-debugging | ascii-art | systematic-debugging, test-driven-development, songwriting-and-ai-music, ascii-art, docker |
| coding-debugging-009 | coding | embedding-minilm | top1-miss | test-driven-development | songwriting-and-ai-music | systematic-debugging, test-driven-development, wandb, citation-checking, docker |
| data-mlops-006 | data-analysis | embedding-minilm | top1-miss | python-data-analysis | macos-computer-use | data-analysis, python-data-analysis, wandb, systematic-debugging, research-paper-summary |
| coding-debugging-002 | coding | gated-minilm | negative-hit@5: ascii-art | systematic-debugging | ascii-art | systematic-debugging, test-driven-development, mlflow, wandb, ascii-art |
| productivity-001 | productivity | hybrid | negative-hit@5: citation-checking | apple-reminders | citation-checking | apple-reminders, google-calendar, literature-review, songwriting-and-ai-music, citation-checking |
| productivity-001 | productivity | keyword | negative-hit@5: citation-checking | apple-reminders | citation-checking | apple-reminders, literature-review, songwriting-and-ai-music, citation-checking, google-calendar |
