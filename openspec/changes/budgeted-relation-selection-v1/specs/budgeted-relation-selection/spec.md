## ADDED Requirements

### Requirement: Sparse immutable relations
The opt-in store SHALL bind exact inputs and distinguish not analyzed, positive, zero, semantic unresolved, missing, invalid and rejected states. It SHALL preserve first valid rows and retry only missing or malformed rows.

#### Scenario: Partial matrix
- **WHEN** 322 valid rows arrive for 336 requested pairs
- **THEN** all 322 persist and 14 remain transport missing without affecting N/M

#### Scenario: Resume
- **WHEN** a saved input is resumed
- **THEN** accepted semantic outcomes and elapsed costs remain immutable and changed input is rejected

### Requirement: Bounded current package
A SHALL save M first, share exact feasible-set optimization with D, use conservative unknown bounds, stop within declared acquisition budgets and return the current legal pack without requiring full matrix completion.

#### Scenario: No positive support
- **WHEN** helper calls yield no positive support or time expires
- **THEN** A returns M with its incurred costs and explicit stop/missing states

### Requirement: Separate finite comparisons
The study SHALL freeze final-index inputs and execute at most two prefixes and twelve tails per protocol, preserving all attempts. P SHALL charge method-specific overhead; C SHALL use equal tails with separate overhead disclosure. Trusted target and regression evidence alone SHALL determine functional labels.

#### Scenario: Dense failure
- **WHEN** D remains incomplete
- **THEN** independent P cells remain runnable and only affected D evidence remains partial

#### Scenario: Replay
- **WHEN** saved evidence is replayed
- **THEN** results are recomputed without model calls or new acceptance runs and legacy evidence remains unchanged
