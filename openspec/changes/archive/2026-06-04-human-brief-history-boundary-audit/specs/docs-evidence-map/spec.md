## MODIFIED Requirements

### Requirement: Keep public evidence surfaces current
The project SHALL keep reviewer-facing current public surfaces aligned with the
latest committed evidence phase and current validation count, while preserving
historical Human Briefs as contemporaneous phase records when they clearly mark
old exact counts as original run or baseline evidence.

#### Scenario: Evidence map includes reusable action RC evidence
- **WHEN** the reusable GitHub Action RC is present in the repository
- **THEN** the evidence map MUST link to the action metadata, example fixture,
  synced OpenSpec spec, and phase Human Brief
- **AND** the evidence map MUST describe those artifacts as release-candidate
  evidence rather than Marketplace publication, release approval, PR
  automation, SaaS, runtime MCP routing, or production readiness

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
