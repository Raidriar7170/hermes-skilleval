## 1. Demo Source and Regeneration Contract

- [x] 1.1 Create a small diagnostic demo skill source under `docs/demo/diagnostic-onboarding/`.
- [x] 1.2 Include nearby skills that produce meaningful lint findings, conflict risk clusters, and route risk flags.
- [x] 1.3 Add a demo README with exact scan, lint, inspect, route, and diagnostic-dashboard regeneration commands.

## 2. Demo Artifact Generation

- [x] 2.1 Generate `scan.json` from the demo source.
- [x] 2.2 Generate `lint.json` from the scan artifact.
- [x] 2.3 Generate `inspect.json` from the scan artifact.
- [x] 2.4 Generate at least one `route-*.json` artifact with route evidence and risk flags.
- [x] 2.5 Generate a self-contained `dashboard.html` diagnostic dashboard.

## 3. Documentation Links

- [x] 3.1 Add a concise README link to the diagnostic demo pack without expanding the experiment timeline.
- [x] 3.2 Add detailed demo regeneration notes to `docs/usage.md`.
- [x] 3.3 Keep wording bounded: demo evidence only, no runtime router, SaaS, SOTA benchmark, or CI merge-blocking claim.

## 4. Artifact Integrity Tests

- [x] 4.1 Add tests for diagnostic demo artifact presence, artifact types, and schema versions.
- [x] 4.2 Add tests for expected route evidence, risk flags, and conflict risk wording.
- [x] 4.3 Add tests that the diagnostic dashboard is self-contained and avoids out-of-scope claims.

## 5. Verification and Brief

- [x] 5.1 Run focused diagnostic demo tests.
- [x] 5.2 Run the full pytest suite.
- [x] 5.3 Run the existing release-check command.
- [x] 5.4 Run OpenSpec strict validation and `git diff --check`.
- [x] 5.5 Generate a concise Chinese Human Brief HTML for this phase.
