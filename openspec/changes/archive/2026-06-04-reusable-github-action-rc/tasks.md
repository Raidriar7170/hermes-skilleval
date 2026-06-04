## 1. Tests

- [x] 1.1 Add RED tests for action metadata, example fixtures/workflow, gate
  outputs, bounded public wording, and fresh-clone smoke.

## 2. Gate and Action

- [x] 2.1 Add a deterministic `skilleval github-action-gate` command for
  external benchmark threshold gating and CI summary artifacts.
- [x] 2.2 Add root `action.yml` composite action with required inputs and
  optional artifact upload.
- [x] 2.3 Add `examples/github-action/` with example skills, benchmark tasks,
  README, and workflow.

## 3. Documentation

- [x] 3.1 Add README and usage documentation for external onboarding and
  fresh-clone smoke without release, Marketplace, PR bot, SaaS, MCP router, or
  production-readiness claims.
- [x] 3.2 Generate the phase Human Brief and loop report.

## 4. Verification and Closeout

- [x] 4.1 Run focused tests, fresh-clone smoke, full pytest, OpenSpec
  validation, release-check, drift checks, CI summary simulation, and git diff
  hygiene.
- [x] 4.2 Archive the OpenSpec change after validation and rerun final
  freshness checks before auto integration.
