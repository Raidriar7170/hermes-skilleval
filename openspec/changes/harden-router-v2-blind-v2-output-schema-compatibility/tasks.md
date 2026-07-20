## 1. Freeze successor authority

- [x] 1.1 Add tests that pin the historical schema constants and terminal marker while proving successor canaries cannot ingest old candidates, prompts, responses, scores, or evaluation inputs
- [x] 1.2 Add successor authority constants for the terminal commit, Codex executable/version, exact CLI flags, three role model/effort pairs, synthetic payloads, authorization denials, and public/private evidence paths

## 2. Build strict schemas with TDD

- [x] 2.1 Add RED tests for recursively nested untyped `const`, untyped/incompatible `enum`, supported `anyOf[index]` traversal, fail-closed `$defs`, unsupported composition/conditional/`minLength`/`maxLength` keywords, open/incompletely-required objects, missing array items, and non-object roots
- [x] 2.2 Implement the recursive compatibility validator with stable nested/indexed paths and a zero-finding success contract
- [x] 2.3 Add versioned Generator and Reviewer successor schemas with explicit types, supported `pattern` constraints, and no unsupported keywords including `minLength`/`maxLength`, while leaving historical schema constants unchanged
- [x] 2.4 Add GREEN tests for both successor schemas and deterministic Reviewer decision/rubric plus null-negative validation

## 3. Build the one-shot exact-host preflight

- [x] 3.1 Add mocked RED tests for validation-before-launch, exact three-role argv/configuration, isolated private roots, synthetic stdin only, no retry/fallback/fork, timeout/process/output failure, and exact-object response validation
- [x] 3.2 Implement the successor-only preflight controller and CLI entry point without exposing formal candidate-generation behavior
- [x] 3.3 Add tests for `0700` directories, `0600` regular files, symlink rejection, canonical hashes, sanitized public receipt fields, self-hash validation, and fail-closed terminal truth
- [x] 3.4 Run focused schema/controller tests, formatter/lint/type checks for touched Python, applicable regression tests, strict OpenSpec validation, and `git diff --check`

## 4. Execute and freeze preflight evidence

- [x] 4.1 Revalidate clean host/interface/schema authority, then invoke Generator, Reviewer A, and Reviewer B exactly once each through `codex exec --output-schema` with no retry
- [x] 4.2 Validate private evidence and write the sanitized public receipt as either `PREFLIGHT_READY / KEEP_BASELINE` or a specific fail-closed `PREFLIGHT_*_BLOCKED / KEEP_BASELINE`
- [x] 4.3 Confirm no formal candidate, Arm A/C, score, Commit B, evaluation, training, Git publication, release, or archive artifact was created or authorized

## 5. Human review and closeout

- [x] 5.1 Generate the Chinese Human Brief with root cause, exact frozen interface, RED/GREEN evidence, per-role canary result, limitations, terminal truth, and next authorization boundary
- [x] 5.2 Obtain read-only Reviewer findings and resolve any in-scope blocker without rerunning a role call
- [x] 5.3 Run fresh final verification and report the local uncommitted worktree state without committing, pushing, creating a PR, or archiving the change
