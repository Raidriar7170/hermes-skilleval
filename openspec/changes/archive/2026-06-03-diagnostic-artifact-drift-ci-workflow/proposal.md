## Why

The diagnostic artifact drift check is now available locally, but the GitHub
Actions validation workflow still only runs pytest, release-check, and the
diagnostic CI gate. Adding the drift check to CI turns the committed demo
artifact regeneration contract into fresh workflow evidence without expanding
into PR annotations or hosted automation.

## What Changes

- Add a lightweight GitHub Actions validation step that regenerates the
  diagnostic onboarding demo into a temporary directory and runs
  `skilleval diagnostic-artifact-drift-check` against committed artifacts.
- Keep drift reports outside the repository working tree so CI does not create
  noisy generated-file diffs.
- Add tests and documentation that the workflow runs the drift check while
  preserving the existing bounded claims.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `diagnostic-artifact-drift-check`: add GitHub Actions workflow usage for the
  existing local semantic drift check.

## Impact

- `.github/workflows/validate.yml`
- `tests/test_project_surface.py`
- README / usage documentation for the diagnostic onboarding CI path
- `openspec/specs/diagnostic-artifact-drift-check/spec.md`
