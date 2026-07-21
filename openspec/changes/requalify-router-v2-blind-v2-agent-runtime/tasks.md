## 1. Preserve terminal and scientific authority

- [x] 1.1 Re-read and hash the canonical `agent-config-smoke-terminal.json`; assert `failure_stage=agent_config_smoke`, candidate count zero, no Commit B, no Arm A/C load, no model score, no formal evaluation, and no attempt marker.
- [x] 1.2 Add a frozen-constant regression proving Generator `gpt-5.6-sol/max`, Reviewer A `gpt-5.6-sol/ultra`, Reviewer B `gpt-5.6-luna/max`, 256 first-round candidates, 128/96 freeze, contamination thresholds, selection seed/order, Arm A/C identities, seeds, pilot-002 gate, and one-attempt policy are unchanged.
- [x] 1.3 Add a changed-surface guard that rejects edits to training data, checkpoints, pilot-001/pilot-002 artifacts, candidate data, README/resume/interview surfaces, release state, or default-router state.

## 2. Add RED tests for Stage 0 eligibility and receipts

- [x] 2.1 Add failing tests for a zero-exposure eligibility validator that accepts only the exact preserved terminal/Commit A-agent authority and returns `AGENT_RUNTIME_STAGE0_AUTHORITY_DRIFT` before any invocation on every drift or exposure case.
- [x] 2.2 Replace the old mandatory `returned_model == requested_model` fixture with failing host-envelope tests covering nullable provider metadata, `INTERFACE_UNAVAILABLE`, matching metadata, conflicting metadata, and rejection of Agent self-report as identity evidence.
- [x] 2.3 Add failing strict-canary tests covering role-specific nonces, canonical JSON equality, duplicate keys, extra/missing fields, surrounding prose, invalid UTF-8, and semantic mismatch.
- [x] 2.4 Add failing isolation/lineage tests requiring fresh non-forked sessions, empty history, zero imported memory, zero tools, zero descendants, one response, one top-level invocation per role, and a terminal `LINEAGE_UNVERIFIABLE` path when evidence is absent.
- [x] 2.5 Add failing terminal-vocabulary tests for qualified, config-unavailable, canary-mismatch, isolation-violation, lineage-unverifiable, transport-failure, and authority-drift outcomes, all with `KEEP_BASELINE` and unchanged production/release/default-router fields.
- [x] 2.6 Add failing no-retry tests proving any transport or substantive failure ends Stage 0 and never creates a fourth top-level invocation, fallback alias, lower reasoning effort, or repaired response.

## 3. Implement the bounded host-envelope qualification contract

- [x] 3.1 Add a strict Stage 0 input/receipt schema beside the existing Agent-config smoke helpers in `router_v2_blind_v2_evaluation_runner.py`; keep the legacy v1 receipt readable only as failed audit history.
- [x] 3.2 Implement zero-exposure eligibility validation against the canonical terminal artifact, Commit A-agent `50069a124a8d129e11926e78d1bcc2388bc91a22`, and immutable terminal hashes before parsing any role receipt.
- [x] 3.3 Implement canonical role canary construction and duplicate-key-rejecting response validation with exactly `protocol`, `role`, `nonce`, and `status=READY`.
- [x] 3.4 Implement host-envelope validation for exact requested aliases/efforts, `fork_context=false`, returned Agent identifiers, response hashes, nullable provider metadata, and explicit identity-evidence classification.
- [x] 3.5 Implement positive isolation-lineage validation and fail closed when tool/descendant/history/memory/response-count evidence is invalid or unavailable.
- [x] 3.6 Implement exclusive, hash-bound Stage 0 qualification/terminal receipts outside the formal evaluation attempt namespace; prohibit overwrite and preserve every failed receipt.
- [x] 3.7 Run the new focused RED-to-GREEN batch plus the existing Task 6/7 smoke, Commit A authority, request, pack, model-smoke-order, and single-attempt regressions without invoking a real Agent.

## 4. Add CLI validation without embedding Agent execution

- [x] 4.1 Add a CLI command that reads a predeclared external Stage 0 host-envelope ledger, validates it, and prints only the qualified or exact fail-closed state; the Python CLI MUST NOT spawn or call an Agent itself.
- [x] 4.2 Require the CLI to validate exactly three ordered top-level role rows and reject retries, extra/nested invocations, unknown fields, symlinks below the frozen trusted `/tmp` entry, duplicate JSON keys, non-private paths, and authority drift.
- [x] 4.3 Keep `request-round-1`, `request-reviews`, `request-round-2`, `pack-status`, `freeze`, `model-smoke`, and `evaluate` blocked under the terminalized Commit A-agent; only a separately authorized Commit A2 may restore the existing command sequence.
- [x] 4.4 Add CLI tests for help text, qualified status, each terminal status, no-write validation failures, and absence of candidate/model/attempt side effects.

## 5. Bind the successor protocol and Commit A2 template

- [x] 5.1 Update `docs/router-v2-blind-v2-protocol.md` and `artifacts/router-v2-blind-v2/preregistration.json` only for Stage 0, host-envelope identity evidence, canonical canaries, terminal vocabulary, and conditional Commit A2 supersession.
- [x] 5.2 Bind the prior Commit A-agent, terminal commit/artifact hashes, Stage 0 schema/prompts/nonces, exact role configurations, zero-exposure fields, and `supersession_reason=PRE_DATA_HOST_ATTESTATION_CONTRACT_REPAIR`.
- [x] 5.3 Regenerate canonical hashes and prove every dataset/review/contamination/model/metric/gate/seed/attempt/claim field is unchanged from Commit A-agent.
- [x] 5.4 Add Commit A2 authority tests requiring a qualified receipt, fresh zero-exposure audit, clean worktree, exact changed-file boundary, and explicit commit authorization; classify it as pre-data contract repair rather than attempt-2 or a new blind set.
- [x] 5.5 Keep Candidate generation blocked until the actual Stage 0 receipt hash is inserted and a separately authorized Commit A2 exists; do not fabricate a placeholder qualification receipt.

## 6. Validate and review the apply diff before any experimental Agent call

- [x] 6.1 Run focused qualification and existing blind-v2 regression suites with cache disabled where relevant; report exact pass/fail counts.
- [x] 6.2 Run Ruff/format and mypy on changed Python surfaces, `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`, `git diff --check`, frozen-artifact guards, no-training guards, and no-candidate/no-model/no-attempt guards.
- [x] 6.3 Perform a main-thread read-only acceptance review because this change forbids review Agent invocation before Stage 0; return Must Fix, Should Fix, Re-plan Needed, and Final Verdict.
- [x] 6.4 Stop with an uncommitted apply diff and request user review. Do not commit, push, mutate PR #39, generate a Human Brief, or invoke the three experimental roles.

## 7. Run the separately authorized Stage 0 Goal

- [x] 7.1 After explicit Goal authorization, revalidate zero exposure and create the private, exclusive host-envelope ledger path; stop before any call if authority drift exists.
- [x] 7.2 Invoke exactly Generator `gpt-5.6-sol/max`, Reviewer A `gpt-5.6-sol/ultra`, and Reviewer B `gpt-5.6-luna/max` once each with the frozen dummy canary, `fork_context=false`, no imported history/memory, and no retry.
- [x] 7.3 Record host call envelopes, Agent identifiers, raw/canonical response hashes, provider-metadata status, and positive tool/descendant lineage evidence without reading candidate data or loading Arm A/C.
- [x] 7.3a Repair the macOS pre-receipt path failure by allowing only the frozen platform `/tmp` alias to resolve to a sticky temporary directory while continuing to reject descendant symlinks; preserve the ledger bytes/hash and do not invoke another Agent or rerun the CLI.
- [x] 7.4 Validate the ledger with the CLI and write exactly one qualified or fail-closed Stage 0 terminal receipt; on failure stop the Goal immediately with `KEEP_BASELINE`.
- [x] 7.5 If qualified, report only runtime qualification and request separate Commit A2 authorization; do not create Commit A2, generate candidates, run full CI, push, or update PR #39 inside Goal A.

## 8. Gate Commit A2 and later blind-v2 execution

- [x] 8.1 After separate commit authorization, insert the actual qualified receipt hash, rerun fresh validation/review, and create Commit A2 without rewriting the prior terminal history.
- [x] 8.1a Before Commit A2, harden terminal receipt creation and validation to require a regular `0600` file under a `0700` private parent; repair the existing unique receipt by changing mode only, prove its bytes/self-hash/filename are unchanged, and do not rerun the CLI or any Agent.
- [x] 8.1b Before candidate generation, propagate the nullable provider-model status and positive host-lineage contract through formal Generator/Reviewer envelopes, external metadata, sanitized/retry records, freeze, and evaluation replay; preserve response self-report as non-authoritative and keep the legacy strict smoke history-only.
- [ ] 8.2 Confirm Commit A2 is clean authority and that no candidate/model/attempt exposure occurred before it; otherwise record `KEEP_BASELINE` and stop.
- [ ] 8.3 Require a new explicit full-execution Goal before `request-round-1`; keep generation, dual review, Commit B, A/C model smoke, and the unique formal attempt outside this runtime-requalification change.
- [ ] 8.4 Preserve the final claim boundary as `AGENT_GENERATED / DUAL_AGENT_UNANIMOUS_REVIEWED`, `human_author_count=0`, `human_reviewer_count=0`, same-provider correlation disclosed, and no human-reviewed/statistically-independent claim.
