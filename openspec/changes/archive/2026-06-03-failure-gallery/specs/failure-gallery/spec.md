## ADDED Requirements

### Requirement: Publish failure gallery
The project SHALL provide a reviewer-facing Failure Gallery that indexes
committed failure evidence without becoming a second source of truth.

#### Scenario: Gallery explains scope
- **WHEN** a reviewer opens `docs/failure-gallery.md`
- **THEN** the page MUST state that it is a navigation layer over committed
  artifacts and that canonical evidence remains in the linked files

#### Scenario: Gallery groups release-gate failures
- **WHEN** a reviewer reads the gallery
- **THEN** the page MUST include release-gate examples that link to Phase 16
  blind-validation, Phase 17 release decision, and Phase 18 reproducibility
  artifacts

#### Scenario: Gallery groups diagnostic failures
- **WHEN** a reviewer reads the gallery
- **THEN** the page MUST include diagnostic examples that link to lint findings,
  conflict risk clusters, route risk flags, and local PR review packet evidence

#### Scenario: Gallery groups CI boundary failures
- **WHEN** a reviewer reads the gallery
- **THEN** the page MUST include CI summary and overclaim boundary examples
  without claiming automatic merge approval

### Requirement: Link failure gallery from public entry points
Public documentation SHALL make the Failure Gallery discoverable from existing
reviewer paths.

#### Scenario: README links gallery
- **WHEN** a reviewer follows the README quick review path
- **THEN** the README MUST link to `docs/failure-gallery.md`

#### Scenario: Evidence map links gallery
- **WHEN** a reviewer uses the evidence map
- **THEN** the evidence map MUST link to `docs/failure-gallery.md` and describe
  it as a gallery of examples, not canonical evidence

#### Scenario: Usage docs link gallery
- **WHEN** a maintainer reads the local usage guide
- **THEN** `docs/usage.md` MUST link to the gallery as a review aid

### Requirement: Test failure gallery integrity
The test suite SHALL verify that the Failure Gallery remains linkable,
bounded, and stable.

#### Scenario: Verify gallery links
- **WHEN** project-surface tests scan the Failure Gallery
- **THEN** they MUST fail if local relative links in the gallery do not resolve
  to existing repository paths

#### Scenario: Verify gallery wording
- **WHEN** project-surface tests scan the Failure Gallery and linked public docs
- **THEN** they MUST fail if the gallery introduces disallowed product,
  benchmark-leadership, runtime, or release-approval claims
