## 1. OpenSpec And Scope

- [x] 1.1 Create change `live-agent-runtime-fake` with proposal, design,
  tasks, and `live-agent-runtime` spec.
- [x] 1.2 Keep PR-4 limited to fake `live-agent.v1` runtime abstraction; do
  not modify Phase 10 replay, external matrix, scorer, router promotion, or
  release gate logic.

## 2. Runtime Contract And Conditions

- [x] 2.1 Add RED tests for `AgentRunner` protocol, request/result dataclasses,
  and `live-agent.v1` trace schema fields.
- [x] 2.2 Implement live-agent runtime dataclasses, protocol, schema constants,
  and serialization helpers.
- [x] 2.3 Add RED tests for `no-skill`, `routed-skill`, and `oracle-skill`
  condition builders preserving prompt hashes.
- [x] 2.4 Implement condition builders and no-skill leakage validation.

## 3. Workspace And Skill Mounting

- [x] 3.1 Add RED tests for fresh workspace preparation, workspace reuse
  failure, and workspace-local skill mounting.
- [x] 3.2 Implement isolated workspace preparation and mounted skill hash
  records.

## 4. Fake Runner, Verifier, And Trace

- [x] 4.1 Add RED tests for fake-runner success, verifier failure, process
  failure, and timeout.
- [x] 4.2 Implement fake runner, fake verifier, and execution orchestration.
- [x] 4.3 Add RED tests that process exit code is separate from verifier
  pass/fail and task success derives from verifier outcome.
- [x] 4.4 Add RED tests for `MOUNTED_ONLY`, `READ`, `DECLARED`, and `UNKNOWN`
  skill-use evidence.
- [x] 4.5 Implement live-agent trace rendering with usage/cost `null` when
  unavailable.

## 5. Error Handling And Redaction

- [x] 5.1 Add RED tests for malformed event fail-closed behavior.
- [x] 5.2 Add RED tests for unknown event preservation without crashing.
- [x] 5.3 Add RED tests for secret redaction and log truncation.
- [x] 5.4 Implement event parsing, unknown-event preservation, redaction, and
  log truncation.

## 6. Documentation And Human Brief

- [x] 6.1 Add concise Chinese Human Brief for PR-4 with scope, changed files,
  verification, limits, and next step.
- [x] 6.2 Link PR-4 Human Brief from v0.3 implementation guide only if needed.

## 7. Validation

- [x] 7.1 Run focused live-agent runtime tests.
- [x] 7.2 Run `python -m pytest -q`.
- [x] 7.3 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 7.4 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check --phase17-output-dir docs/demo/phase17-calibrated-release-selector --release-output-dir docs/demo/phase18-ci-release-reproducibility`.
- [x] 7.5 Run `git diff --check`.
- [x] 7.6 Run v0.3 YAML parse check.
- [x] 7.7 Run CRLF/new-file line-ending check.
