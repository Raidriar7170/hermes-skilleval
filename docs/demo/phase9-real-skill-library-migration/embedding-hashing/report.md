# Hermes SkillEval Report

- Router: embedding-hashing
- Records: 12

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 0.750 |
| Recall@3 | 0.958 |
| Recall@5 | 1.000 |
| Precision@5 | 0.267 |
| MRR | 0.944 |
| NDCG@5 | 0.948 |
| Negative Hit Rate | 0.167 |
| Accepted Count | 5.000 |
| Coverage | 1.000 |
| Selection Rate@5 | 1.000 |
| Abstention Rate | 0.000 |
| Accepted Recall@5 | 1.000 |
| Negative Accepted Rate | 0.167 |
| Average Latency (ms) | 2.819 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| visual-regression-review | 8 |
| browser-smoke-testing | 7 |
| accessibility-tree-inspection | 6 |
| systematic-debugging | 6 |
| mcp-tool-routing | 4 |
| slash-command-workflow | 4 |
| workspace-git-hygiene | 3 |
| evidence-backed-final | 3 |
| subagent-worker-protocol | 3 |
| verification-before-completion | 3 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| browser-accessibility-audit | 1.000 | 0.000 | 2.838 |
| browser-form-regression | 1.000 | 0.000 | 2.974 |
| browser-local-dashboard | 1.000 | 0.000 | 2.709 |
| claude-command-routing | 1.000 | 0.000 | 2.731 |
| claude-mcp-selection | 1.000 | 0.000 | 3.042 |
| claude-plan-to-tasks | 1.000 | 1.000 | 2.888 |
| codex-git-hygiene | 1.000 | 0.000 | 2.685 |
| codex-minimal-diff | 1.000 | 0.000 | 2.989 |
| codex-worker-handoff | 1.000 | 0.000 | 2.646 |
| sp-debug-red-green | 1.000 | 1.000 | 2.782 |
| sp-isolated-worktree | 1.000 | 0.000 | 2.822 |
| sp-verify-before-claim | 1.000 | 0.000 | 2.727 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| claude-plan-to-tasks | plan-mode, visual-regression-review, evidence-backed-final, subagent-worker-protocol, verification-before-completion | plan-mode | 1.000 | 1.000 |
| sp-debug-red-green | test-driven-development, systematic-debugging, visual-regression-review, browser-smoke-testing, slash-command-workflow | systematic-debugging, test-driven-development | 1.000 | 1.000 |
