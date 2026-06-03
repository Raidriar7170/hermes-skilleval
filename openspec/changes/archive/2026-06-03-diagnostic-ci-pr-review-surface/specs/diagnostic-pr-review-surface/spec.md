## ADDED Requirements

### Requirement: Generate PR review packets from diagnostic evidence
The system SHALL provide a deterministic diagnostic PR review surface that reads
diagnostic CI gate output and writes JSON and Markdown review packets for human
pull request review.

#### Scenario: Write reviewer-facing packet
- **WHEN** a Skill Library Maintainer runs the PR review surface with a valid
  diagnostic CI gate report
- **THEN** the system MUST write JSON and Markdown packets that summarize the
  gate verdict, policy status, reviewer attention items, evidence gaps, and
  display-safe source artifact paths from the gate report

#### Scenario: Preserve gate verdict source
- **WHEN** the diagnostic CI gate report contains pass or fail status
- **THEN** the PR review surface MUST use that gate report as the verdict source
  instead of recomputing pass/fail semantics from raw artifacts

#### Scenario: Reject invalid gate report
- **WHEN** the PR review surface receives a missing, malformed, or unsupported
  gate report
- **THEN** the system MUST fail with a clear error naming the invalid input

### Requirement: Keep PR review surface bounded
The system SHALL describe the PR review surface as local reviewer-facing
diagnostic evidence, not as hosted pull request automation.

#### Scenario: Avoid GitHub integration claims
- **WHEN** generated packets, docs, or examples describe the PR review surface
- **THEN** they MUST NOT claim GitHub API integration, PR comments, PR
  annotations, automatic merge blocking beyond CI failure semantics, Marketplace
  Action release, SaaS, runtime MCP routing, or benchmark SOTA

#### Scenario: Preserve review-worthy language
- **WHEN** the packet lists conflict clusters or route risk flags
- **THEN** it MUST describe them as review-worthy diagnostic signals and MUST
  NOT claim that skills are definitely duplicated, unsafe, or wrong

### Requirement: Demonstrate review packet artifacts
The system SHALL include committed demo review packet artifacts generated from
the diagnostic onboarding demo evidence pack.

#### Scenario: Inspect demo review packet
- **WHEN** a Skill Library Maintainer opens the diagnostic demo directory
- **THEN** the system MUST provide JSON and Markdown PR review packet artifacts
  generated from the committed diagnostic demo evidence

#### Scenario: Regenerate demo review packet
- **WHEN** a developer follows the demo README commands from the repository root
- **THEN** the system MUST regenerate the review packet artifacts without
  requiring network access, GitHub credentials, model downloads, a server, or a
  SaaS backend
