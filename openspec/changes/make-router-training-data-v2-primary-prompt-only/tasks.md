## 1. Baseline and Scope Guards

- [x] 1.1 In the isolated apply worktree, record `pwd`, clean `git status --short`, branch, HEAD, and the stacked baseline `4f995c2595a6314ae86111a54409af9f7243b51a`; stop if the baseline or worktree is unexpected.
- [x] 1.2 Record the v1 SHA-256 values of `candidate-pairs.jsonl`, `qualification-report.json`, and `manifest.json`, plus Git blob identities for `benchmarks/blind-migration-tasks/**` and Phase 14–18 demo paths, before implementation.
- [x] 1.3 Run the existing focused Router Training Data V2 tests and confirm the current v1 pack is reproducible before introducing v2 expectations.
- [x] 1.4 Establish a changed-path allowlist limited to the prompt-only qualification source, focused tests, the three canonical machine artifacts, the pack README, the v1 historical brief, the new apply brief, and this OpenSpec change; explicitly deny training/runtime-router, blind, and Phase 14–18 paths.

## 2. TDD RED Contract Tests

- [x] 2.1 Add a focused test requiring each candidate `query_text` to equal the loader-normalized `task.prompt` byte-for-byte and requiring `sha256(query_text.encode("utf-8")) == prompt_text_sha256`; run it and capture the expected RED failure against v1.
- [x] 2.2 Add isolated metadata-invariance tests that vary valid task ID, category, difficulty, and robustness tags while holding the prompt constant, and require identical query bytes and prompt hash; run them RED before implementation.
- [x] 2.3 Add RED tests for `router-training-data-v2-candidate-v2`, row-level `query_text_policy="prompt_only"`, the exact candidate field set, and absence of any legacy/alternate/composite/second primary-query field.
- [x] 2.4 Add RED tests for `router-training-data-v2-qualification-v2`, report/manifest v2 schemas, `artifact_version=2`, and the exact identical machine-readable query contract in report and manifest.
- [x] 2.5 Extend canonical and artifact tests to lock 192/16/32/144/64/32/0/11-of-16/0, all eight blocker codes, `REVIEW_REQUIRED`, `KEEP_BASELINE`, `can_start_training=false`, `accepted_for_training=false`, and absence of both `training-pairs.jsonl` and `training-pairs-v2.jsonl`; confirm failures are only the intended v1-to-v2 contract gap.

## 3. Minimal Prompt-Only Implementation

- [x] 3.1 In `src/hermes_skilleval/router_training_data_v2.py`, advance only the qualification policy, candidate, report, and manifest identifiers to the approved v2 values and define the single immutable query-contract object.
- [x] 3.2 Replace the candidate primary-query construction with direct loader-normalized `task.prompt`, compute `prompt_text_sha256` from those same UTF-8 bytes, and add only `query_text_policy="prompt_only"`; do not modify generic training or runtime-router text helpers.
- [x] 3.3 Add the identical query contract to report and manifest, set manifest `artifact_version=2`, and preserve classification, dispositions, counts, blockers, readiness, non-actions, input provenance, and fresh-target publication behavior.
- [x] 3.4 Run the focused unit contract suite to GREEN and inspect serialized rows to confirm category can still drive candidate classification without entering the query and that no secondary query representation exists.

## 4. Fresh-Target Regeneration and Hash Binding

- [x] 4.1 Regenerate the pack twice into two fresh absent temporary targets from the canonical non-blind tasks and 16-skill index; compare all three machine artifacts byte-for-byte and require deterministic v2 output.
- [x] 4.2 Validate both fresh targets for exact schemas/query contracts, canonical counts/blockers/readiness, repository-relative provenance, valid input/output hashes, and absence of trainer-ready files before touching the committed pack.
- [x] 4.3 Compute fresh SHA-256 values and require candidate, report, and manifest hashes each to differ from its recorded v1 hash; then replace only the three machine files under the existing canonical pack path without creating a second pack path.
- [x] 4.4 Update frozen artifact-hash expectations with the computed v2 values and prove that a third fresh-target regeneration matches the committed machine artifacts byte-for-byte and by SHA-256.

## 5. Current and Historical Truth Surfaces

- [x] 5.1 Update the pack README to describe the prompt-only v2 contract, current v2 identifiers and computed hashes, unchanged qualification truth, fresh-target reproduction, and active OpenSpec links whose resolved targets exist.
- [x] 5.2 Mark `docs/human-briefs/2026-07-11-build-router-training-data-v2-qualification-pack.html` visibly as `HISTORICAL_V1_SNAPSHOT`; state that its v1 hashes/query evidence are historical and link to the current v2 apply brief and machine artifacts without rewriting its historical qualification result.
- [x] 5.3 Create `docs/human-briefs/2026-07-11-make-router-training-data-v2-primary-prompt-only-apply.html` from fresh artifacts and validation evidence, showing prompt-only v2, all canonical blocked truth, and explicit no-training/no-GPU/no-checkpoint/no-blind-rerun/no-performance-claim/no-commit/no-push/no-PR/no-merge/no-archive/no-release boundaries; state that it is not a second source of truth.
- [x] 5.4 Update visible-text and real-path tests so the README, proposal brief, apply brief, historical v1 brief, OpenSpec links, machine artifacts, and validation references cannot be stale, contradictory, or broken.

## 6. Regression, Provenance, and Protected-Evidence Guards

- [x] 6.1 Run focused builder and committed-artifact tests covering metadata invariance, prompt/hash equality, exact v2 fields/contracts, deterministic regeneration, all counts/blockers/readiness, current/historical document truth, and real link resolution.
- [x] 6.2 Re-run blind preflight and protected-output tests and prove no blind prompt was read, hashed, copied, mined, calibrated on, or selected against.
- [x] 6.3 Compare Git blob identities for `benchmarks/blind-migration-tasks/**` and Phase 14–18 demo paths with the recorded baseline and require zero changes.
- [x] 6.4 Audit `git diff --name-only` against the allowlist and require no changes to task metadata/prompts, skill index, `embedding_training`, runtime routers, training scripts, thresholds, Phase 14–18 results, or unrelated repositories.

## 7. Full Verification and Read-Only Review

- [x] 7.1 Run the full pytest suite and require all tests to pass with fresh output recorded.
- [x] 7.2 Run scoped Ruff check and format-check commands on every changed Python file, plus `git diff --check`, and require clean results.
- [x] 7.3 Run strict validation for `make-router-training-data-v2-primary-prompt-only` and `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`; require the change to remain apply-complete but unarchived.
- [x] 7.4 Run the release reproducibility gate with fresh temporary Phase 17/18 outputs, require `PASS` / `KEEP_BASELINE`, and verify that committed Phase 14–18 artifacts were not rewritten.
- [x] 7.5 Start a read-only Reviewer over the complete diff and require sections `Must Fix`, `Should Fix`, `Nice to Have`, `Re-plan Needed`, and `Final Verdict`; the Reviewer must not edit files.
- [x] 7.6 If `Re-plan Needed = No`, return only in-scope Must Fix items to the sole Worker, rerun focused and full verification, and obtain a final read-only verdict; if `Re-plan Needed = Yes`, stop and revise OpenSpec before further implementation.
- [x] 7.7 Report changed files, v1→v2 hashes, RED/GREEN and full-validation evidence, preserved truth/protected identities, remaining risks, and clean/dirty status, then stop for user review without commit, push, PR, merge, archive, tag, release, deploy, training, A100/GPU work, checkpoint creation, or blind evaluation.
