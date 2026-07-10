## 1. Refresh and Freeze the Approved Boundary

- [x] 1.1 Run a read-only Explorer pass over current refs, merge topology, conflict shape, path call sites, protected evidence, and validation entry points; re-plan if findings differ from the approved design.
- [x] 1.2 In the isolated Worker worktree, record `pwd`, `git status`, `git branch`, and a clean baseline; fetch `origin/main` and tags without changing the canonical worktree.
- [x] 1.3 Capture and verify the `origin/main` SHA, annotated `v0.3.0` tag object, peeled target, merge base, unique-commit counts, aggregate diff shape, and merge-tree conflict list.
- [x] 1.4 Stop for renewed review if the captured `origin/main` SHA, annotated tag object, peeled target, or exact conflict set differs from the approved snapshot; the only approved conflicts are `README.md` and `tests/test_project_surface.py`.

## 2. Create and Verify the Lineage Bridge

- [x] 2.1 Ensure the approved OpenSpec artifacts are preserved and the Worker index is clean, then create a real `--no-ff` merge from the peeled `v0.3.0` commit into the branch based on refreshed `origin/main`.
- [x] 2.2 Resolve `README.md` by retaining current-main post-publish framing and links while preserving release limitations and applicable `REVIEW_REQUIRED` / `KEEP_BASELINE` language.
- [x] 2.3 Resolve `tests/test_project_surface.py` by retaining current public-surface assertions and the release-line assertions for evidence links and version consistency.
- [x] 2.4 Verify package metadata, `hermes_skilleval.__version__`, CLI/README version surfaces, and release checks consistently report `0.3.0`.
- [x] 2.5 Verify the bridge has exactly two parents (bridge-pre Worker HEAD first and `7fd85579edc34d2207b6472d2aa000904cfb554d` second), carries release content, makes both captured main and `v0.3.0^{}` ancestors, and leaves the annotated tag object and peeled target unchanged.
- [x] 2.6 Run the full Python suite, strict OpenSpec validation, and the release reproducibility gate with a clean Phase 17/18 evidence diff.
- [x] 2.7 Run the complete first-parent `git diff --check` and retain its raw exit-2 output losslessly in `docs/release-lineage/v0.3.0-bridge-whitespace-exception.json`; prove every diagnostic is limited to the five literal paths and two inherited diagnostic classes specified in the lineage spec, then require the exact-five-exclusion first-parent check, complete second-parent check, and two-conflict-file check to exit zero. Record and compare modes/blob IDs at second parent and bridge; no glob, broad exclusion, suppression, or normalization is allowed.

## 3. Add Portable Root Behavior with TDD

- [x] 3.1 Add focused failing tests for generic containment, the A100 compatibility wrapper, local roots, relative output directories, contained absolute paths, sibling-prefix escape, `..` escape, and existing-symlink escape; run them and record the expected red state.
- [x] 3.2 Implement the minimal generic root-containment helper in `src/hermes_skilleval/remote_paths.py` and refactor `validate_a100_user_path()` into a backward-compatible wrapper.
- [x] 3.3 Add focused failing tests for `build_train_config()` root recording/defaults, relative-root resolution from process CWD, and trainer selection precedence (`--output-root` over config over A100 default); run them and record the expected red state.
- [x] 3.4 Extend `build_train_config()` to accept, validate, canonicalize, and record `output_root` together with its contained `output_dir` while preserving legacy-call defaults.
- [x] 3.5 Add focused failing tests proving the selected root reaches model-manifest validation and `train-run-summary.json`, and proving a mismatched root fails before output writes.
- [x] 3.6 Add `--output-root` selection to `scripts/train_embedding_router.py`, remove its duplicate fixed-root validator, pass the selected root to model-manifest validation, and record canonical root/output provenance.
- [x] 3.7 Extend model-manifest functions with a backward-compatible selected-root parameter and run all focused portability tests to green.

## 4. Update Live Guidance Without Rewriting Evidence

- [x] 4.1 Update `docs/phase14.md`, `docs/usage.md`, and the source template for future model cards to document the `/mnt/data/minghongsun` default, config behavior, explicit CLI override, and one local-root example; do not edit the committed demo model card.
- [x] 4.2 Capture protected blob IDs at the bridge commit and compare them with final `HEAD` for `docs/demo/phase14-finetuned-embedding-router/**`, `docs/demo/phase15-held-out-generalization/**`, `docs/demo/phase16-blind-validation/regression-summary.json`, and `docs/demo/phase7a-cross-encoder/embedding-cache.json`; also prove the five closed-exception entries retain identical mode/blob IDs and a clean path-limited bridge-to-HEAD diff, then inspect `git diff --name-only <bridge> HEAD`.
- [x] 4.3 Scan active docs and code for stale claims that training output is unconditionally fixed to `/mnt/data/minghongsun`, without changing unrelated A100-specific workflows.

## 5. Validate and Review the Complete Change

- [x] 5.1 Run focused path/config/trainer/manifest tests and the full `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q` suite.
- [x] 5.2 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`, the release reproducibility gate plus its explicit Phase 17/18 evidence diff check, version/truth-surface scans, ancestry/tag assertions, the closed inherited-whitespace exception checks/evidence, and exception-free `git diff --check <bridge> HEAD`.
- [x] 5.3 Generate `docs/human-briefs/2026-07-10-close-v0-3-release-lineage-and-portable-root.html` from the final diffs and validation evidence, including the large-bridge boundary and honest non-claims.
- [ ] 5.4 Start a read-only Reviewer over the complete diff including the Human Brief; require `Must Fix`, `Should Fix`, `Nice to Have`, `Re-plan Needed`, and `Final Verdict` sections.
- [ ] 5.5 If `Re-plan Needed = No`, return only in-scope Must Fix items to the Worker and repeat focused/full verification plus Reviewer coverage of any resulting diff; if `Re-plan Needed = Yes`, stop and revise the plan before further edits.

## 6. Stop at the Publication Gate

- [ ] 6.1 Report changed files, bridge parent/tag identities, validation results, protected-evidence status, remaining risks, and Reviewer verdict for user inspection.
- [ ] 6.2 Stop for explicit user confirmation without pushing, opening or merging a PR, changing tags, publishing a release, deploying, training, benchmarking, or archiving unrelated OpenSpec changes.
