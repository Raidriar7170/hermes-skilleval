# Phase 10 Agent-in-the-loop Report

- Run: agent-loop-hybrid
- Source router: hybrid
- Execution condition: routed-skill
- Tasks: 12
- Agent success rate: 0.750
- Mean evidence completion: 0.750

## Task Results

| Task ID | Success | Selected Skills | Failure Type |
| --- | --- | --- | --- |
| browser-accessibility-audit | True | accessibility-tree-inspection, browser-smoke-testing, form-interaction-flow, visual-regression-review, workspace-git-hygiene |  |
| browser-form-regression | True | browser-smoke-testing, visual-regression-review, form-interaction-flow, accessibility-tree-inspection, systematic-debugging |  |
| browser-local-dashboard | False | browser-smoke-testing, visual-regression-review, form-interaction-flow, test-driven-development, systematic-debugging | negative_skill_selected |
| claude-command-routing | False | slash-command-workflow, apply-patch-discipline, subagent-worker-protocol, workspace-git-hygiene, evidence-backed-final | negative_skill_selected |
| claude-mcp-selection | True | mcp-tool-routing, task-tool-delegation, browser-smoke-testing, visual-regression-review, systematic-debugging |  |
| claude-plan-to-tasks | True | plan-mode, evidence-backed-final, subagent-worker-protocol, systematic-debugging, apply-patch-discipline |  |
| codex-git-hygiene | True | workspace-git-hygiene, using-git-worktrees, apply-patch-discipline, slash-command-workflow, accessibility-tree-inspection |  |
| codex-minimal-diff | True | apply-patch-discipline, subagent-worker-protocol, using-git-worktrees, workspace-git-hygiene, mcp-tool-routing |  |
| codex-worker-handoff | True | subagent-worker-protocol, evidence-backed-final, using-git-worktrees, apply-patch-discipline, workspace-git-hygiene |  |
| sp-debug-red-green | False | test-driven-development, systematic-debugging, visual-regression-review, browser-smoke-testing, mcp-tool-routing | negative_skill_selected |
| sp-isolated-worktree | True | using-git-worktrees, workspace-git-hygiene, subagent-worker-protocol, evidence-backed-final, apply-patch-discipline |  |
| sp-verify-before-claim | True | verification-before-completion, systematic-debugging, evidence-backed-final, subagent-worker-protocol, test-driven-development |  |
