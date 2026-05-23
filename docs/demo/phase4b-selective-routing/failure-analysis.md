# Hermes SkillEval Failure Analysis

## Failure Summary

| Router | Tasks | Top-1 Misses | Missing Gold@5 | Negative Hits@5 | Any Failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| embedding-minilm | 30 | 2 | 0 | 1 | 3 |
| gated-minilm-selective | 30 | 0 | 0 | 0 | 0 |
| hybrid | 30 | 0 | 0 | 1 | 1 |
| keyword | 30 | 0 | 0 | 1 | 1 |

## Candidate vs Baseline

- Baseline: `embedding-minilm`
- Candidate: `gated-minilm-selective`

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Recall@1 | 0.867 | 0.933 | +0.067 |
| Recall@5 | 1.000 | 1.000 | +0.000 |
| MRR | 0.967 | 1.000 | +0.033 |
| NDCG@5 | 0.973 | 1.000 | +0.027 |
| Negative Hit Rate | 0.033 | 0.000 | +0.033 |
| Avg Latency ms | 29.598 | 9.995 | +19.603 |

## Candidate Task Changes

| Task ID | Change | Baseline Issues | Candidate Issues | Baseline Selected@5 | Candidate Selected@5 |
| --- | --- | --- | --- | --- | --- |
| coding-debugging-002 | improved | negative-hit@5: ascii-art | ok | systematic-debugging, test-driven-development, songwriting-and-ai-music, ascii-art, docker | systematic-debugging, test-driven-development |
| coding-debugging-009 | improved | top1-miss | ok | systematic-debugging, test-driven-development, wandb, citation-checking, docker | test-driven-development, systematic-debugging |
| data-mlops-006 | improved | top1-miss | ok | data-analysis, python-data-analysis, wandb, systematic-debugging, research-paper-summary | python-data-analysis, data-analysis |

## Failure Cases By Task

| Task ID | Category | Router | Issues | Gold Skills | Negative Skills | Selected@5 |
| --- | --- | --- | --- | --- | --- | --- |
| coding-debugging-002 | coding | embedding-minilm | negative-hit@5: ascii-art | systematic-debugging | ascii-art | systematic-debugging, test-driven-development, songwriting-and-ai-music, ascii-art, docker |
| coding-debugging-009 | coding | embedding-minilm | top1-miss | test-driven-development | songwriting-and-ai-music | systematic-debugging, test-driven-development, wandb, citation-checking, docker |
| data-mlops-006 | data-analysis | embedding-minilm | top1-miss | python-data-analysis | macos-computer-use | data-analysis, python-data-analysis, wandb, systematic-debugging, research-paper-summary |
| productivity-001 | productivity | hybrid | negative-hit@5: citation-checking | apple-reminders | citation-checking | apple-reminders, google-calendar, literature-review, songwriting-and-ai-music, citation-checking |
| productivity-001 | productivity | keyword | negative-hit@5: citation-checking | apple-reminders | citation-checking | apple-reminders, literature-review, songwriting-and-ai-music, citation-checking, google-calendar |
