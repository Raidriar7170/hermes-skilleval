## Why

The published `v0.3.0` tag lives on a 93-commit release line that is not an ancestor of `main`, so the repository's default branch and published release do not share a truthful forward lineage. The embedding-router training entry point also fixes output validation to `/mnt/data/minghongsun`, which prevents the same workflow from being reproduced under an explicitly selected local or remote root.

## What Changes

- Rejoin the immutable `v0.3.0` release commit to the current `origin/main` lineage with a real non-fast-forward bridge merge, preserving both histories and the published tag object.
- Resolve only the known `README.md` and `tests/test_project_surface.py` merge conflicts, retaining current-main public wording together with the release line's evidence links and `REVIEW_REQUIRED` / `KEEP_BASELINE` truth surfaces.
- Add an explicit training output-root contract with `/mnt/data/minghongsun` as the backward-compatible default and support for caller-selected roots.
- Require output paths to remain contained within the selected root after normalization and symlink resolution, failing closed on traversal or absolute-path escape.
- Propagate the selected root through training configuration, model-manifest validation, and run-summary provenance.
- Preserve committed historical Phase 14/A100 evidence artifacts as historical records; update only current commands, documentation, tests, and runtime behavior.
- Exclude tag rewriting, force-push, history rewriting, release publication, model training, benchmark execution, and archival of unrelated OpenSpec changes.

## Capabilities

### New Capabilities

- `release-lineage-integrity`: Defines the ancestry, immutable-tag, conflict-resolution, and verification contract for reconnecting the published `v0.3.0` release line to `main`.
- `portable-training-output-root`: Defines explicit, contained, and provenance-recorded output-root behavior for embedding-router training while preserving the existing A100 default.

### Modified Capabilities

None.

## Impact

- Git topology: a future bridge merge will make both current `origin/main` and the peeled `v0.3.0` commit ancestors of the repaired branch. The reviewed topology introduces the release line's 93 unique commits and an approximately 563-file aggregate bridge diff, with two known conflict files.
- Runtime and CLI: `scripts/train_embedding_router.py`, `src/hermes_skilleval/remote_paths.py`, training configuration, model-manifest validation, and run-summary generation.
- Verification: focused containment/provenance tests, the full Python test suite, release checks, strict OpenSpec validation, Git ancestry/tag assertions, boundary scans, and `git diff --check`.
- Documentation: current training commands and portability guidance; historical evidence remains unchanged.
- Dependencies and external systems: no new runtime dependency, GPU job, A100 access, tag mutation, GitHub release, or deployment is required by this change.
