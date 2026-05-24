# Hermes SkillEval Failure Analysis

## Failure Summary

| Router | Tasks | Top-1 Misses | Missing Gold@5 | Negative Hits@5 | Any Failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| cross-encoder-minilm | 80 | 13 | 22 | 0 | 22 |
| embedding-minilm | 80 | 8 | 5 | 8 | 17 |
| gated-minilm-contrastive | 80 | 2 | 5 | 3 | 10 |

## Candidate vs Baseline

- Baseline: `gated-minilm-contrastive`
- Candidate: `cross-encoder-minilm`

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Recall@1 | 0.881 | 0.775 | -0.106 |
| Recall@5 | 0.969 | 0.781 | -0.188 |
| MRR | 0.985 | 0.838 | -0.148 |
| NDCG@5 | 0.964 | 0.794 | -0.170 |
| Negative Hit Rate | 0.037 | 0.000 | +0.037 |
| Avg Latency ms | 10.711 | 18.222 | -7.512 |

## Candidate Task Changes

| Task ID | Change | Baseline Issues | Candidate Issues | Baseline Selected@5 | Candidate Selected@5 |
| --- | --- | --- | --- | --- | --- |
| agent-workflows-006 | improved | top1-miss | ok | tool-planning, prompt-engineering, context-management, self-improvement-harness, skill-routing | prompt-engineering |
| agent-workflows-007 | regressed | ok | missing-gold@5: skill-routing | verifier-gated-routing, skill-routing, context-management, tool-planning, self-improvement-harness | verifier-gated-routing |
| agent-workflows-012 | trade-off | top1-miss | missing-gold@5: verifier-gated-routing; top1-miss | skill-routing, tool-planning, verifier-gated-routing |  |
| coding-debugging-001 | regressed | ok | missing-gold@5: test-driven-development | systematic-debugging, test-driven-development | systematic-debugging |
| coding-debugging-002 | regressed | ok | missing-gold@5: systematic-debugging; top1-miss | systematic-debugging, test-driven-development |  |
| coding-debugging-004 | regressed | ok | missing-gold@5: systematic-debugging; top1-miss | systematic-debugging |  |
| coding-debugging-007 | regressed | ok | missing-gold@5: systematic-debugging, test-driven-development; top1-miss | test-driven-development, systematic-debugging |  |
| coding-debugging-010 | regressed | ok | missing-gold@5: systematic-debugging; top1-miss | systematic-debugging |  |
| creative-productivity-003 | regressed | ok | missing-gold@5: songwriting-and-ai-music; top1-miss | songwriting-and-ai-music |  |
| data-mlops-006 | regressed | ok | missing-gold@5: python-data-analysis; top1-miss | python-data-analysis, data-analysis | data-analysis |
| infra-ops-007 | regressed | ok | missing-gold@5: github-actions | python-packaging, github-actions | python-packaging |
| multimodal-asr-006 | regressed | ok | missing-gold@5: asr-evaluation, speech-transcription; top1-miss | asr-evaluation, speech-transcription, audio-preprocessing, image-captioning |  |
| multimodal-asr-007 | regressed | ok | missing-gold@5: audio-preprocessing | multimodal-alignment, speech-transcription, audio-preprocessing | multimodal-alignment |
| multimodal-asr-008 | trade-off | missing-gold@5: research-paper-summary | missing-gold@5: image-captioning, research-paper-summary; top1-miss | image-captioning, asr-evaluation, speech-transcription, audio-preprocessing |  |
| retrieval-eval-010 | regressed | ok | missing-gold@5: vector-search | vector-search, cross-encoder-reranking, embedding-finetuning, rag | cross-encoder-reranking |
| retrieval-eval-011 | regressed | ok | missing-gold@5: dataset-curation, evaluation-suite-design; top1-miss | evaluation-suite-design, dataset-curation |  |
| retrieval-eval-012 | regressed | ok | missing-gold@5: error-analysis, llm-judge-evaluation; top1-miss | llm-judge-evaluation, error-analysis, evaluation-suite-design |  |
| robustness-ambiguous-001 | trade-off | negative-hit@5: test-driven-development | missing-gold@5: systematic-debugging; top1-miss | systematic-debugging, test-driven-development |  |
| robustness-ambiguous-003 | improved | negative-hit@5: wandb | ok | mlflow, wandb | mlflow |
| robustness-ambiguous-007 | trade-off | negative-hit@5: data-analysis | missing-gold@5: python-data-analysis; top1-miss | python-data-analysis, data-analysis |  |

## Failure Cases By Task

| Task ID | Category | Router | Issues | Gold Skills | Negative Skills | Selected@5 |
| --- | --- | --- | --- | --- | --- | --- |
| agent-workflows-007 | agent | cross-encoder-minilm | missing-gold@5: skill-routing | skill-routing, verifier-gated-routing | popular-web-designs | verifier-gated-routing |
| agent-workflows-008 | agent | cross-encoder-minilm | missing-gold@5: error-analysis | self-improvement-harness, error-analysis | baoyu-comic | self-improvement-harness |
| agent-workflows-012 | agent | cross-encoder-minilm | missing-gold@5: verifier-gated-routing; top1-miss | verifier-gated-routing | creative-ideation |  |
| coding-debugging-001 | coding | cross-encoder-minilm | missing-gold@5: test-driven-development | systematic-debugging, test-driven-development | songwriting-and-ai-music | systematic-debugging |
| coding-debugging-002 | coding | cross-encoder-minilm | missing-gold@5: systematic-debugging; top1-miss | systematic-debugging | ascii-art |  |
| coding-debugging-004 | coding | cross-encoder-minilm | missing-gold@5: systematic-debugging; top1-miss | systematic-debugging | creative-ideation |  |
| coding-debugging-007 | coding | cross-encoder-minilm | missing-gold@5: systematic-debugging, test-driven-development; top1-miss | test-driven-development, systematic-debugging | ascii-art |  |
| coding-debugging-010 | coding | cross-encoder-minilm | missing-gold@5: systematic-debugging; top1-miss | systematic-debugging | creative-ideation |  |
| creative-productivity-003 | creative | cross-encoder-minilm | missing-gold@5: songwriting-and-ai-music; top1-miss | songwriting-and-ai-music | test-driven-development |  |
| data-mlops-006 | data-analysis | cross-encoder-minilm | missing-gold@5: python-data-analysis; top1-miss | python-data-analysis | macos-computer-use | data-analysis |
| infra-ops-007 | infra | cross-encoder-minilm | missing-gold@5: github-actions | github-actions, python-packaging | songwriting-and-ai-music | python-packaging |
| infra-ops-008 | infra | cross-encoder-minilm | missing-gold@5: model-serving | model-serving, observability | literature-review | observability |
| multimodal-asr-006 | multimodal | cross-encoder-minilm | missing-gold@5: asr-evaluation, speech-transcription; top1-miss | asr-evaluation, speech-transcription | google-calendar |  |
| multimodal-asr-007 | multimodal | cross-encoder-minilm | missing-gold@5: audio-preprocessing | audio-preprocessing, multimodal-alignment | test-driven-development | multimodal-alignment |
| multimodal-asr-008 | multimodal | cross-encoder-minilm | missing-gold@5: image-captioning, research-paper-summary; top1-miss | image-captioning, research-paper-summary | mlflow |  |
| research-writing-005 | research | cross-encoder-minilm | missing-gold@5: citation-checking | literature-review, citation-checking | songwriting-and-ai-music | literature-review |
| retrieval-eval-009 | retrieval | cross-encoder-minilm | missing-gold@5: citation-checking | rag, citation-checking | prompt-engineering | rag |
| retrieval-eval-010 | retrieval | cross-encoder-minilm | missing-gold@5: vector-search | vector-search, cross-encoder-reranking | apple-reminders | cross-encoder-reranking |
| retrieval-eval-011 | evaluation | cross-encoder-minilm | missing-gold@5: dataset-curation, evaluation-suite-design; top1-miss | dataset-curation, evaluation-suite-design | macos-computer-use |  |
| retrieval-eval-012 | evaluation | cross-encoder-minilm | missing-gold@5: error-analysis, llm-judge-evaluation; top1-miss | llm-judge-evaluation, error-analysis | songwriting-and-ai-music |  |
| robustness-ambiguous-001 | coding | cross-encoder-minilm | missing-gold@5: systematic-debugging; top1-miss | systematic-debugging | test-driven-development |  |
| robustness-ambiguous-007 | data-analysis | cross-encoder-minilm | missing-gold@5: python-data-analysis; top1-miss | python-data-analysis | data-analysis |  |
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
