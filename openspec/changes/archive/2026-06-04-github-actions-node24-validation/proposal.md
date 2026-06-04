## Why

GitHub Actions is migrating JavaScript actions from Node 20 to Node 24, and the
latest remote Validate run already surfaced a Node 20 deprecation annotation.
The repository should preflight the existing Validate workflow under Node 24
before GitHub changes the default runtime.

## What Changes

- Add an explicit `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` environment setting
  to the Validate workflow so repository actions are exercised against the
  upcoming JavaScript action runtime.
- Document the Node 24 preflight boundary in README and usage docs without
  claiming a Marketplace Action, PR comment bot, PR annotations, SaaS, runtime
  MCP router, SOTA status, production readiness, release approval, or automatic
  merge approval.
- Add focused tests that keep the workflow and public wording stable.
- Generate a Human Brief for this phase and include it in current surface
  checks.

## Capabilities

### New Capabilities
- `github-actions-node24-validation`: Validate workflow Node 24 JavaScript
  action runtime preflight and bounded documentation.

### Modified Capabilities
- None.

## Impact

- `.github/workflows/validate.yml`
- `README.md`
- `docs/usage.md`
- `docs/human-briefs/`
- `tests/test_project_surface.py`
- OpenSpec change artifacts
