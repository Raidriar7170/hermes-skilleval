## ADDED Requirements

### Requirement: Provide reproducible diagnostic demo evidence

The system SHALL provide a committed demo evidence pack for the zero-label
Diagnostic Onboarding Path.

#### Scenario: Inspect committed demo artifacts

- **WHEN** a Skill Library Maintainer opens the diagnostic demo directory
- **THEN** the system MUST provide scan, lint, inspect, route, and static
  diagnostic dashboard artifacts generated from a small local demo skill source

#### Scenario: Regenerate demo artifacts

- **WHEN** a developer follows the demo README commands from the repository root
- **THEN** the system MUST regenerate the same class of diagnostic artifacts
  without requiring labels, network access, model downloads, a server, or a SaaS
  backend

#### Scenario: Preserve bounded demo claims

- **WHEN** the demo README, artifacts, or dashboard describe diagnostic output
- **THEN** the system MUST describe findings as local review-worthy diagnostic
  evidence and MUST NOT claim SOTA benchmark status, runtime routing,
  pull-request merge blocking, or hosted SaaS functionality

### Requirement: Verify diagnostic demo artifact integrity

The system SHALL include tests that protect the diagnostic demo evidence pack
from drift.

#### Scenario: Validate demo artifact contract

- **WHEN** the test suite validates the diagnostic demo pack
- **THEN** it MUST check artifact types, schema versions, expected route
  evidence, conflict risk cluster wording, and dashboard self-containment

#### Scenario: Preserve existing release evidence

- **WHEN** the diagnostic demo pack is added
- **THEN** existing benchmark and release-gate commands and Phase 16-18 release
  evidence MUST remain reproducible
