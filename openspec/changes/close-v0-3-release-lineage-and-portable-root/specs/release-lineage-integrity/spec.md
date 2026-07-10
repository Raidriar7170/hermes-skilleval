## ADDED Requirements

### Requirement: Published release has truthful forward ancestry
The repaired branch SHALL contain both the refreshed `origin/main` base and the peeled `v0.3.0` release commit as ancestors of its final head.

#### Scenario: Both approved histories are ancestors
- **WHEN** lineage repair is complete
- **THEN** `git merge-base --is-ancestor <captured-origin-main> HEAD` succeeds
- **AND** `git merge-base --is-ancestor v0.3.0^{} HEAD` succeeds

### Requirement: Published tag identity remains immutable
The lineage repair SHALL preserve both the annotated `v0.3.0` tag object and its peeled commit target exactly as captured during preflight.

#### Scenario: Tag identity is unchanged after repair
- **WHEN** preflight and post-repair tag identities are compared
- **THEN** the tag object remains `f8656e336b35b703bc52acc4be9f5e55237cf7e1`
- **AND** the peeled target remains `7fd85579edc34d2207b6472d2aa000904cfb554d`

### Requirement: Bridge is a content-bearing merge
The lineage repair MUST use a non-fast-forward merge with exactly two parents: the first parent MUST be the Worker head immediately before the bridge, descended from the captured current main, and the second parent MUST be `7fd85579edc34d2207b6472d2aa000904cfb554d`. It MUST incorporate the release line's tree changes rather than simulating repair with squash, cherry-pick, rebase, retagging, or an `ours`/empty merge strategy.

#### Scenario: Merge topology and content are inspectable
- **WHEN** the bridge commit is inspected
- **THEN** it has exactly two parents in the approved first-parent/second-parent order
- **AND** its first-parent diff includes the non-conflicting release-line content plus the approved conflict resolutions

### Requirement: Conflict set is fail-closed
The bridge implementation SHALL manually resolve only `README.md` and `tests/test_project_surface.py`; any additional conflict or materially different preflight shape MUST stop implementation for renewed review.

#### Scenario: Rehearsed conflict set is unchanged
- **WHEN** the refreshed merge rehearsal reports exactly the two approved files
- **THEN** implementation may resolve those files using the approved conflict policy

#### Scenario: Unexpected conflict appears
- **WHEN** the refreshed merge rehearsal or real merge reports any other conflicted path
- **THEN** implementation stops before creating a completed bridge commit

### Requirement: Release and review truth surfaces remain consistent
After the bridge, package metadata, runtime version output, CLI version output, README/release presentation, and release checks SHALL agree on `0.3.0`, while existing `REVIEW_REQUIRED` and `KEEP_BASELINE` evidence-state markers MUST remain intact where applicable.

#### Scenario: Version surfaces agree
- **WHEN** release-surface validation runs against the repaired branch
- **THEN** every active version surface reports `0.3.0`
- **AND** no active surface reports package version `0.2.1`

#### Scenario: Evidence limitations remain truthful
- **WHEN** protected evidence and public wording are scanned after conflict resolution
- **THEN** `REVIEW_REQUIRED` and `KEEP_BASELINE` remain present in their applicable release evidence surfaces

### Requirement: Historical evidence is preserved
The portability step MUST use the completed bridge commit as its comparison baseline and MUST preserve the blob identities of `docs/demo/phase14-finetuned-embedding-router/**`, `docs/demo/phase15-held-out-generalization/**`, `docs/demo/phase16-blind-validation/regression-summary.json`, and `docs/demo/phase7a-cross-encoder/embedding-cache.json`. These historical evidence records MUST NOT be rewritten merely to replace recorded `/mnt/data/minghongsun` paths with portable examples.

#### Scenario: Historical artifacts are compared
- **WHEN** the protected evidence blobs at the bridge commit are compared with final `HEAD`
- **THEN** every protected path retains the same blob identity

### Requirement: Inherited whitespace exception is closed and hash-backed
The complete first-parent whitespace check for bridge `887672bba07235fd1b1d4c030866f4e74248c1c8` MUST be retained as an expected inherited failure and MUST NOT be described as passing. Its only accepted nonzero result is exit `2`, every diagnostic MUST be either `trailing whitespace` or `new blank line at EOF`, and every diagnostic MUST belong to exactly one of these five literal paths:

- `artifacts/v0.3/skillsbench-pilot/v0.3-stage2-input-package-candidate-20260701T010000Z/apt-source-diagnostics-20260702T052036Z/logs/docker-context-ls.log`
- `artifacts/v0.3/skillsbench-pilot/v0.3-stage2-input-package-candidate-20260701T010000Z/apt-source-diagnostics-20260702T052036Z/logs/docker-image-ls.log`
- `artifacts/v0.3/skillsbench-pilot/v0.3-stage2-input-package-candidate-20260701T010000Z/apt-source-diagnostics-20260702T052036Z/logs/docker-info.log`
- `artifacts/v0.3/skillsbench-pilot/v0.3-stage2-input-package-candidate-20260701T010000Z/apt-source-diagnostics-20260702T052036Z/logs/docker-run-python312-slim-network-shape.log`
- `artifacts/v0.3/skillsbench-pilot/v0.3-stage2-real-codex-12-run-execution-20260707T032920Z/command-output/codex-exec-help.stdout.txt`

The implementation MUST NOT use globs, directory-wide exclusions, `.gitattributes` suppression, or content normalization for this exception.

#### Scenario: Complete first-parent failure is fully accounted for
- **WHEN** `git diff --check 1c44972f2777eafbc1fe5b64b2e8e02a72917e79 887672bba07235fd1b1d4c030866f4e74248c1c8` runs
- **THEN** its exit status is exactly `2`
- **AND** its complete raw output contains only the five literal paths and two accepted diagnostic classes
- **AND** the raw output is retained losslessly with its SHA-256 as expected-failure evidence

#### Scenario: Exception-free bridge checks pass
- **WHEN** the first-parent check excludes exactly the five literal paths
- **THEN** `git diff --check` exits `0`
- **AND** the complete second-parent `git diff --check` exits `0`
- **AND** the first-parent check restricted to `README.md` and `tests/test_project_surface.py` exits `0`

#### Scenario: Allowlisted entries remain immutable through final head
- **WHEN** the five entries are inspected at the `v0.3.0` second parent, bridge, and final `HEAD`
- **THEN** each entry has the same tree mode and blob ID at all three points
- **AND** both second-parent-to-bridge and bridge-to-HEAD path-limited diffs exit `0`

#### Scenario: Ordinary new work has no exception
- **WHEN** post-bridge work is checked with `git diff --check 887672bba07235fd1b1d4c030866f4e74248c1c8 HEAD`
- **THEN** the command exits `0` without exclusions
- **AND** bridge `887672bba07235fd1b1d4c030866f4e74248c1c8` remains an ancestor of `HEAD`
- **AND** the recorded tag object and peeled commit IDs remain unchanged

### Requirement: Remote publication remains separately gated
Completing this OpenSpec apply phase SHALL NOT itself push the branch, merge remote `main`, move or create a tag, or publish a release without a subsequent explicit user confirmation.

#### Scenario: Local apply reaches completion
- **WHEN** implementation and local verification are complete
- **THEN** the work remains local and reports the publish boundary for user review
