# Hermes SkillEval Report

- Router: hybrid
- Records: 12

## Metrics

| Metric | Mean |
| --- | ---: |
| Recall@1 | 0.750 |
| Recall@3 | 1.000 |
| Recall@5 | 1.000 |
| Precision@5 | 0.267 |
| MRR | 0.944 |
| NDCG@5 | 0.958 |
| Negative Hit Rate | 0.250 |
| Accepted Count | 5.000 |
| Coverage | 1.000 |
| Selection Rate@5 | 1.000 |
| Abstention Rate | 0.000 |
| Accepted Recall@5 | 1.000 |
| Negative Accepted Rate | 0.250 |
| Average Latency (ms) | 0.607 |

## Top Selected Skills

| Skill | Count |
| --- | ---: |
| workspace-git-hygiene | 6 |
| systematic-debugging | 6 |
| apply-patch-discipline | 6 |
| subagent-worker-protocol | 6 |
| browser-smoke-testing | 5 |
| visual-regression-review | 5 |
| evidence-backed-final | 5 |
| using-git-worktrees | 4 |
| accessibility-tree-inspection | 3 |
| form-interaction-flow | 3 |

## Task Results

| Task ID | Recall@5 | Negative Hit Rate | Latency (ms) |
| --- | ---: | ---: | ---: |
| browser-accessibility-audit | 1.000 | 0.000 | 2.266 |
| browser-form-regression | 1.000 | 0.000 | 0.423 |
| browser-local-dashboard | 1.000 | 1.000 | 0.444 |
| claude-command-routing | 1.000 | 1.000 | 0.549 |
| claude-mcp-selection | 1.000 | 0.000 | 0.456 |
| claude-plan-to-tasks | 1.000 | 0.000 | 0.429 |
| codex-git-hygiene | 1.000 | 0.000 | 0.437 |
| codex-minimal-diff | 1.000 | 0.000 | 0.511 |
| codex-worker-handoff | 1.000 | 0.000 | 0.477 |
| sp-debug-red-green | 1.000 | 1.000 | 0.440 |
| sp-isolated-worktree | 1.000 | 0.000 | 0.408 |
| sp-verify-before-claim | 1.000 | 0.000 | 0.449 |

## Failure Cases

| Task ID | Selected Skill IDs | Gold Skills | Recall@5 | Negative Hit Rate |
| --- | --- | --- | ---: | ---: |
| browser-local-dashboard | browser-smoke-testing, visual-regression-review, form-interaction-flow, test-driven-development, systematic-debugging | browser-smoke-testing, visual-regression-review | 1.000 | 1.000 |
| claude-command-routing | slash-command-workflow, apply-patch-discipline, subagent-worker-protocol, workspace-git-hygiene, evidence-backed-final | slash-command-workflow | 1.000 | 1.000 |
| sp-debug-red-green | test-driven-development, systematic-debugging, visual-regression-review, browser-smoke-testing, mcp-tool-routing | systematic-debugging, test-driven-development | 1.000 | 1.000 |
