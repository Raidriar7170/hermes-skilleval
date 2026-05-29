# Phase 15 Held-Out Fine-Tuned Embedding Router Evaluation

- Baseline: `embedding-minilm`
- Candidate: `finetuned-embedding`
- Evaluated split: `test`
- Source task count: 12
- Evaluated task count: 4
- Guard status: PASS
- Model checkpoint committed: False

| Metric | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| recall_at_5 | 1.000000 | 1.000000 | +0.000000 |
| mrr | 1.000000 | 1.000000 | +0.000000 |
| ndcg_at_5 | 1.000000 | 1.000000 | +0.000000 |
| negative_hit_rate | 0.250000 | 0.250000 | +0.000000 |
| negative_accepted_rate | 0.250000 | 0.250000 | +0.000000 |
| selection_rate_at_5 | 1.000000 | 1.000000 | +0.000000 |

## Guard Flags

No per-task regression or improvement flags were observed.
