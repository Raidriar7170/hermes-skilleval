## 1. Recover and freeze authority

- [x] 1.1 Verify PR #38 merged, the branch starts at current `origin/main`, public Router V2 counts/limitations remain unchanged, and the new worktree is clean.
- [x] 1.2 Recompute tracked pilot hashes plus all Arm A/C manifest, model-file, training-metadata, frozen-input, and run-pack hashes and sizes without loading blind data.
- [x] 1.3 Record the pre-existing `origin/main` full-suite and GitHub Validate failures as baseline evidence without repairing them in this change.

## 2. Freeze Commit A before blind-v2 access

- [x] 2.1 Add RED tests for the 64/48 contract, unchanged gate, A/C-only metrics, statistical definitions, preregistration truth fields, and forbidden post-data actions.
- [x] 2.2 Implement the dedicated evaluation contract and pure metrics/statistics builders, then make the focused tests GREEN.
- [x] 2.3 Add RED tests for external-pack validation, privacy-preserving freeze output, A/C synthetic smoke, frozen-hash preflight, output-root safety, and terminal single-attempt behavior.
- [x] 2.4 Implement the dedicated runner and CLI, then make the focused runner tests GREEN without modifying pilot-001/002 code or artifacts.
- [x] 2.5 Add `docs/router-v2-blind-v2-protocol.md` and `artifacts/router-v2-blind-v2/preregistration.json` binding source/model/data/gate/evaluator hashes and `blind_v2_data_seen=false`.
- [x] 2.6 Run focused tests, Ruff, mypy, OpenSpec strict validation, frozen-artifact guards, and `git diff --check`; then create Commit A `docs(router): preregister final Router V2 blind-v2` and record its SHA.
- [x] 2.7 Convert final Reviewer findings into RED tests and repair env-only freeze authority, private-prompt exact regeneration, exact Commit A/B preflight, per-query warm-up, eight-decimal ranking, and complete marker/terminal lineage before any blind data access.

## 3. Run the pre-data model smoke

- [ ] 3.1 On clean Commit A, run the fixed-string real-load smoke for Arm A and Arm C seeds `7170`, `7171`, and `7172` on CPU, verify finite equal-dimension embeddings, remove temporary files, and stop on any failure.

## 4. Gate on external human data

- [ ] 4.1 After Commit A and smoke only, check `HERMES_BLIND_V2_ROOT` and the three required external files without allowing repository-local input.
- [ ] 4.2 If the pack is absent or incomplete, generate only blank authoring/review/metadata templates and a human guide under `/tmp/hermes-blind-v2-authoring-pack/`, report the 64/48 deficits, and stop at `BLIND_V2_WAITING_FOR_HUMAN_DATA`.

## 5. Conditionally freeze Commit B

- [ ] 5.1 If the pack is complete, run static-only schema, review, distribution, leakage, exact/near-duplicate, and family-disjointness validation with no model load or score.
- [ ] 5.2 Generate the privacy-appropriate three-file dataset freeze, verify exact-byte regeneration and `model_scores_observed=false`, then create Commit B `data(router): freeze human-reviewed Router V2 blind-v2`.

## 6. Conditionally execute the unique attempt

- [ ] 6.1 Create a fresh clean Commit B worktree, revalidate every hash/count/marker/namespace/smoke condition, and create the exclusive `attempt-1.started.json` marker.
- [ ] 6.2 Evaluate only Arm A and Arm C for all three seeds with fixed order/device/warm-up/timer, retain terminal failure evidence on any exception, and never retry.
- [ ] 6.3 Generate per-seed, aggregate, paired, statistical, failure-slice, summary, report, and complete lineage artifacts; mechanically apply the unchanged gate.

## 7. Conditionally close out the project

- [ ] 7.1 Update only `README.md`, `README_EN.md`, `docs/resume.md`, and `docs/interview-project-overview.html` with the actual supported/not-supported/infrastructure-failure result and unchanged-default limitations.
- [ ] 7.2 Run the required focused/full validations, prove all frozen old artifacts and no-training/non-action constraints, and obtain a read-only Reviewer verdict in the required format.
- [ ] 7.3 Fix only non-result-changing Must Fix items, create the final result commit, push the branch, and create one PR without merge, tag, release, deploy, archive, or router promotion.
