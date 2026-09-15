## ADDED Requirements

### Requirement: Shared trusted replay
The system SHALL use one capture, reconstruction and isolated verification path for two qualified repositories with explicit package and CLI identity.

#### Scenario: Candidate patch verification
- **WHEN** a qualified task supplies a patch
- **THEN** the system rebuilds fresh base, checks source identity, and distinguishes target failure, regression failure, invalid collection and passing results.

### Requirement: Fair fixed baseline
The system SHALL select exactly two fixed skills using repository configuration alone and SHALL give F/S identical presentation semantics and shared resources.

#### Scenario: Request text changes
- **WHEN** task text or labels change for the same repository
- **THEN** fixed selection remains unchanged and performs no model loading.

### Requirement: Installable and honest entrypoints
The system SHALL provide wheel-installed offline doctor and records paths, and explicit replay versus assist acceptance boundaries.

#### Scenario: Missing model assets
- **WHEN** doctor or native/fixed runs without retrieval assets
- **THEN** those paths do not load retrieval models and doctor reports missing strong capabilities accurately.

### Requirement: Complete public evidence
The system SHALL retain all launched attempts, bind patches and trusted results, and publish only inspected minimal records on the designated draft branch.

#### Scenario: Recompute records
- **WHEN** offline records are recomputed
- **THEN** missing verification cannot become a pass and existing records are not overwritten.
