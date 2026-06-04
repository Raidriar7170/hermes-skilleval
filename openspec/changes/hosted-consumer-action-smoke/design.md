## Context

The previous `external-repo-action-smoke-pack` phase proved consumer-relative
paths locally by executing the composite action shell step from a temporary
consumer repository. The remaining gap is hosted-run behavior: GitHub Actions
checkout, hosted runner environment, action resolution through
`uses: Raidriar7170/hermes-skilleval@main`, artifact upload, and run-level
metadata.

## Goals / Non-Goals

**Goals:**
- Run a minimal hosted GitHub Actions consumer workflow against the public
  Reusable GitHub Action RC.
- Keep the consumer repository tiny: `skills/`, `benchmark/`, one workflow, and
  no secrets.
- Commit sanitized evidence that a reviewer can inspect without needing access
  to the consumer repository UI.
- Preserve conservative wording: hosted smoke evidence, not release approval.

**Non-Goals:**
- No `v0.2.0` tag, GitHub Release, Marketplace listing, release note, or
  release approval.
- No PR comments, PR annotations, GitHub API bot, SaaS dashboard, or runtime MCP
  router.
- No private logs, tokens, secrets, or credentials in committed artifacts.
- No claim that one hosted smoke proves production readiness.

## Decisions

1. Use a dedicated consumer repo named
   `Raidriar7170/hermes-skilleval-action-consumer-smoke` if no existing repo is
   available. This keeps hosted workflow state separate from the producer repo.
2. Keep the workflow public-safe and deterministic: `workflow_dispatch`,
   `permissions: contents: read`, checkout, Python 3.11 setup, call
   `Raidriar7170/hermes-skilleval@main`, use two public example skills and two
   labeled tasks, set strict thresholds, and upload artifacts.
3. Download only generated gate artifacts, input manifest, and structured run
   metadata. Do not
   commit raw logs, tokens, environment dumps, or credentials.
4. Record run URL, repository URL, head SHA, workflow name, conclusion, and
   artifact names in a local JSON evidence file.
5. Add tests before evidence files so the phase fails until hosted run evidence
   and bounded docs exist.

## Risks / Trade-offs

- A public hosted consumer repo is a visible account artifact. Mitigation:
  name it clearly as a smoke repo, keep contents minimal, and avoid release
  wording.
- Hosted run URLs can become inaccessible if repo permissions change.
  Mitigation: commit sanitized run metadata and downloaded artifacts locally.
- GitHub Actions warnings may mention Node runtime deprecations from upstream
  actions. Mitigation: record conclusions and keep warnings out of claims unless
  they block the run.
