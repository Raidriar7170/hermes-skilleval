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

### Requirement: Remote publication remains separately gated
Completing this OpenSpec apply phase SHALL NOT itself push the branch, merge remote `main`, move or create a tag, or publish a release without a subsequent explicit user confirmation.

#### Scenario: Local apply reaches completion
- **WHEN** implementation and local verification are complete
- **THEN** the work remains local and reports the publish boundary for user review
