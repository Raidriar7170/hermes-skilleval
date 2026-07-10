## Context

At the planning snapshot, `origin/main` is `1a219d755ce31b94fee9dfb6b7824d6b9236f821`, while the annotated `v0.3.0` tag object `f8656e336b35b703bc52acc4be9f5e55237cf7e1` peels to commit `7fd85579edc34d2207b6472d2aa000904cfb554d`. Their common ancestor is the former local-main commit `c0e7ef558eaea6171b24a9b771c68e70d96957a6`; current main has two unique commits and the release line has 93. A merge-tree rehearsal reports an approximately 563-file aggregate diff and exactly two conflict files: `README.md` and `tests/test_project_surface.py`.

This split explains the current truth mismatch: main carries post-publish README wording, but the package and release implementation live on the tagged branch. The change must repair topology without rewriting the already-published tag or disguising the size of the bridge.

Separately, embedding-router training validates both configuration and model-manifest labels against the fixed `A100_USER_ROOT = /mnt/data/minghongsun`. `scripts/train_embedding_router.py` duplicates that containment logic. This protects the shared A100 filesystem but prevents an equivalent local or alternate-root run. Historical Phase 14/A100 artifacts are evidence records and are not migration targets.

## Goals / Non-Goals

**Goals:**

- Make the published `v0.3.0` commit and the current remote-main base genuine ancestors of the repaired branch.
- Preserve the annotated tag object and its peeled target exactly.
- Resolve only the rehearsed conflicts with an explicit, reviewable policy and make all public/package version surfaces agree on `0.3.0`.
- Replace duplicated fixed-root validation in the training path with one generic containment primitive while retaining the A100-specific wrapper.
- Let callers select a training output root, safely resolve relative or absolute output directories within it, and record the canonical root in generated provenance.
- Keep the work bounded to lineage repair, training-path portability, tests, current documentation, and review evidence.

**Non-Goals:**

- Retagging, rebasing, squashing, force-pushing, cherry-picking the 93 commits, or using an `ours` strategy to fabricate ancestry.
- Publishing a GitHub release, merging to remote `main`, deploying, training a model, running GPU benchmarks, or claiming model-quality gains.
- Rewriting committed Phase 14/A100 evidence, migrating every A100-specific command in the repository, or archiving unrelated completed OpenSpec changes.
- Expanding the router algorithm, training data, losses, evaluation policy, or release acceptance policy.

## Decisions

### 1. Repair lineage with a real bridge merge

The apply phase will refresh remote refs, re-check the topology, and merge the peeled tag commit `7fd85579edc34d2207b6472d2aa000904cfb554d` into a branch based on the refreshed `origin/main` using `--no-ff`. The resulting merge commit must have both histories as parents and must contain the release tree changes; the annotated tag itself is never moved.

Before merging, the apply phase will assert the expected tag object/target and rehearse the merge again. If the captured `origin/main` SHA, annotated tag object, peeled tag target, or exact two-file conflict set differs from this approved snapshot, implementation stops for re-review rather than guessing.

Alternatives rejected:

- **Cherry-pick or squash the release line:** copies content but does not make the published release an ancestor.
- **Rebase or retag:** rewrites published identity and invalidates existing references.
- **`ours`/empty bridge:** creates graph ancestry while silently discarding the release content.
- **Merge main into the release branch first:** adds an unnecessary intermediate topology and makes the default-branch repair harder to review.

### 2. Apply a narrow conflict policy

Only the rehearsed conflicts are eligible for manual resolution:

- `README.md`: retain the current-main post-publish framing and release links while preserving the release line's honest limitations and review-state language.
- `tests/test_project_surface.py`: retain assertions for the current public surface and add the release-line assertions needed to protect evidence links and version consistency.

All non-conflicting release changes flow from Git's normal merge. Any additional conflict is a hard stop. After resolution, package metadata, `hermes_skilleval.__version__`, CLI output, README/release badge, and release checks must consistently report `0.3.0`. `REVIEW_REQUIRED` and `KEEP_BASELINE` remain literal truth surfaces where they already describe evidence state.

### 3. Treat inherited whitespace as a closed evidence exception

The complete first-parent command `git diff --check 1c44972f2777eafbc1fe5b64b2e8e02a72917e79 887672bba07235fd1b1d4c030866f4e74248c1c8` reports inherited whitespace in exactly five raw evidence files:

- `artifacts/v0.3/skillsbench-pilot/v0.3-stage2-input-package-candidate-20260701T010000Z/apt-source-diagnostics-20260702T052036Z/logs/docker-context-ls.log`
- `artifacts/v0.3/skillsbench-pilot/v0.3-stage2-input-package-candidate-20260701T010000Z/apt-source-diagnostics-20260702T052036Z/logs/docker-image-ls.log`
- `artifacts/v0.3/skillsbench-pilot/v0.3-stage2-input-package-candidate-20260701T010000Z/apt-source-diagnostics-20260702T052036Z/logs/docker-info.log`
- `artifacts/v0.3/skillsbench-pilot/v0.3-stage2-input-package-candidate-20260701T010000Z/apt-source-diagnostics-20260702T052036Z/logs/docker-run-python312-slim-network-shape.log`
- `artifacts/v0.3/skillsbench-pilot/v0.3-stage2-real-codex-12-run-execution-20260707T032920Z/command-output/codex-exec-help.stdout.txt`

Each blob is byte-identical between the `v0.3.0` second parent and the bridge. Normalizing the files would falsify historical command output, so the bridge gate records the full exit-2 output as an expected inherited failure rather than calling it a pass. The raw output is retained losslessly as base64 plus SHA-256 in `docs/release-lineage/v0.3.0-bridge-whitespace-exception.json`, avoiding reproduction of the offending whitespace in the evidence file itself.

The exception is closed: only the five literal paths and only `trailing whitespace` / `new blank line at EOF` diagnostics are accepted. The first-parent check excluding those literal paths, the complete second-parent check, and the first-parent check on both manual conflict files must exit zero. Tree modes and blob IDs must match at second parent, bridge, and final `HEAD`; the bridge must remain an ancestor; tag identities remain immutable. All post-bridge work remains subject to an exception-free `git diff --check 887672bba07235fd1b1d4c030866f4e74248c1c8 HEAD`. No glob, directory-wide waiver, `.gitattributes` suppression, normalization, or future modification is allowed.

### 4. Keep portability as a second bounded implementation step

After the topology bridge is validated, path portability is implemented as a separate logical commit in the same branch/PR. This preserves reviewability: reviewers can inspect the unavoidable historical bridge independently from the small runtime change.

The path step will add a generic helper in `remote_paths.py` that canonicalizes a selected root and candidate with `Path.resolve(strict=False)`, joins relative candidates under the root, and requires the resolved candidate to be relative to the resolved root. The existing `validate_a100_user_path()` remains a compatibility wrapper around the generic helper with `A100_USER_ROOT`.

Alternatives rejected:

- **Delete containment checks:** improves convenience by removing the safety boundary.
- **Prefix-string validation:** is vulnerable to sibling-prefix and traversal mistakes.
- **Duplicate a second validator in the script:** preserves drift between config, trainer, and manifest behavior.
- **Make all repository paths portable in this phase:** widens the change beyond the confirmed training-output scope.

### 5. Select one root and propagate it end to end

`scripts/train_embedding_router.py` will expose `--output-root`. Root selection is: explicit CLI value, otherwise a config `output_root` value when present, otherwise `/mnt/data/minghongsun`. This retains old configs and A100 commands while allowing generated portable configs and one-off CLI overrides. A relative `output_root` is resolved against the trainer process's current working directory, regardless of the config file's directory; documentation and tests make that rule explicit.

`build_train_config()` will accept an optional `output_root`, default it to the A100 root, validate `output_dir` against it, and record both canonical values. A relative `output_dir` is interpreted beneath the selected root; an absolute directory is accepted only when contained by that root. The trainer passes the same selected root to model-manifest validation and records canonical `output_root` and `output_dir` values in `train-run-summary.json`.

An invalid path fails before output-directory creation, model save, or manifest/summary writes. Existing symlink components are resolved, so a path that appears to be beneath the root but traverses a symlink outside it is rejected. This is a filesystem containment check, not a defense against a concurrent symlink-swap race by an adversarial local user.

### 6. Preserve historical evidence and update only live guidance

The portability commit uses the completed bridge commit as its comparison baseline and preserves these tracked historical artifacts byte-for-byte:

- `docs/demo/phase14-finetuned-embedding-router/**`
- `docs/demo/phase15-held-out-generalization/**`
- `docs/demo/phase16-blind-validation/regression-summary.json`
- `docs/demo/phase7a-cross-encoder/embedding-cache.json`

Their bridge-baseline blob IDs are captured before portability edits and compared with final `HEAD`. Current guidance in `docs/phase14.md`, `docs/usage.md`, and the source template used to render future model cards may describe the A100 default and an explicit local-root invocation; the already-committed demo model card remains protected. No historical run is relabeled as portable or rerun.

## Risks / Trade-offs

- **[Large bridge obscures small edits]** → Keep the bridge and portability work as separate logical commits; publish the exact parent SHAs, conflict list, and ancestry checks in the Human Brief/review packet.
- **[Inherited raw logs fail first-parent whitespace checking]** → Preserve their exact blobs, retain the full expected failure as structured evidence, enforce a five-path/two-diagnostic allowlist, and require all exception-free checks plus bridge-to-HEAD immutability to pass.
- **[Remote main changes before apply]** → Fetch and repeat identity and merge-tree checks; any `origin/main` SHA change or exact conflict-set change stops apply for renewed review.
- **[Conflict resolution overstates release readiness]** → Preserve `REVIEW_REQUIRED`, `KEEP_BASELINE`, and existing limitation language; run truth-surface scans and release checks.
- **[A caller supplies inconsistent config and CLI roots]** → Treat explicit CLI `--output-root` as authoritative and revalidate the configured `output_dir`; reject rather than silently relocate an absolute path.
- **[Symlink or traversal escapes the selected root]** → Resolve root and candidate before any writes and add focused absolute, `..`, sibling-prefix, and symlink-escape tests.
- **[Changing provenance fields breaks old consumers]** → Add `output_root` without removing existing keys, preserve old-config defaults, and run the full suite.
- **[Historical evidence is accidentally normalized]** → Maintain an explicit protected-path scan and review the second commit's name-only diff.

## Migration Plan

1. Refresh `origin/main` and tag refs; record the expected SHAs, tag object, peeled target, merge base, unique-commit counts, aggregate diff, and conflict set. Stop if any captured main/tag identity or the exact conflict set differs from the approved snapshot.
2. Create the real non-fast-forward bridge merge and resolve only the two approved files.
3. Validate ancestry, merge parents/content, immutable tag identity, version consistency, release checks, full tests, OpenSpec, and the closed inherited-whitespace exception with hash-backed evidence.
4. Add failing portability tests, implement the generic validator and end-to-end root propagation, then update current documentation.
5. Re-run focused and full validation, protected-evidence scans, and a read-only Reviewer pass; generate the Chinese Human Brief from the resulting evidence.
6. Stop for user confirmation before any push, PR publication, remote merge, tag, or release action.

Rollback is local branch/worktree deletion before publication. If a published PR is rejected, close it without merging; no remote tag or default-branch mutation is part of this apply phase.

## Open Questions

None. Any topology drift, new merge conflict, or need to modify historical evidence reopens design review instead of being resolved inside implementation.
