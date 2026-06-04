# docs-evidence-map Specification

## Purpose
Define the bounded reviewer navigation map that groups committed SkillEval
evidence without replacing canonical artifacts or making release, product, or
benchmark-leadership claims.
## Requirements
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

### Requirement: Preserve source-of-truth boundaries
The evidence map SHALL act as a navigation layer and MUST NOT replace the
underlying evidence artifacts.

#### Scenario: Explain proof and limits
- **WHEN** an evidence map row describes an artifact
- **THEN** it MUST state what the artifact helps verify and avoid presenting
  the map itself as release approval, benchmark leadership, or product
  integration evidence

#### Scenario: Avoid overclaiming product capabilities
- **WHEN** README, usage docs, or the evidence map describe the map
- **THEN** they MUST NOT claim Marketplace Action release, GitHub API PR
  comments, PR annotations, SaaS, runtime MCP routing, SOTA benchmark status,
  production readiness, automatic merge approval, or release approval

### Requirement: Surface evidence map from public docs
The repository SHALL link the evidence map from public reviewer entry points.

#### Scenario: README links evidence map
- **WHEN** a reviewer follows the README recruiter or diagnostic review path
- **THEN** the README MUST provide a link to the evidence map

#### Scenario: Usage docs link evidence map
- **WHEN** a maintainer reads the CLI usage guide
- **THEN** `docs/usage.md` MUST provide a link to the evidence map as a local
  navigation aid

### Requirement: Test evidence map integrity
The test suite SHALL verify that the evidence map remains usable and bounded.

#### Scenario: Verify evidence map links
- **WHEN** project-surface tests run
- **THEN** they MUST verify that local relative links in the evidence map
  resolve to existing repository paths

#### Scenario: Verify evidence map wording
- **WHEN** project-surface tests scan the evidence map and linked public docs
- **THEN** they MUST fail if the map introduces disallowed product or
  benchmark-leadership claims

### Requirement: Keep public evidence surfaces current
The project SHALL keep reviewer-facing current public surfaces aligned with the
latest committed evidence phase and current validation count, while preserving
historical validation counts as original phase evidence when they are clearly
labeled.

#### Scenario: Evidence map includes reusable action RC evidence
- **WHEN** the reusable GitHub Action RC is present in the repository
- **THEN** the evidence map MUST link to the action metadata, example fixture,
  local external consumer smoke pack, hosted consumer action smoke pack,
  `v0.2.0` release decision pack, synced OpenSpec specs, and phase Human Briefs
- **AND** the evidence map MUST describe those artifacts as release-candidate
  and release-review evidence rather than Marketplace publication, release
  approval, PR automation, SaaS, runtime MCP routing, production readiness, or
  automatic merge approval

#### Scenario: Current public docs use current validation count
- **WHEN** current public reviewer docs mention the exact pytest suite size
- **THEN** they MUST use the current validated public count and MUST NOT retain
  older exact-count wording from prior phases

#### Scenario: Historical Human Briefs preserve count provenance
- **WHEN** historical autonomous-loop Human Briefs retain old exact pytest
  counts from their original phase
- **THEN** those briefs MUST mark the count as an original run, implementation
  baseline, or historical count rather than the latest public validation count

#### Scenario: Synced OpenSpec specs have explicit purpose text
- **WHEN** a reviewer opens a synced spec under `openspec/specs/`
- **THEN** the spec MUST include a capability-specific Purpose section and MUST
  NOT contain archive-generated `Purpose TBD` placeholder text

### Requirement: Surface v0.2.0 release notes and final approval review
The evidence map SHALL link the `v0.2.0` release-notes draft and final approval
checklist as review artifacts without treating them as publication records.

#### Scenario: Evidence map includes final approval artifacts
- **WHEN** the `v0.2.0` final approval checklist exists
- **THEN** the evidence map MUST link the release-notes draft, final approval
  Markdown checklist, final approval JSON checklist, final approval input
  manifest, synced OpenSpec spec, and phase Human Brief
- **AND** the evidence map MUST describe them as release-review artifacts rather
  than a tag, GitHub Release, Marketplace publication, release approval,
  production readiness, or automatic publication
