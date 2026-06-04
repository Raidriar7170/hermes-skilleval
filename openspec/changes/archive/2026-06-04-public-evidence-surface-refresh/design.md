## Context

The project is already positioned as an interview-ready, developer-facing
routing reliability toolkit. The latest completed phase added a reusable GitHub
Action RC and synced its OpenSpec capability, but the cross-repo reviewer
navigation still focuses on earlier diagnostic and CI surfaces.

The change is documentation and contract hygiene: it updates public surfaces
that reviewers read first, and it keeps main OpenSpec specs readable after
archive sync. It does not introduce new runtime behavior.

## Goals / Non-Goals

**Goals:**

- Make the reusable action RC discoverable from `docs/evidence-map.md`.
- Keep public test-count wording aligned with the current 392-test suite.
- Replace synced `Purpose TBD` placeholders with bounded purpose text.
- Add project-surface tests that fail on the current stale or missing surfaces.

**Non-Goals:**

- No Marketplace Action publication, release tag, PR comments, PR annotations,
  SaaS, runtime MCP router, or release approval.
- No change to benchmark metrics, router behavior, or GitHub Actions gate logic.
- No broad rewrite of README or interview positioning.

## Decisions

- Use the existing `docs-evidence-map` capability rather than adding a new
  product capability. The change refreshes reviewer navigation and public
  surface consistency, not runtime behavior.
- Keep tests in `tests/test_project_surface.py` because the current regressions
  are public-surface contracts: stale test counts, missing evidence-map links,
  and OpenSpec source-of-truth readability.
- Update main synced specs only for purpose text. Archived change artifacts
  remain historical records; main specs are the long-lived source of truth.

## Risks / Trade-offs

- [Risk] Evidence-map additions could read like release approval. -> Mitigation:
  every new row states the artifact's limit and preserves existing boundary
  wording.
- [Risk] Purpose text could accidentally broaden a capability. -> Mitigation:
  keep each purpose tied to existing requirements and avoid new product claims.
- [Risk] Public-count tests can become brittle after future test additions. ->
  Mitigation: this phase records the current count because the public docs
  already claim exact counts; a future phase should update the count and tests
  together.
