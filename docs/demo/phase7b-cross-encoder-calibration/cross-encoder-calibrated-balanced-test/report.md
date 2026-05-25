# Hermes SkillEval Report

- Router: cross-encoder-calibrated
- Records: 30

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 0.850 |
| Recall@3 | 0.950 |
| Recall@5 | 0.967 |
| Precision@5 | 0.247 |
| MRR | 1.000 |
| NDCG@5 | 0.970 |
| Negative Hit Rate | 0.100 |
| Accepted Count | 1.967 |
| Coverage | 1.000 |
| Selection Rate@5 | 0.393 |
| Abstention Rate | 0.000 |
| Accepted Recall@5 | 0.967 |
| Negative Accepted Rate | 0.100 |
| Average Latency (ms) | 18.222 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| model-serving | 5 |
| multimodal-alignment | 5 |
| asr-evaluation | 5 |
| speech-transcription | 4 |
| verifier-gated-routing | 4 |
| github-actions | 2 |
| python-packaging | 2 |
| distributed-training | 2 |
| observability | 2 |
| audio-preprocessing | 2 |

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
| multimodal-asr-008 | 0.500 | 0.000 | 18.171 |
| retrieval-eval-009 | 1.000 | 0.000 | 17.900 |
| retrieval-eval-010 | 1.000 | 0.000 | 18.213 |
| retrieval-eval-011 | 0.500 | 0.000 | 18.129 |
| retrieval-eval-012 | 1.000 | 0.000 | 18.105 |
| robustness-ambiguous-001 | 1.000 | 0.000 | 18.253 |
| robustness-ambiguous-002 | 1.000 | 1.000 | 18.158 |
| robustness-ambiguous-003 | 1.000 | 1.000 | 17.921 |
| robustness-ambiguous-004 | 1.000 | 0.000 | 18.042 |
| robustness-ambiguous-005 | 1.000 | 0.000 | 17.798 |
| robustness-ambiguous-006 | 1.000 | 0.000 | 17.807 |
| robustness-ambiguous-007 | 1.000 | 0.000 | 17.804 |
| robustness-ambiguous-008 | 1.000 | 0.000 | 18.256 |
| robustness-ambiguous-009 | 1.000 | 1.000 | 17.890 |
| robustness-ambiguous-010 | 1.000 | 0.000 | 18.006 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| robustness-ambiguous-002 | test-driven-development, systematic-debugging | test-driven-development | 1.000 | 1.000 |
| robustness-ambiguous-003 | mlflow, wandb, evaluation-suite-design | mlflow | 1.000 | 1.000 |
| robustness-ambiguous-009 | skill-routing, verifier-gated-routing, tool-planning | skill-routing | 1.000 | 1.000 |
