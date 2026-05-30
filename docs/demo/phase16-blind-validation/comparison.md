# Phase 16 Blind Validation

- Baseline: `baseline-minilm`
- Candidate: `finetuned-embedding`
- Task root: `benchmarks/blind-migration-tasks`
- Task count: 16
- Guard status: REVIEW_REQUIRED
- Model checkpoint committed: False

| Metric | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| recall_at_5 | 1.000000 | 1.000000 | +0.000000 |
| mrr | 1.000000 | 0.968750 | -0.031250 |
| ndcg_at_5 | 1.000000 | 0.976933 | -0.023067 |
| negative_hit_rate | 0.750000 | 0.812500 | +0.062500 |
| negative_accepted_rate | 0.750000 | 0.812500 | +0.062500 |
| selection_rate_at_5 | 1.000000 | 1.000000 | +0.000000 |

## Guard Flags

| Task | Regression Flags | Improvement Flags |
|---|---|---|
| blind-claude-mcp-routing | negative_hit_rate_increased, negative_accepted_rate_increased, new_negative_skill_selected | - |
| blind-codex-worker-handoff | mrr_decreased, ndcg_at_5_decreased | - |
