## MODIFIED Requirements

### Requirement: Provide bounded evidence map
The system SHALL provide a reviewer-facing documentation evidence map that
groups committed SkillEval evidence by reviewer task without replacing the
README developer-tool onboarding path.

#### Scenario: Inspect evidence map categories
- **WHEN** a reviewer opens the evidence map
- **THEN** it MUST include categories for project positioning, release-gate
  evidence, diagnostic onboarding, external-style validation, PR-facing CI
  summary, reusable GitHub Action evidence, local external consumer smoke pack,
  hosted consumer action smoke evidence, post-release `v0.2.0` evidence,
  OpenSpec specs, and Human Briefs
- **AND** it MUST distinguish historical pre-publish review artifacts from
  current post-release status

### Requirement: Keep public evidence surfaces current
The project SHALL keep reviewer-facing current public surfaces aligned with the
published `v0.2.0` state and current validation count, while preserving
historical validation counts and pre-release artifacts as original phase
evidence when they are clearly labeled.

#### Scenario: Evidence map includes reusable action evidence
- **WHEN** the reusable GitHub Action is present in the repository
- **THEN** the evidence map MUST link to the action metadata, example fixture,
  local external consumer smoke pack, hosted consumer action smoke pack,
  `v0.2.0` release decision pack, `v0.2.0` post-release evidence, synced
  OpenSpec specs, and phase Human Briefs
- **AND** the evidence map MUST describe current Action usage as a published
  reusable repository Action and historical smoke artifacts as evidence rather
  than Marketplace publication, release approval, PR automation, SaaS, runtime
  MCP routing, production readiness, or automatic merge approval

#### Scenario: Current public docs use current validation count
- **WHEN** current public reviewer docs mention the exact pytest suite size
- **THEN** they MUST use the current validated public count and MUST NOT retain
  older exact-count wording from prior phases

#### Scenario: Historical Human Briefs preserve count provenance
- **WHEN** historical autonomous-loop Human Briefs retain old exact pytest
  counts from their original phase
- **THEN** those briefs MUST mark the count as an original run,
  implementation baseline, or historical count rather than the latest public
  validation count

#### Scenario: Synced OpenSpec specs have explicit purpose text
- **WHEN** a reviewer opens a synced spec under `openspec/specs/`
- **THEN** the spec MUST include a capability-specific Purpose section and MUST
  NOT contain archive-generated `Purpose TBD` placeholder text

### Requirement: Surface v0.2.0 release notes and final approval review
The evidence map SHALL link the `v0.2.0` release notes, historical final
approval checklist, and post-release evidence without treating pre-publish
review artifacts as the current release state.

#### Scenario: Evidence map includes final approval and post-release artifacts
- **WHEN** the `v0.2.0` final approval checklist and post-release evidence exist
- **THEN** the evidence map MUST link the release notes, final approval
  Markdown checklist, final approval JSON checklist, final approval input
  manifest, post-release Markdown, post-release JSON, synced OpenSpec spec, and
  phase Human Brief
- **AND** the evidence map MUST describe final approval artifacts as
  historical pre-publish review artifacts and post-release artifacts as the
  current publication record
- **AND** it MUST NOT claim Marketplace publication, PR comment automation,
  PR annotations, SaaS, runtime MCP routing, SOTA benchmark status, production
  readiness, automatic merge approval, or `finetuned-embedding`
  default-router approval
