# Phase 14 Fine-Tuned Embedding Router Evaluation

- Baseline: `embedding-minilm`
- Candidate: `finetuned-embedding`
- Guard status: REVIEW_REQUIRED
- Model checkpoint committed: False

| Metric | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| recall_at_5 | 1.000000 | 1.000000 | +0.000000 |
| mrr | 0.902778 | 0.916667 | +0.013889 |
| ndcg_at_5 | 0.920888 | 0.938488 | +0.017600 |
| negative_hit_rate | 0.333333 | 0.250000 | -0.083333 |
| negative_accepted_rate | 0.333333 | 0.250000 | -0.083333 |
| selection_rate_at_5 | 1.000000 | 1.000000 | +0.000000 |

## Guard Flags

| Task | Regression Flags | Improvement Flags |
|---|---|---|
| browser-form-regression | - | mrr_increased, ndcg_at_5_increased, negative_hit_rate_decreased, negative_accepted_rate_decreased, removed_negative_skill |
| browser-local-dashboard | negative_hit_rate_increased, negative_accepted_rate_increased, new_negative_skill_selected | - |
| codex-worker-handoff | - | ndcg_at_5_increased |
| sp-debug-red-green | - | negative_hit_rate_decreased, negative_accepted_rate_decreased, removed_negative_skill |
