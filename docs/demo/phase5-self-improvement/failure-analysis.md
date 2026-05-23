# Hermes SkillEval Failure Analysis

## Failure Summary

| Router | Tasks | Top-1 Misses | Missing Gold@5 | Negative Hits@5 | Any Failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| embedding-minilm-before | 30 | 2 | 0 | 1 | 3 |
| embedding-minilm-patched | 30 | 0 | 0 | 1 | 1 |

## Candidate vs Baseline

- Baseline: `embedding-minilm-before`
- Candidate: `embedding-minilm-patched`

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Recall@1 | 0.867 | 0.933 | +0.067 |
| Recall@5 | 1.000 | 1.000 | +0.000 |
| MRR | 0.967 | 1.000 | +0.033 |
| NDCG@5 | 0.973 | 1.000 | +0.027 |
| Negative Hit Rate | 0.033 | 0.033 | -0.000 |
| Avg Latency ms | 29.598 | 27.319 | +2.279 |

## Candidate Task Changes

| Task ID | Change | Baseline Issues | Candidate Issues | Baseline Selected@5 | Candidate Selected@5 |
| --- | --- | --- | --- | --- | --- |
| coding-debugging-009 | improved | top1-miss | ok | systematic-debugging, test-driven-development, wandb, citation-checking, docker | test-driven-development, systematic-debugging, wandb, citation-checking, docker |
| data-mlops-006 | improved | top1-miss | ok | data-analysis, python-data-analysis, wandb, systematic-debugging, research-paper-summary | python-data-analysis, data-analysis, wandb, mlflow, systematic-debugging |

## Failure Cases By Task

| Task ID | Category | Router | Issues | Gold Skills | Negative Skills | Selected@5 |
| --- | --- | --- | --- | --- | --- | --- |
| coding-debugging-002 | coding | embedding-minilm-before | negative-hit@5: ascii-art | systematic-debugging | ascii-art | systematic-debugging, test-driven-development, songwriting-and-ai-music, ascii-art, docker |
| coding-debugging-009 | coding | embedding-minilm-before | top1-miss | test-driven-development | songwriting-and-ai-music | systematic-debugging, test-driven-development, wandb, citation-checking, docker |
| data-mlops-006 | data-analysis | embedding-minilm-before | top1-miss | python-data-analysis | macos-computer-use | data-analysis, python-data-analysis, wandb, systematic-debugging, research-paper-summary |
| coding-debugging-002 | coding | embedding-minilm-patched | negative-hit@5: ascii-art | systematic-debugging | ascii-art | systematic-debugging, test-driven-development, songwriting-and-ai-music, ascii-art, docker |
