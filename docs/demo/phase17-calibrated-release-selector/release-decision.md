# Phase 17 Calibrated Release Selector

- Source phase: Phase 16
- Source guard status: `REVIEW_REQUIRED`
- Aggregate decision: `KEEP_BASELINE`
- Selected router: `baseline-minilm`
- Baseline router: `baseline-minilm`
- Candidate router: `finetuned-embedding`
- Approved for default: `False`
- Task count: 16
- Regression count: 2

## Policy

| Budget | Value |
|---|---:|
| max_regressions | 0 |
| max_negative_hit_delta | 0.0 |
| max_negative_accepted_delta | 0.0 |
| min_recall_at_5_delta | 0.0 |
| min_mrr_delta | 0.0 |
| min_ndcg_at_5_delta | 0.0 |

## Reasons

- source guard_status is not PASS
- regression_count exceeds policy
- negative_hit_rate delta exceeds policy
- negative_accepted_rate delta exceeds policy
- mrr delta is below policy
- ndcg_at_5 delta is below policy

## Task-level Decisions

`NO_CHANGE` is a task-level status only; aggregate release decisions are `APPROVE_CANDIDATE`, `KEEP_BASELINE`, or `REVIEW_REQUIRED`.

| Task | Task-level decision | Regression flags |
|---|---|---|
| blind-browser-accessibility-tree | `NO_CHANGE` | - |
| blind-browser-form-wizard | `NO_CHANGE` | - |
| blind-browser-smoke-console | `NO_CHANGE` | - |
| blind-browser-visual-diff | `NO_CHANGE` | - |
| blind-claude-mcp-routing | `KEEP_BASELINE` | negative_hit_rate_increased, negative_accepted_rate_increased, new_negative_skill_selected |
| blind-claude-plan-session | `NO_CHANGE` | - |
| blind-claude-slash-command | `NO_CHANGE` | - |
| blind-claude-task-delegation | `NO_CHANGE` | - |
| blind-codex-apply-patch | `NO_CHANGE` | - |
| blind-codex-evidence-final | `NO_CHANGE` | - |
| blind-codex-git-hygiene | `NO_CHANGE` | - |
| blind-codex-worker-handoff | `KEEP_BASELINE` | mrr_decreased, ndcg_at_5_decreased |
| blind-sp-debug-loop | `NO_CHANGE` | - |
| blind-sp-red-green | `NO_CHANGE` | - |
| blind-sp-verify-before-claim | `NO_CHANGE` | - |
| blind-sp-worktree-isolation | `NO_CHANGE` | - |
