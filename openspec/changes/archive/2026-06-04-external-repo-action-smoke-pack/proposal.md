## Why

The reusable GitHub Action RC already has a local fresh-clone smoke test, but
reviewers still lack a durable consumer-facing evidence pack that shows what an
external repository would run and what artifacts the gate produces. This phase
turns that smoke path into committed, public-safe evidence without creating a
remote repository, tag, release, or Marketplace publication.

## What Changes

- Add a local external-consumer smoke pack that records a fresh-clone style
  `skilleval github-action-gate` run against the existing example fixture.
- Add deterministic tests that verify the smoke pack artifacts, commands,
  metrics, and conservative claim boundaries.
- Link the smoke pack from reviewer-facing docs and the evidence map.
- Add a concise Chinese Human Brief for this phase.
- Do not create a remote GitHub repository, require secrets, publish a release,
  create a tag, or claim Marketplace Action status.

## Capabilities

### New Capabilities
- `external-repo-action-smoke-pack`: durable local consumer smoke evidence for
  the reusable GitHub Action RC.

### Modified Capabilities
- `docs-evidence-map`: surface the external consumer smoke pack from the
  reviewer-facing evidence map without changing release posture.

## Impact

- Affected docs/evidence: a new committed smoke pack under
  `docs/demo/external-repo-action-smoke-pack/`, README/usage/evidence-map links,
  and a phase Human Brief.
- Affected tests: reusable action RC and project-surface tests.
- Affected OpenSpec specs: new `external-repo-action-smoke-pack` spec and
  updated `docs-evidence-map` spec after archive sync.
- No runtime GitHub API, remote repository, secrets, tag, release, Marketplace,
  SaaS, or MCP router changes.
