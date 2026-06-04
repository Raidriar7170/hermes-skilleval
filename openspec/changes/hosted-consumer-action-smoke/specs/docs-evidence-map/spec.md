## MODIFIED Requirements

### Requirement: Provide bounded evidence map
The system SHALL provide a reviewer-facing documentation evidence map that
groups committed SkillEval evidence by reviewer task.

#### Scenario: Inspect evidence map categories
- **WHEN** a reviewer opens the evidence map
- **THEN** it MUST include categories for project positioning, release-gate
  evidence, diagnostic onboarding, external-style validation, PR-facing CI
  summary, Reusable Action RC Evidence for the reusable GitHub Action RC,
  local external consumer smoke pack, hosted consumer action smoke evidence,
  OpenSpec specs, and Human Briefs

### Requirement: Keep public evidence surfaces current
The project SHALL keep reviewer-facing current public surfaces aligned with the
latest committed evidence phase and current validation count, while preserving
historical Human Briefs as contemporaneous phase records when they clearly mark
old exact counts as original run or baseline evidence.

#### Scenario: Evidence map includes reusable action RC evidence
- **WHEN** the reusable GitHub Action RC is present in the repository
- **THEN** the evidence map MUST link to the action metadata, example fixture,
  local external consumer smoke pack, hosted consumer action smoke pack,
  synced OpenSpec specs, and phase Human Briefs
- **AND** the evidence map MUST describe those artifacts as release-candidate
  evidence rather than Marketplace publication, release approval, PR
  automation, SaaS, runtime MCP routing, production readiness, or automatic
  merge approval
