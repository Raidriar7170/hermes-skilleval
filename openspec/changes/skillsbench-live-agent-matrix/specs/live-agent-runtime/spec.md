## ADDED Requirements

### Requirement: Adapt SkillsBench tasks for live-agent selection

The system SHALL validate SkillsBench-shaped local task inputs before live-agent
selection or matrix execution.

#### Scenario: Validate selectable tasks

- **WHEN** SkillsBench task data is validated
- **THEN** each selectable task MUST have a non-empty prompt, deterministic
  verifier metadata, no private credential requirement, and controlled network
  requirements
- **AND** malformed files, duplicate IDs, missing skill definitions, private
  credentials, and uncontrolled network requirements MUST fail closed
- **AND** task prompts and public skill metadata MUST fail closed when they leak
  task IDs, oracle skill IDs, or oracle/gold/source-task labels
- **AND** frozen-evaluation upstream references MUST be immutable commit SHAs,
  with fixture-only or pilot-mode records labeled as non-final evidence

### Requirement: Freeze live-agent task plans

The system SHALL write explicit pilot or frozen live-agent task plans before
executing a matrix.

#### Scenario: Freeze selected tasks

- **WHEN** a plan is written
- **THEN** it MUST record mode, run ID, upstream reference, license note, input
  SHA-256/size provenance, selected tasks, and global skill registry
- **AND** frozen mode MUST require oracle qualification records for every
  selected task
- **AND** pilot mode MUST remain distinguishable from frozen evaluation mode
- **AND** plan files MUST write a digest sidecar and derived hashes for selected
  tasks, prompt/verifier fields, global registry, oracle qualification records,
  and matrix entries
- **AND** matrix execution MUST recompute frozen derived fields from frozen
  source inputs and fail closed if the plan, source files, or derived fields
  changed after planning

### Requirement: Build three-condition live-agent matrix

The system SHALL build no-skill, routed-skill, and oracle-skill live-agent runs
from the same prompt for every selected task.

#### Scenario: Build comparable run entries

- **WHEN** a selected task is expanded into matrix entries
- **THEN** all three conditions MUST share the same prompt hash
- **AND** each run MUST use a fresh workspace
- **AND** the global registry, not a per-task-only registry, MUST provide skill
  definitions
- **AND** routed-skill entries MUST mount only stable de-duplicated routed top-k
  skills while preserving full prediction counts in diagnostics

### Requirement: Record live-agent evidence without promoting routers

The system SHALL record live-agent evidence envelopes without treating process
success as task success or promoting any router.

#### Scenario: Write matrix report

- **WHEN** matrix execution records traces
- **THEN** verifier pass/fail MUST be the only source of task success
- **AND** the report MUST include trace paths, skill inventory, mounted/read/
  unknown evidence, timeout, process exit, verifier result, and redacted events
- **AND** Hermes Negative Hit Rate MUST NOT be calculated unless explicit
  negative labels exist

### Requirement: Report SkillRouter and SkillsBench overlap decisions

The system SHALL separate independent-generalization claims from linked-transfer
or unavailable overlap evidence.

#### Scenario: Detect overlap from optional SkillRouter inputs

- **WHEN** a SkillsBench plan is written with optional SkillRouter task inputs
- **THEN** the overlap report MUST compute exact ID overlap, normalized
  prompt/query text-hash overlap, and declared SkillsBench metadata links
- **AND** it MUST emit one of DISJOINT, LINKED_TRANSFER, INVALID, or UNAVAILABLE
- **AND** missing SkillRouter inputs MUST report UNAVAILABLE with
  `independent_generalization_claim=false`
