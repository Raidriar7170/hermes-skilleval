# Hermes SkillEval Failure Analysis

## Failure Summary

| Router | Tasks | Top-1 Misses | Missing Gold@5 | Negative Hits@5 | Any Failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| embedding-minilm | 80 | 8 | 5 | 8 | 17 |
| gated-minilm-contrastive | 80 | 2 | 5 | 3 | 10 |
| gated-minilm-selective | 80 | 2 | 3 | 9 | 14 |

## Candidate vs Baseline

- Baseline: `gated-minilm-selective`
- Candidate: `gated-minilm-contrastive`

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Recall@1 | 0.881 | 0.881 | +0.000 |
| Recall@5 | 0.981 | 0.969 | -0.012 |
| MRR | 0.985 | 0.985 | +0.000 |
| NDCG@5 | 0.974 | 0.964 | -0.010 |
| Negative Hit Rate | 0.113 | 0.037 | +0.075 |
| Avg Latency ms | 7.968 | 13.249 | -5.281 |

## Candidate Task Changes

| Task ID | Change | Baseline Issues | Candidate Issues | Baseline Selected@5 | Candidate Selected@5 |
| --- | --- | --- | --- | --- | --- |
| infra-ops-008 | regressed | ok | missing-gold@5: model-serving | observability, model-serving, distributed-training, cuda-profiling | observability |
| research-writing-005 | regressed | ok | missing-gold@5: citation-checking | literature-review, citation-checking, research-paper-summary, academic-writing | literature-review |
| robustness-ambiguous-002 | improved | negative-hit@5: systematic-debugging | ok | test-driven-development, systematic-debugging | test-driven-development |
| robustness-ambiguous-004 | improved | negative-hit@5: mlflow | ok | wandb, mlflow, docker | wandb |
| robustness-ambiguous-005 | improved | negative-hit@5: literature-review | ok | citation-checking, research-paper-summary, academic-writing, literature-review | citation-checking, research-paper-summary |
| robustness-ambiguous-006 | improved | negative-hit@5: citation-checking | ok | literature-review, research-paper-summary, academic-writing, citation-checking | literature-review |
| robustness-ambiguous-008 | improved | negative-hit@5: python-data-analysis | ok | data-analysis, python-data-analysis | data-analysis |
| robustness-ambiguous-009 | improved | negative-hit@5: tool-planning | ok | skill-routing, tool-planning, verifier-gated-routing, context-management, self-improvement-harness | skill-routing |

## Failure Cases By Task

| Task ID | Category | Router | Issues | Gold Skills | Negative Skills | Selected@5 |
| --- | --- | --- | --- | --- | --- | --- |
| agent-workflows-008 | agent | embedding-minilm | missing-gold@5: error-analysis | self-improvement-harness, error-analysis | baoyu-comic | self-improvement-harness, verifier-gated-routing, skill-routing, systematic-debugging, tool-planning |
| agent-workflows-012 | agent | embedding-minilm | missing-gold@5: verifier-gated-routing; top1-miss | verifier-gated-routing | creative-ideation | skill-routing, tool-planning, prompt-engineering, self-improvement-harness, github-actions |
| coding-debugging-009 | coding | embedding-minilm | top1-miss | test-driven-development | songwriting-and-ai-music | systematic-debugging, test-driven-development, prompt-engineering, evaluation-suite-design, github-actions |
| data-mlops-006 | data-analysis | embedding-minilm | top1-miss | python-data-analysis | macos-computer-use | data-analysis, python-data-analysis, dataset-curation, wandb, evaluation-suite-design |
| infra-ops-001 | infra | embedding-minilm | top1-miss | github-actions | baoyu-comic | skill-routing, github-actions, self-improvement-harness, distributed-training, verifier-gated-routing |
| multimodal-asr-008 | multimodal | embedding-minilm | missing-gold@5: research-paper-summary | image-captioning, research-paper-summary | mlflow | image-captioning, multimodal-alignment, asr-evaluation, ascii-art, speech-transcription |
| research-writing-002 | research | embedding-minilm | missing-gold@5: literature-review; top1-miss | literature-review | songwriting-and-ai-music | skill-routing, self-improvement-harness, verifier-gated-routing, llm-judge-evaluation, prompt-engineering |
| retrieval-eval-005 | evaluation | embedding-minilm | top1-miss | dataset-curation | baoyu-comic | embedding-finetuning, dataset-curation, evaluation-suite-design, cross-encoder-reranking, skill-routing |
| retrieval-eval-011 | evaluation | embedding-minilm | missing-gold@5: dataset-curation; top1-miss | dataset-curation, evaluation-suite-design | macos-computer-use | skill-routing, verifier-gated-routing, self-improvement-harness, evaluation-suite-design, embedding-finetuning |
| robustness-ambiguous-001 | coding | embedding-minilm | negative-hit@5: test-driven-development | systematic-debugging | test-driven-development | systematic-debugging, test-driven-development, evaluation-suite-design, prompt-engineering, self-improvement-harness |
| robustness-ambiguous-002 | coding | embedding-minilm | negative-hit@5: systematic-debugging | test-driven-development | systematic-debugging | test-driven-development, systematic-debugging, evaluation-suite-design, prompt-engineering, self-improvement-harness |
| robustness-ambiguous-003 | mlops | embedding-minilm | negative-hit@5: wandb | mlflow | wandb | mlflow, wandb, observability, docker, systematic-debugging |
| robustness-ambiguous-004 | mlops | embedding-minilm | negative-hit@5: mlflow | wandb | mlflow | wandb, evaluation-suite-design, mlflow, systematic-debugging, error-analysis |
| robustness-ambiguous-007 | data-analysis | embedding-minilm | negative-hit@5: data-analysis | python-data-analysis | data-analysis | python-data-analysis, data-analysis, systematic-debugging, dataset-curation, observability |
| robustness-ambiguous-008 | data-analysis | embedding-minilm | negative-hit@5: python-data-analysis | data-analysis | python-data-analysis | data-analysis, systematic-debugging, evaluation-suite-design, python-data-analysis, cuda-profiling |
| robustness-ambiguous-009 | agent | embedding-minilm | negative-hit@5: tool-planning | skill-routing | tool-planning | skill-routing, tool-planning, prompt-engineering, self-improvement-harness, verifier-gated-routing |
| robustness-ambiguous-010 | agent | embedding-minilm | negative-hit@5: llm-judge-evaluation; top1-miss | verifier-gated-routing | llm-judge-evaluation | prompt-engineering, verifier-gated-routing, llm-judge-evaluation, skill-routing, self-improvement-harness |
| agent-workflows-006 | agent | gated-minilm-contrastive | top1-miss | prompt-engineering | cuda-profiling | tool-planning, prompt-engineering, context-management, self-improvement-harness, skill-routing |
| agent-workflows-008 | agent | gated-minilm-contrastive | missing-gold@5: error-analysis | self-improvement-harness, error-analysis | baoyu-comic | self-improvement-harness |
| agent-workflows-012 | agent | gated-minilm-contrastive | top1-miss | verifier-gated-routing | creative-ideation | skill-routing, tool-planning, verifier-gated-routing |
| infra-ops-008 | infra | gated-minilm-contrastive | missing-gold@5: model-serving | model-serving, observability | literature-review | observability |
| multimodal-asr-008 | multimodal | gated-minilm-contrastive | missing-gold@5: research-paper-summary | image-captioning, research-paper-summary | mlflow | image-captioning, asr-evaluation, speech-transcription, audio-preprocessing |
| research-writing-005 | research | gated-minilm-contrastive | missing-gold@5: citation-checking | literature-review, citation-checking | songwriting-and-ai-music | literature-review |
| retrieval-eval-009 | retrieval | gated-minilm-contrastive | missing-gold@5: citation-checking | rag, citation-checking | prompt-engineering | rag, embedding-finetuning, vector-search, cross-encoder-reranking |
| robustness-ambiguous-001 | coding | gated-minilm-contrastive | negative-hit@5: test-driven-development | systematic-debugging | test-driven-development | systematic-debugging, test-driven-development |
| robustness-ambiguous-003 | mlops | gated-minilm-contrastive | negative-hit@5: wandb | mlflow | wandb | mlflow, wandb |
| robustness-ambiguous-007 | data-analysis | gated-minilm-contrastive | negative-hit@5: data-analysis | python-data-analysis | data-analysis | python-data-analysis, data-analysis |
| agent-workflows-006 | agent | gated-minilm-selective | top1-miss | prompt-engineering | cuda-profiling | tool-planning, prompt-engineering, context-management, self-improvement-harness, skill-routing |
| agent-workflows-008 | agent | gated-minilm-selective | missing-gold@5: error-analysis | self-improvement-harness, error-analysis | baoyu-comic | self-improvement-harness, skill-routing, tool-planning, verifier-gated-routing, context-management |
| agent-workflows-012 | agent | gated-minilm-selective | top1-miss | verifier-gated-routing | creative-ideation | skill-routing, tool-planning, verifier-gated-routing, prompt-engineering, self-improvement-harness |
| multimodal-asr-008 | multimodal | gated-minilm-selective | missing-gold@5: research-paper-summary | image-captioning, research-paper-summary | mlflow | image-captioning, asr-evaluation, speech-transcription, audio-preprocessing, multimodal-alignment |
| retrieval-eval-009 | retrieval | gated-minilm-selective | missing-gold@5: citation-checking | rag, citation-checking | prompt-engineering | rag, embedding-finetuning, vector-search, cross-encoder-reranking |
| robustness-ambiguous-001 | coding | gated-minilm-selective | negative-hit@5: test-driven-development | systematic-debugging | test-driven-development | systematic-debugging, test-driven-development |
| robustness-ambiguous-002 | coding | gated-minilm-selective | negative-hit@5: systematic-debugging | test-driven-development | systematic-debugging | test-driven-development, systematic-debugging |
| robustness-ambiguous-003 | mlops | gated-minilm-selective | negative-hit@5: wandb | mlflow | wandb | mlflow, wandb, docker |
| robustness-ambiguous-004 | mlops | gated-minilm-selective | negative-hit@5: mlflow | wandb | mlflow | wandb, mlflow, docker |
| robustness-ambiguous-005 | research | gated-minilm-selective | negative-hit@5: literature-review | citation-checking | literature-review | citation-checking, research-paper-summary, academic-writing, literature-review |
| robustness-ambiguous-006 | research | gated-minilm-selective | negative-hit@5: citation-checking | literature-review | citation-checking | literature-review, research-paper-summary, academic-writing, citation-checking |
| robustness-ambiguous-007 | data-analysis | gated-minilm-selective | negative-hit@5: data-analysis | python-data-analysis | data-analysis | python-data-analysis, data-analysis |
| robustness-ambiguous-008 | data-analysis | gated-minilm-selective | negative-hit@5: python-data-analysis | data-analysis | python-data-analysis | data-analysis, python-data-analysis |
| robustness-ambiguous-009 | agent | gated-minilm-selective | negative-hit@5: tool-planning | skill-routing | tool-planning | skill-routing, tool-planning, verifier-gated-routing, context-management, self-improvement-harness |
