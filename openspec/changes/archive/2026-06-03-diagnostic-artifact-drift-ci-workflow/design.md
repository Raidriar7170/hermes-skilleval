## Context

The repository already has committed diagnostic onboarding artifacts, a
diagnostic CI gate, a local PR review packet generator, and
`skilleval diagnostic-artifact-drift-check`. The existing
`.github/workflows/validate.yml` runs pytest, the Phase 18 release-check, and
the diagnostic CI gate, but it does not regenerate the diagnostic demo and run
the semantic drift check in CI.

## Goals / Non-Goals

**Goals:**

- Run the documented diagnostic demo regeneration flow in GitHub Actions.
- Compare regenerated artifacts against committed artifacts with the existing
  drift check.
- Keep generated CI-only reports in `$RUNNER_TEMP`.
- Preserve the existing release-check and diagnostic CI gate steps.

**Non-Goals:**

- Publishing a Marketplace Action or reusable external action.
- Calling the GitHub API, posting PR comments, or creating annotations.
- Changing diagnostic artifact schemas or drift normalization rules.
- Treating drift results as release approval or runtime-router evidence.

## Decisions

- **Use the existing validate workflow.** The repo already exposes a single
  public validation badge through `.github/workflows/validate.yml`. Adding a
  step there keeps CI evidence discoverable without creating another workflow
  surface.
- **Regenerate into `$RUNNER_TEMP`.** The step should recreate the diagnostic
  onboarding demo artifacts outside the repository, then compare them to the
  committed demo directory. This avoids generated files changing the checkout
  while still exercising the regeneration contract.
- **Test workflow text as project surface.** Existing `tests/test_project_surface.py`
  already verifies the diagnostic CI gate workflow step. Extending it gives a
  fast guard that CI keeps running the drift check with temporary outputs.

## Risks / Trade-offs

- [Risk] The workflow command can drift from docs. -> Mitigation: keep command
  shape aligned with the documented regeneration flow and add surface tests for
  the critical command fragments.
- [Risk] Running full diagnostic regeneration in CI increases runtime. ->
  Mitigation: the demo skill library is tiny and uses offline deterministic
  commands only.
- [Risk] Readers may confuse CI drift detection with PR automation. ->
  Mitigation: docs and reports continue to say this is semantic artifact drift
  detection, not GitHub API integration, annotations, Marketplace Action, SaaS,
  runtime routing, or release approval.
