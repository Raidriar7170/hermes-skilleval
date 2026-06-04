# github-actions-node24-validation Specification

## Purpose
Define Validate workflow Node 24 preflight behavior and conservative
documentation for GitHub Actions JavaScript runtime compatibility checks.

## Requirements
### Requirement: Preflight Validate workflow with Node 24 JavaScript actions
The system SHALL configure the repository Validate workflow to run GitHub
Actions JavaScript actions under the Node 24 preflight runtime.

#### Scenario: Workflow opts into Node 24 preflight
- **WHEN** a maintainer inspects `.github/workflows/validate.yml`
- **THEN** the workflow MUST set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` to `true`
  for the Validate run
- **AND** it MUST NOT set `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION`

#### Scenario: Existing validation checks remain in workflow
- **WHEN** the Node 24 preflight setting is added
- **THEN** the workflow MUST still run pytest, OpenSpec validation,
  release-check, diagnostic CI gate, diagnostic artifact drift, external skill
  library validation, PR-facing CI summary, artifact upload, and final summary
  decision enforcement

### Requirement: Document Node 24 preflight boundary
The system SHALL document the Node 24 Validate preflight as a CI compatibility
check with conservative public wording.

#### Scenario: Public docs explain local and remote validation
- **WHEN** a maintainer reads README or usage docs
- **THEN** the docs MUST explain that the Validate workflow preflights GitHub
  Actions JavaScript actions with Node 24
- **AND** the docs MUST provide a local simulation command or checklist for the
  existing validation gates

#### Scenario: Avoid overclaiming CI runtime migration
- **WHEN** docs, workflow examples, or reports describe the Node 24 preflight
- **THEN** they MUST NOT claim Marketplace Action release, GitHub API PR
  comments, PR annotations, SaaS, runtime MCP routing, benchmark SOTA,
  production readiness, automatic merge approval, release approval, or a
  permanent compatibility guarantee
