# Hermes SkillEval Report

- Router: gated-minilm-contrastive
- Records: 30

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 0.850 |
| Recall@3 | 0.950 |
| Recall@5 | 0.950 |
| Precision@5 | 0.240 |
| MRR | 1.000 |
| NDCG@5 | 0.959 |
| Negative Hit Rate | 0.100 |
| Accepted Count | 1.800 |
| Coverage | 1.000 |
| Selection Rate@5 | 0.360 |
| Abstention Rate | 0.000 |
| Accepted Recall@5 | 0.950 |
| Negative Accepted Rate | 0.100 |
| Average Latency (ms) | 10.496 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| speech-transcription | 4 |
| audio-preprocessing | 4 |
| asr-evaluation | 3 |
| image-captioning | 3 |
| github-actions | 2 |
| distributed-training | 2 |
| cuda-profiling | 2 |
| python-packaging | 2 |
| observability | 2 |
| multimodal-alignment | 2 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| infra-ops-001 | 1.000 | 0.000 | 10.471 |
| infra-ops-002 | 1.000 | 0.000 | 10.465 |
| infra-ops-003 | 1.000 | 0.000 | 10.319 |
| infra-ops-004 | 1.000 | 0.000 | 10.348 |
| infra-ops-005 | 1.000 | 0.000 | 10.394 |
| infra-ops-006 | 1.000 | 0.000 | 10.508 |
| infra-ops-007 | 1.000 | 0.000 | 10.461 |
| infra-ops-008 | 0.500 | 0.000 | 10.476 |
| multimodal-asr-001 | 1.000 | 0.000 | 10.458 |
| multimodal-asr-002 | 1.000 | 0.000 | 10.447 |
| multimodal-asr-003 | 1.000 | 0.000 | 10.482 |
| multimodal-asr-004 | 1.000 | 0.000 | 10.662 |
| multimodal-asr-005 | 1.000 | 0.000 | 10.408 |
| multimodal-asr-006 | 1.000 | 0.000 | 10.541 |
| multimodal-asr-007 | 1.000 | 0.000 | 10.572 |
| multimodal-asr-008 | 0.500 | 0.000 | 10.617 |
| retrieval-eval-009 | 0.500 | 0.000 | 10.762 |
| retrieval-eval-010 | 1.000 | 0.000 | 10.748 |
| retrieval-eval-011 | 1.000 | 0.000 | 10.575 |
| retrieval-eval-012 | 1.000 | 0.000 | 10.537 |
| robustness-ambiguous-001 | 1.000 | 1.000 | 10.476 |
| robustness-ambiguous-002 | 1.000 | 0.000 | 10.336 |
| robustness-ambiguous-003 | 1.000 | 1.000 | 10.493 |
| robustness-ambiguous-004 | 1.000 | 0.000 | 10.359 |
| robustness-ambiguous-005 | 1.000 | 0.000 | 10.476 |
| robustness-ambiguous-006 | 1.000 | 0.000 | 10.458 |
| robustness-ambiguous-007 | 1.000 | 1.000 | 10.445 |
| robustness-ambiguous-008 | 1.000 | 0.000 | 10.452 |
| robustness-ambiguous-009 | 1.000 | 0.000 | 10.582 |
| robustness-ambiguous-010 | 1.000 | 0.000 | 10.560 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| robustness-ambiguous-001 | systematic-debugging, test-driven-development | systematic-debugging | 1.000 | 1.000 |
| robustness-ambiguous-003 | mlflow, wandb | mlflow | 1.000 | 1.000 |
| robustness-ambiguous-007 | python-data-analysis, data-analysis | python-data-analysis | 1.000 | 1.000 |
