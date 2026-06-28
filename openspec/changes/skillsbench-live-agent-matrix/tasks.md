## 1. OpenSpec And Scope

- [x] 1.1 Create change `skillsbench-live-agent-matrix` with proposal, design,
  tasks, and `live-agent-runtime` spec delta.
- [x] 1.2 Keep PR-6 limited to SkillsBench adapter, task selection/freeze,
  oracle qualification, and three-condition matrix planning/execution helpers.

## 2. Fixtures And Adapter

- [x] 2.1 Add tiny SkillsBench-shaped fixture with tasks, skills, verifier
  metadata, oracle qualification records, routed predictions, and optional
  SkillRouter overlap IDs.
- [x] 2.2 Add RED tests for adapter validation: malformed files, duplicate IDs,
  missing deterministic verifier, private credential requirement, uncontrolled
  network requirement, and missing oracle qualification for frozen plans.
- [x] 2.3 Implement adapter records, provenance hashes, deterministic verifier
  parsing, and fail-closed validation.

## 3. Freeze Plan And Registry

- [x] 3.1 Add RED tests that pilot and frozen plans are separate and frozen
  plans require oracle qualification.
- [x] 3.2 Add RED tests that the skill registry is global across selected tasks,
  includes all oracle/routed skills, and fails on missing skill definitions.
- [x] 3.3 Implement plan writing with input SHA-256/size provenance, run IDs,
  selected tasks, global skill registry, and matrix output path.

## 4. Three-Condition Matrix

- [x] 4.1 Add RED tests for no-skill/routed-skill/oracle-skill entries sharing
  the same prompt hash.
- [x] 4.2 Add RED tests that each run receives a fresh workspace and verifier
  pass/fail remains the only task-success source.
- [x] 4.3 Implement matrix execution helpers using PR-4 runtime and PR-5 runner
  interfaces, with fake runner/verifier tests only.
- [x] 4.4 Record `live-agent.v1` trace paths, skill inventory, skill-use
  evidence, timeout, process exit, verifier result, and redacted events.

## 5. CLI, Reports, And Docs

- [x] 5.1 Add scoped CLI commands for SkillsBench validation, plan freeze, and
  matrix execution.
- [x] 5.2 Add SkillRouter overlap report scaffold for selected task metadata.
- [x] 5.3 Add concise Chinese Human Brief for PR-6 and link it from the v0.3
  implementation guide.

## 6. Validation

- [x] 6.1 Run focused SkillsBench live-agent tests.
- [x] 6.2 Run `python -m pytest -q`.
- [x] 6.3 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 6.4 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check --phase17-output-dir docs/demo/phase17-calibrated-release-selector --release-output-dir docs/demo/phase18-ci-release-reproducibility`.
- [x] 6.5 Run `git diff --check`.
- [x] 6.6 Run v0.3 YAML parse check.
- [x] 6.7 Run CRLF/new-file line-ending check.
