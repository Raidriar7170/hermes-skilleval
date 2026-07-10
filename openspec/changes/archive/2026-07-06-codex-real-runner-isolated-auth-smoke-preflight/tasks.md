## 1. Proposal Closeout

- [x] 1.1 Create a dedicated worktree and branch from latest `origin/codex/v0.3-pr0-protocol`.
- [x] 1.2 Create OpenSpec proposal, design, delta spec, and tasks for isolated-auth smoke/preflight.
- [x] 1.3 Validate proposal artifacts with `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 1.4 Add a concise Chinese Human Brief for the proposal stage.
- [x] 1.5 Commit, push, and open a draft PR for proposal review.

## 2. Base and Boundary Verification

- [x] 2.1 Confirm PR #18 and PR #19 merge commits are reachable from the base branch.
- [x] 2.2 Confirm the archived PR #18 artifact remains
  `BLOCKED_ISOLATED_CODEX_HOME_AUTH_401_AFTER_PREFLIGHT`.
- [x] 2.3 Confirm `execution_readiness=false` and
  `can_be_used_as_real_stage2_input_package_now=false` before any new smoke.
- [x] 2.4 Confirm no Stage 2 task manifests, public prompts, oracle/verifier evidence,
  routed predictions, scorer/matrix/evidence-gate semantics, or router defaults changed.

## 3. Isolated Auth Materialization

- [x] 3.1 Identify the minimal installed Codex CLI authentication material required for
  isolated smoke/preflight without printing or committing secret values.
- [x] 3.2 Create a fresh isolated `HOME` / `CODEX_HOME` runtime workspace.
- [x] 3.3 Materialize only allowlisted authentication files into isolated `CODEX_HOME`.
- [x] 3.4 Record auth provenance summary, file presence, sizes, and hashes where safe.
- [x] 3.5 Confirm clean user, admin, and workspace skill inventory after auth materialization.

## 4. Minimal Non-Task Smoke/Preflight

- [x] 4.1 Capture Codex CLI path, version, and `exec --help` hashes.
- [x] 4.2 Run only the minimal non-task Codex runner smoke/preflight command needed to
  prove isolated authentication and runner wiring.
- [x] 4.3 Record command lines, stdout/stderr paths and hashes, prompt hash,
  environment allowlist, sandbox mode, approval policy, and terminal status.
- [x] 4.4 Confirm no selected Stage 2 task IDs or public prompts were used.
- [x] 4.5 Confirm no task traces, 4x3x1 matrix output, pilot freeze output, evidence-gate
  output, oracle qualification output, verifier rewrite, routed-prediction rewrite, or
  performance claim was created.

## 5. Evidence and Review

- [x] 5.1 Add the bounded isolated-auth smoke/preflight JSON artifact.
- [x] 5.2 Add a concise Chinese Human Brief for the smoke/preflight result.
- [x] 5.3 Run JSON/JSONL parse checks and provenance/readiness guard scans.
- [x] 5.4 Run prohibited true-flag, execution marker, trace, and performance-claim scans.
- [x] 5.5 Run `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q`.
- [x] 5.6 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 5.7 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check`.
- [x] 5.8 Run `git diff --check`.
- [x] 5.9 Commit, push, and open a draft PR against `codex/v0.3-pr0-protocol`.
