## 1. Base Hygiene

- [x] 1.1 Fetch latest remote refs and create the branch from latest `origin/codex/v0.3-pr0-protocol`.
- [x] 1.2 Confirm PR #13, #14, #15, #16, and #17 merge commits are reachable.
- [x] 1.3 Confirm Issue #11 is closed and the worktree is clean before edits.

## 2. Prerequisite Artifact Verification

- [x] 2.1 Confirm required Stage 2 package, oracle, validator, routed prediction, privacy, and static preflight artifacts exist.
- [x] 2.2 Record required artifact SHA-256 hashes.
- [x] 2.3 Confirm 4/4 tasks are qualified, 4/4 verifier records passed, validator status is PASS, human privacy acceptance is recorded, and execution readiness remains false.

## 3. Codex Runner Smoke/Preflight

- [x] 3.1 Capture Codex CLI path, version, and `exec --help` output with hashes.
- [x] 3.2 Create isolated `HOME` / `CODEX_HOME` runtime workspace.
- [x] 3.3 Run the minimal non-task `CodexCliRunner` smoke/preflight invocation needed to prove runner wiring and isolation.
- [x] 3.4 Record command lines, stdout/stderr paths, output hashes, environment allowlist, network/sandbox mode, and clean skill inventory.

## 4. Evidence Artifacts

- [x] 4.1 Add the bounded smoke/preflight JSON artifact.
- [x] 4.2 Add a concise Chinese Human Brief.
- [x] 4.3 Confirm no Stage 2 task prompts, task traces, 4x3x1 matrix, pilot freeze, evidence gate rerun, oracle rerun, verifier rewrite, routed-prediction rewrite, or performance claim occurred.

## 5. Validation and Publication

- [x] 5.1 Run JSON/JSONL parse checks.
- [x] 5.2 Run provenance/readiness guard checks, prohibited true-flag scans, and execution marker / trace scans.
- [x] 5.3 Run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q`.
- [x] 5.4 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 5.5 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check`.
- [x] 5.6 Run `git diff --check`.
- [x] 5.7 Commit, push, and open a PR against `codex/v0.3-pr0-protocol`.
