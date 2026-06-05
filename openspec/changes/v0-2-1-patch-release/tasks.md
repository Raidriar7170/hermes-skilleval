## 1. Release Surface Updates

- [x] 1.1 Update package metadata and package `__version__` to `0.2.1`.
- [x] 1.2 Update current README, usage, example workflow, demo-repo plan, and tests from `Raidriar7170/hermes-skilleval@v0.2.0` to `Raidriar7170/hermes-skilleval@v0.2.1`.
- [x] 1.3 Promote `docs/release-notes/v0.2.1-candidate.md` into bounded `docs/release-notes/v0.2.1.md` release notes.
- [ ] 1.4 Update evidence map, release handoff, and Human Brief links for `v0.2.1` release notes and post-release evidence.

## 2. Tests and Validation

- [x] 2.1 Update project-surface and reusable-action tests for `0.2.1`, `@v0.2.1`, and `v0.2.1` release evidence.
- [x] 2.2 Run `python -m pytest -q`.
- [x] 2.3 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 2.4 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check`.
- [x] 2.5 Run `git diff --check`.
- [x] 2.6 Run existing local smoke, drift-check, and CI summary simulations.

## 3. Release Publication

- [ ] 3.1 Create a release commit after validation passes.
- [ ] 3.2 Push the release commit to `main` or an approved release branch according to current git state.
- [ ] 3.3 Create and push tag `v0.2.1`.
- [ ] 3.4 Create the GitHub Release for `v0.2.1` from `docs/release-notes/v0.2.1.md`.
- [ ] 3.5 Verify the remote tag and GitHub Release exist.

## 4. Post-release Evidence and Closeout

- [ ] 4.1 Add `docs/demo/v0.2.1-post-release/post-release.md` and JSON with verified publication facts.
- [ ] 4.2 Rerun focused tests and release surface scans after post-release evidence is written.
- [ ] 4.3 Rerun full validation after final evidence updates.
- [ ] 4.4 Report changed files, validation results, release URL, tag status, and any remaining limitations.
