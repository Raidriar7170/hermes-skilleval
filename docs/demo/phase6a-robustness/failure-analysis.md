# Hermes SkillEval Failure Analysis

## Failure Summary

| Router | Tasks | Top-1 Misses | Missing Gold@5 | Negative Hits@5 | Any Failure |
| --- | ---: | ---: | ---: | ---: | ---: |
| embedding-hashing | 80 | 27 | 14 | 6 | 36 |
| embedding-minilm | 80 | 8 | 5 | 8 | 17 |
| gated-minilm-selective | 80 | 2 | 3 | 9 | 14 |
| hybrid | 80 | 3 | 1 | 11 | 15 |
| keyword | 80 | 3 | 2 | 11 | 16 |

## Candidate vs Baseline

- Baseline: `embedding-minilm`
- Candidate: `gated-minilm-selective`

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Recall@1 | 0.812 | 0.881 | +0.069 |
| Recall@5 | 0.956 | 0.981 | +0.025 |
| MRR | 0.934 | 0.985 | +0.051 |
| NDCG@5 | 0.930 | 0.974 | +0.044 |
| Negative Hit Rate | 0.100 | 0.113 | -0.012 |
| Avg Latency ms | 11.266 | 7.603 | +3.663 |

## Candidate Task Changes

| Task ID | Change | Baseline Issues | Candidate Issues | Baseline Selected@5 | Candidate Selected@5 |
| --- | --- | --- | --- | --- | --- |
| agent-workflows-006 | regressed | ok | top1-miss | prompt-engineering, tool-planning, skill-routing, verifier-gated-routing, test-driven-development | tool-planning, prompt-engineering, context-management, self-improvement-harness, skill-routing |
| agent-workflows-012 | trade-off | missing-gold@5: verifier-gated-routing; top1-miss | top1-miss | skill-routing, tool-planning, prompt-engineering, self-improvement-harness, github-actions | skill-routing, tool-planning, verifier-gated-routing, prompt-engineering, self-improvement-harness |
| coding-debugging-009 | improved | top1-miss | ok | systematic-debugging, test-driven-development, prompt-engineering, evaluation-suite-design, github-actions | test-driven-development, systematic-debugging |
| data-mlops-006 | improved | top1-miss | ok | data-analysis, python-data-analysis, dataset-curation, wandb, evaluation-suite-design | python-data-analysis, data-analysis |
| infra-ops-001 | improved | top1-miss | ok | skill-routing, github-actions, self-improvement-harness, distributed-training, verifier-gated-routing | github-actions, distributed-training, cuda-profiling |
| research-writing-002 | improved | missing-gold@5: literature-review; top1-miss | ok | skill-routing, self-improvement-harness, verifier-gated-routing, llm-judge-evaluation, prompt-engineering | literature-review, research-paper-summary |
| retrieval-eval-005 | improved | top1-miss | ok | embedding-finetuning, dataset-curation, evaluation-suite-design, cross-encoder-reranking, skill-routing | dataset-curation, evaluation-suite-design, llm-judge-evaluation, error-analysis |
| retrieval-eval-009 | regressed | ok | missing-gold@5: citation-checking | rag, citation-checking, vector-search, research-paper-summary, embedding-finetuning | rag, embedding-finetuning, vector-search, cross-encoder-reranking |
| retrieval-eval-011 | improved | missing-gold@5: dataset-curation; top1-miss | ok | skill-routing, verifier-gated-routing, self-improvement-harness, evaluation-suite-design, embedding-finetuning | evaluation-suite-design, dataset-curation, llm-judge-evaluation |
| robustness-ambiguous-005 | regressed | ok | negative-hit@5: literature-review | citation-checking, research-paper-summary, academic-writing, evaluation-suite-design, systematic-debugging | citation-checking, research-paper-summary, academic-writing, literature-review |
| robustness-ambiguous-006 | regressed | ok | negative-hit@5: citation-checking | literature-review, academic-writing, systematic-debugging, creative-ideation, evaluation-suite-design | literature-review, research-paper-summary, academic-writing, citation-checking |
| robustness-ambiguous-010 | improved | negative-hit@5: llm-judge-evaluation; top1-miss | ok | prompt-engineering, verifier-gated-routing, llm-judge-evaluation, skill-routing, self-improvement-harness | verifier-gated-routing, skill-routing, prompt-engineering, tool-planning, self-improvement-harness |

## Failure Cases By Task

| Task ID | Category | Router | Issues | Gold Skills | Negative Skills | Selected@5 |
| --- | --- | --- | --- | --- | --- | --- |
| agent-workflows-002 | agent | embedding-hashing | top1-miss | verifier-gated-routing | ascii-art | tool-planning, skill-routing, prompt-engineering, verifier-gated-routing, github-actions |
| agent-workflows-004 | agent | embedding-hashing | negative-hit@5: songwriting-and-ai-music; top1-miss | tool-planning | songwriting-and-ai-music | github-actions, tool-planning, distributed-training, songwriting-and-ai-music, context-management |
| agent-workflows-006 | agent | embedding-hashing | top1-miss | prompt-engineering | cuda-profiling | tool-planning, prompt-engineering, macos-computer-use, context-management, skill-routing |
| agent-workflows-007 | agent | embedding-hashing | missing-gold@5: verifier-gated-routing; top1-miss | skill-routing, verifier-gated-routing | popular-web-designs | tool-planning, skill-routing, context-management, self-improvement-harness, apple-reminders |
| agent-workflows-008 | agent | embedding-hashing | missing-gold@5: self-improvement-harness; top1-miss | self-improvement-harness, error-analysis | baoyu-comic | tool-planning, prompt-engineering, songwriting-and-ai-music, error-analysis, model-serving |
| agent-workflows-010 | agent | embedding-hashing | top1-miss | context-management | citation-checking | tool-planning, context-management, literature-review, skill-routing, multimodal-alignment |
| agent-workflows-012 | agent | embedding-hashing | missing-gold@5: verifier-gated-routing; top1-miss | verifier-gated-routing | creative-ideation | tool-planning, context-management, prompt-engineering, apple-reminders, skill-routing |
| coding-debugging-002 | coding | embedding-hashing | top1-miss | systematic-debugging | ascii-art | test-driven-development, systematic-debugging, observability, mlflow, asr-evaluation |
| coding-debugging-004 | coding | embedding-hashing | missing-gold@5: systematic-debugging; top1-miss | systematic-debugging | creative-ideation | wandb, tool-planning, academic-writing, cuda-profiling, observability |
| coding-debugging-005 | coding | embedding-hashing | top1-miss | test-driven-development | baoyu-comic | systematic-debugging, test-driven-development, observability, embedding-finetuning, data-analysis |
| coding-debugging-007 | coding | embedding-hashing | missing-gold@5: systematic-debugging | test-driven-development, systematic-debugging | ascii-art | test-driven-development, research-paper-summary, wandb, citation-checking, songwriting-and-ai-music |
| coding-debugging-008 | coding | embedding-hashing | top1-miss | systematic-debugging | popular-web-designs | mlflow, systematic-debugging, observability, docker, self-improvement-harness |
| coding-debugging-009 | coding | embedding-hashing | negative-hit@5: songwriting-and-ai-music | test-driven-development | songwriting-and-ai-music | test-driven-development, systematic-debugging, skill-routing, audio-preprocessing, songwriting-and-ai-music |
| creative-productivity-003 | creative | embedding-hashing | top1-miss | songwriting-and-ai-music | test-driven-development | creative-ideation, songwriting-and-ai-music, docker, distributed-training, skill-routing |
| data-mlops-006 | data-analysis | embedding-hashing | top1-miss | python-data-analysis | macos-computer-use | data-analysis, python-data-analysis, error-analysis, songwriting-and-ai-music, academic-writing |
| infra-ops-001 | infra | embedding-hashing | top1-miss | github-actions | baoyu-comic | skill-routing, songwriting-and-ai-music, citation-checking, github-actions, vector-search |
| infra-ops-002 | infra | embedding-hashing | top1-miss | python-packaging | note-taking | error-analysis, mlflow, python-packaging, vector-search, github-actions |
| infra-ops-007 | infra | embedding-hashing | missing-gold@5: github-actions; top1-miss | github-actions, python-packaging | songwriting-and-ai-music | python-data-analysis, error-analysis, python-packaging, audio-preprocessing, macos-computer-use |
| infra-ops-008 | infra | embedding-hashing | missing-gold@5: model-serving | model-serving, observability | literature-review | observability, error-analysis, songwriting-and-ai-music, vector-search, asr-evaluation |
| multimodal-asr-001 | multimodal | embedding-hashing | top1-miss | speech-transcription | academic-writing | multimodal-alignment, speech-transcription, audio-preprocessing, distributed-training, vector-search |
| multimodal-asr-006 | multimodal | embedding-hashing | missing-gold@5: speech-transcription; top1-miss | asr-evaluation, speech-transcription | google-calendar | multimodal-alignment, asr-evaluation, evaluation-suite-design, observability, python-data-analysis |
| multimodal-asr-008 | multimodal | embedding-hashing | top1-miss | image-captioning, research-paper-summary | mlflow | wandb, multimodal-alignment, image-captioning, github-actions, research-paper-summary |
| productivity-001 | productivity | embedding-hashing | top1-miss | apple-reminders | citation-checking | distributed-training, apple-reminders, docker, literature-review, songwriting-and-ai-music |
| productivity-003 | productivity | embedding-hashing | negative-hit@5: docker | note-taking | docker | note-taking, docker, creative-ideation, distributed-training, google-calendar |
| research-writing-005 | research | embedding-hashing | missing-gold@5: citation-checking; top1-miss | literature-review, citation-checking | songwriting-and-ai-music | academic-writing, tool-planning, audio-preprocessing, literature-review, distributed-training |
| retrieval-eval-008 | evaluation | embedding-hashing | top1-miss | error-analysis | creative-ideation | evaluation-suite-design, dataset-curation, macos-computer-use, error-analysis, model-serving |
| retrieval-eval-009 | retrieval | embedding-hashing | missing-gold@5: citation-checking | rag, citation-checking | prompt-engineering | rag, embedding-finetuning, vector-search, academic-writing, research-paper-summary |
| retrieval-eval-010 | retrieval | embedding-hashing | top1-miss | vector-search, cross-encoder-reranking | apple-reminders | embedding-finetuning, verifier-gated-routing, vector-search, ascii-art, cross-encoder-reranking |
| retrieval-eval-011 | evaluation | embedding-hashing | missing-gold@5: dataset-curation, evaluation-suite-design; top1-miss | dataset-curation, evaluation-suite-design | macos-computer-use | skill-routing, literature-review, tool-planning, songwriting-and-ai-music, github-actions |
| retrieval-eval-012 | evaluation | embedding-hashing | missing-gold@5: error-analysis | llm-judge-evaluation, error-analysis | songwriting-and-ai-music | llm-judge-evaluation, embedding-finetuning, systematic-debugging, vector-search, mlflow |
| robustness-ambiguous-001 | coding | embedding-hashing | missing-gold@5: systematic-debugging; top1-miss | systematic-debugging | test-driven-development | skill-routing, popular-web-designs, multimodal-alignment, embedding-finetuning, vector-search |
| robustness-ambiguous-002 | coding | embedding-hashing | negative-hit@5: systematic-debugging | test-driven-development | systematic-debugging | test-driven-development, systematic-debugging, skill-routing, prompt-engineering, audio-preprocessing |
| robustness-ambiguous-003 | mlops | embedding-hashing | negative-hit@5: wandb | mlflow | wandb | mlflow, llm-judge-evaluation, docker, wandb, evaluation-suite-design |
| robustness-ambiguous-007 | data-analysis | embedding-hashing | missing-gold@5: python-data-analysis; top1-miss | python-data-analysis | data-analysis | citation-checking, creative-ideation, songwriting-and-ai-music, github-actions, research-paper-summary |
| robustness-ambiguous-009 | agent | embedding-hashing | negative-hit@5: tool-planning | skill-routing | tool-planning | skill-routing, context-management, prompt-engineering, tool-planning, literature-review |
| robustness-ambiguous-010 | agent | embedding-hashing | top1-miss | verifier-gated-routing | llm-judge-evaluation | evaluation-suite-design, verifier-gated-routing, ascii-art, asr-evaluation, prompt-engineering |
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
| agent-workflows-006 | agent | hybrid | top1-miss | prompt-engineering | cuda-profiling | tool-planning, prompt-engineering, context-management, self-improvement-harness, skill-routing |
| agent-workflows-008 | agent | hybrid | missing-gold@5: error-analysis | self-improvement-harness, error-analysis | baoyu-comic | self-improvement-harness, llm-judge-evaluation, skill-routing, tool-planning, embedding-finetuning |
| agent-workflows-011 | agent | hybrid | negative-hit@5: literature-review | prompt-engineering | literature-review | prompt-engineering, context-management, skill-routing, tool-planning, literature-review |
| agent-workflows-012 | agent | hybrid | top1-miss | verifier-gated-routing | creative-ideation | skill-routing, context-management, tool-planning, verifier-gated-routing, prompt-engineering |
| infra-ops-001 | infra | hybrid | top1-miss | github-actions | baoyu-comic | skill-routing, github-actions, self-improvement-harness, cuda-profiling, distributed-training |
| robustness-ambiguous-001 | coding | hybrid | negative-hit@5: test-driven-development | systematic-debugging | test-driven-development | systematic-debugging, test-driven-development, skill-routing, audio-preprocessing, academic-writing |
| robustness-ambiguous-002 | coding | hybrid | negative-hit@5: systematic-debugging | test-driven-development | systematic-debugging | test-driven-development, systematic-debugging, skill-routing, academic-writing, audio-preprocessing |
| robustness-ambiguous-003 | mlops | hybrid | negative-hit@5: wandb | mlflow | wandb | mlflow, wandb, docker, evaluation-suite-design, systematic-debugging |
| robustness-ambiguous-004 | mlops | hybrid | negative-hit@5: mlflow | wandb | mlflow | wandb, docker, mlflow, python-data-analysis, skill-routing |
| robustness-ambiguous-005 | research | hybrid | negative-hit@5: literature-review | citation-checking | literature-review | citation-checking, research-paper-summary, academic-writing, literature-review, github-actions |
| robustness-ambiguous-006 | research | hybrid | negative-hit@5: citation-checking | literature-review | citation-checking | literature-review, research-paper-summary, academic-writing, image-captioning, citation-checking |
| robustness-ambiguous-007 | data-analysis | hybrid | negative-hit@5: data-analysis | python-data-analysis | data-analysis | python-data-analysis, data-analysis, songwriting-and-ai-music, github-actions, llm-judge-evaluation |
| robustness-ambiguous-008 | data-analysis | hybrid | negative-hit@5: python-data-analysis | data-analysis | python-data-analysis | data-analysis, python-data-analysis, research-paper-summary, academic-writing, dataset-curation |
| robustness-ambiguous-009 | agent | hybrid | negative-hit@5: tool-planning | skill-routing | tool-planning | skill-routing, context-management, tool-planning, verifier-gated-routing, self-improvement-harness |
| robustness-ambiguous-010 | agent | hybrid | negative-hit@5: llm-judge-evaluation | verifier-gated-routing | llm-judge-evaluation | verifier-gated-routing, skill-routing, llm-judge-evaluation, context-management, prompt-engineering |
| agent-workflows-006 | agent | keyword | top1-miss | prompt-engineering | cuda-profiling | tool-planning, prompt-engineering, context-management, self-improvement-harness, literature-review |
| agent-workflows-008 | agent | keyword | missing-gold@5: error-analysis | self-improvement-harness, error-analysis | baoyu-comic | self-improvement-harness, llm-judge-evaluation, embedding-finetuning, popular-web-designs, skill-routing |
| agent-workflows-011 | agent | keyword | negative-hit@5: literature-review | prompt-engineering | literature-review | prompt-engineering, context-management, skill-routing, tool-planning, literature-review |
| agent-workflows-012 | agent | keyword | top1-miss | verifier-gated-routing | creative-ideation | skill-routing, context-management, tool-planning, verifier-gated-routing, prompt-engineering |
| infra-ops-001 | infra | keyword | top1-miss | github-actions | baoyu-comic | skill-routing, github-actions, self-improvement-harness, apple-reminders, cuda-profiling |
| productivity-001 | productivity | keyword | negative-hit@5: citation-checking | apple-reminders | citation-checking | apple-reminders, literature-review, image-captioning, songwriting-and-ai-music, citation-checking |
| research-writing-005 | research | keyword | missing-gold@5: citation-checking | literature-review, citation-checking | songwriting-and-ai-music | literature-review, tool-planning, context-management, vector-search, image-captioning |
| robustness-ambiguous-001 | coding | keyword | negative-hit@5: test-driven-development | systematic-debugging | test-driven-development | systematic-debugging, test-driven-development, skill-routing, audio-preprocessing, academic-writing |
| robustness-ambiguous-002 | coding | keyword | negative-hit@5: systematic-debugging | test-driven-development | systematic-debugging | test-driven-development, systematic-debugging, skill-routing, academic-writing, audio-preprocessing |
| robustness-ambiguous-003 | mlops | keyword | negative-hit@5: wandb | mlflow | wandb | mlflow, wandb, docker, evaluation-suite-design, systematic-debugging |
| robustness-ambiguous-004 | mlops | keyword | negative-hit@5: mlflow | wandb | mlflow | wandb, python-data-analysis, skill-routing, docker, mlflow |
| robustness-ambiguous-005 | research | keyword | negative-hit@5: literature-review | citation-checking | literature-review | citation-checking, research-paper-summary, academic-writing, literature-review, github-actions |
| robustness-ambiguous-007 | data-analysis | keyword | negative-hit@5: data-analysis | python-data-analysis | data-analysis | python-data-analysis, songwriting-and-ai-music, data-analysis, github-actions, llm-judge-evaluation |
| robustness-ambiguous-008 | data-analysis | keyword | negative-hit@5: python-data-analysis | data-analysis | python-data-analysis | data-analysis, python-data-analysis, research-paper-summary, academic-writing, dataset-curation |
| robustness-ambiguous-009 | agent | keyword | negative-hit@5: tool-planning | skill-routing | tool-planning | skill-routing, context-management, tool-planning, verifier-gated-routing, self-improvement-harness |
| robustness-ambiguous-010 | agent | keyword | negative-hit@5: llm-judge-evaluation | verifier-gated-routing | llm-judge-evaluation | verifier-gated-routing, llm-judge-evaluation, skill-routing, github-actions, context-management |
