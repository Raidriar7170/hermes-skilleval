## ADDED Requirements

### Requirement: Bounded public context
The system SHALL derive deterministic, sourced context only from the supplied pre-repair/current snapshot and public request, preserving unknowns and truncation.

#### Scenario: Current bytes change
- **WHEN** a relevant tracked configuration or source file changes
- **THEN** the context identity changes and the previous cache is not reused.

### Requirement: Real learned routing
The system SHALL use a real trained checkpoint for repo-aware routing and exact budget selection within the candidate pool.

#### Scenario: Checkpoint unavailable
- **WHEN** explicit repo-aware routing lacks valid weights
- **THEN** it fails clearly; auto may record a declared cheap fallback without loading heavy dependencies.

### Requirement: Pre-retrieval gate
The system SHALL fit action quality and cost only on real feedback from frozen R, separating fit, calibration and final families.

#### Scenario: Cheap decision
- **WHEN** auto selects N or F
- **THEN** encoder, reranker and heavy model construction counts are zero.

### Requirement: Shared execution and evidence
The system SHALL preserve replay qualification and assist source protection, give all five policies equal public context, and retain all actual attempts.

#### Scenario: Final comparison
- **WHEN** frozen confirmation runs
- **THEN** N/F/S/R/H execute their own decisions and report unknown outcomes without fabricated labels or utility claims.
