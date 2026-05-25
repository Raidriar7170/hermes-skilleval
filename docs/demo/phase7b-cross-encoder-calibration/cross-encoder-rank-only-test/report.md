# Hermes SkillEval Report

- Router: cross-encoder
- Records: 30

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 0.850 |
| Recall@3 | 0.950 |
| Recall@5 | 1.000 |
| Precision@5 | 0.260 |
| MRR | 1.000 |
| NDCG@5 | 0.987 |
| Negative Hit Rate | 0.333 |
| Accepted Count | 5.000 |
| Coverage | 1.000 |
| Selection Rate@5 | 1.000 |
| Abstention Rate | 0.000 |
| Accepted Recall@5 | 1.000 |
| Negative Accepted Rate | 0.333 |
| Average Latency (ms) | 18.222 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| evaluation-suite-design | 11 |
| verifier-gated-routing | 9 |
| distributed-training | 8 |
| multimodal-alignment | 8 |
| asr-evaluation | 8 |
| audio-preprocessing | 8 |
| image-captioning | 8 |
| speech-transcription | 7 |
| model-serving | 6 |
| embedding-finetuning | 6 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| infra-ops-001 | 1.000 | 0.000 | 18.277 |
| infra-ops-002 | 1.000 | 0.000 | 18.065 |
| infra-ops-003 | 1.000 | 0.000 | 18.073 |
| infra-ops-004 | 1.000 | 0.000 | 18.180 |
| infra-ops-005 | 1.000 | 0.000 | 18.290 |
| infra-ops-006 | 1.000 | 0.000 | 18.376 |
| infra-ops-007 | 1.000 | 0.000 | 18.542 |
| infra-ops-008 | 1.000 | 0.000 | 20.813 |
| multimodal-asr-001 | 1.000 | 0.000 | 18.243 |
| multimodal-asr-002 | 1.000 | 0.000 | 18.649 |
| multimodal-asr-003 | 1.000 | 0.000 | 18.178 |
| multimodal-asr-004 | 1.000 | 0.000 | 18.129 |
| multimodal-asr-005 | 1.000 | 0.000 | 18.268 |
| multimodal-asr-006 | 1.000 | 0.000 | 17.967 |
| multimodal-asr-007 | 1.000 | 0.000 | 18.168 |
| multimodal-asr-008 | 1.000 | 0.000 | 18.171 |
| retrieval-eval-009 | 1.000 | 0.000 | 17.900 |
| retrieval-eval-010 | 1.000 | 0.000 | 18.213 |
| retrieval-eval-011 | 1.000 | 0.000 | 18.129 |
| retrieval-eval-012 | 1.000 | 0.000 | 18.105 |
| robustness-ambiguous-001 | 1.000 | 1.000 | 18.253 |
| robustness-ambiguous-002 | 1.000 | 1.000 | 18.158 |
| robustness-ambiguous-003 | 1.000 | 1.000 | 17.921 |
| robustness-ambiguous-004 | 1.000 | 1.000 | 18.042 |
| robustness-ambiguous-005 | 1.000 | 1.000 | 17.798 |
| robustness-ambiguous-006 | 1.000 | 1.000 | 17.807 |
| robustness-ambiguous-007 | 1.000 | 1.000 | 17.804 |
| robustness-ambiguous-008 | 1.000 | 1.000 | 18.256 |
| robustness-ambiguous-009 | 1.000 | 1.000 | 17.890 |
| robustness-ambiguous-010 | 1.000 | 1.000 | 18.006 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| robustness-ambiguous-001 | systematic-debugging, test-driven-development, github-actions, evaluation-suite-design, prompt-engineering | systematic-debugging | 1.000 | 1.000 |
| robustness-ambiguous-002 | test-driven-development, systematic-debugging, evaluation-suite-design, prompt-engineering, llm-judge-evaluation | test-driven-development | 1.000 | 1.000 |
| robustness-ambiguous-003 | mlflow, wandb, evaluation-suite-design, docker, model-serving | mlflow | 1.000 | 1.000 |
| robustness-ambiguous-004 | wandb, evaluation-suite-design, mlflow, docker, observability | wandb | 1.000 | 1.000 |
| robustness-ambiguous-005 | citation-checking, research-paper-summary, evaluation-suite-design, literature-review, academic-writing | citation-checking | 1.000 | 1.000 |
| robustness-ambiguous-006 | literature-review, research-paper-summary, evaluation-suite-design, academic-writing, citation-checking | literature-review | 1.000 | 1.000 |
| robustness-ambiguous-007 | python-data-analysis, evaluation-suite-design, data-analysis, dataset-curation, error-analysis | python-data-analysis | 1.000 | 1.000 |
| robustness-ambiguous-008 | data-analysis, evaluation-suite-design, python-data-analysis, dataset-curation, research-paper-summary | data-analysis | 1.000 | 1.000 |
| robustness-ambiguous-009 | skill-routing, verifier-gated-routing, tool-planning, prompt-engineering, self-improvement-harness | skill-routing | 1.000 | 1.000 |
| robustness-ambiguous-010 | verifier-gated-routing, skill-routing, evaluation-suite-design, prompt-engineering, llm-judge-evaluation | verifier-gated-routing | 1.000 | 1.000 |
