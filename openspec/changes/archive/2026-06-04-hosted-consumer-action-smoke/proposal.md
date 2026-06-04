## Why

The Reusable GitHub Action RC now has local external-consumer smoke evidence,
but it still does not prove that a GitHub-hosted consumer workflow can call
`Raidriar7170/hermes-skilleval@main`, run the composite action on a hosted
runner, and produce downloadable gate artifacts. This phase adds a bounded
hosted consumer smoke record without changing release posture.

## What Changes

- Run a minimal GitHub-hosted consumer workflow in a dedicated consumer
  repository that calls `Raidriar7170/hermes-skilleval@main`.
- Download and commit sanitized hosted-run evidence: run metadata, workflow
  source, gate report JSON/Markdown, CI summary JSON/Markdown, results JSONL,
  and a short reproduction/provenance README.
- Add deterministic project-surface tests that verify hosted evidence links,
  run metadata, artifact decisions, and conservative claim boundaries.
- Link the hosted smoke from README, usage docs, evidence map, and Human Briefs.
- Do not create a tag, release, Marketplace Action listing, PR comment bot, PR
  annotations, SaaS surface, runtime MCP router, or release approval claim.

## Capabilities

### New Capabilities
- `hosted-consumer-action-smoke`: hosted GitHub Actions consumer smoke evidence
  for the reusable action RC.

### Modified Capabilities
- `docs-evidence-map`: surface hosted consumer smoke evidence without changing
  release, product, or Marketplace posture.
- `reusable-github-action-rc`: include hosted consumer smoke evidence in the RC
  proof chain while preserving RC boundaries.

## Impact

- Affected docs/evidence: new hosted smoke evidence under
  `docs/demo/hosted-consumer-action-smoke/`, README/usage/evidence map links,
  and a phase Human Brief.
- Affected tests: reusable action RC and project-surface tests.
- Affected OpenSpec specs: new hosted smoke spec and updated evidence-map /
  reusable-action specs after archive sync.
- Remote action: a dedicated GitHub-hosted consumer workflow run, with sanitized
  evidence committed back to this repository.
