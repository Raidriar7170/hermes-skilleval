# Phase 14 Fine-Tuned Embedding Router Evaluation

- Baseline: `embedding-minilm`
- Candidate: `finetuned-embedding`
- Guard status: PASS
- Model checkpoint committed: False

| Metric | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| recall_at_5 | 1.000000 | 1.000000 | +0.000000 |
| mrr | 0.902778 | 1.000000 | +0.097222 |
| ndcg_at_5 | 0.920888 | 1.000000 | +0.079112 |
| negative_hit_rate | 0.333333 | 0.083333 | -0.250000 |
| negative_accepted_rate | 0.333333 | 0.083333 | -0.250000 |
| selection_rate_at_5 | 1.000000 | 1.000000 | +0.000000 |

## Guard Flags

| Task | Regression Flags | Improvement Flags |
|---|---|---|
| browser-form-regression | - | mrr_increased, ndcg_at_5_increased, negative_hit_rate_decreased, negative_accepted_rate_decreased, removed_negative_skill |
| claude-command-routing | - | mrr_increased, ndcg_at_5_increased |
| codex-worker-handoff | - | ndcg_at_5_increased, negative_hit_rate_decreased, negative_accepted_rate_decreased, removed_negative_skill |
| sp-debug-red-green | - | negative_hit_rate_decreased, negative_accepted_rate_decreased, removed_negative_skill |
