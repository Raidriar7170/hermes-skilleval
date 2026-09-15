## ADDED Requirements

### Requirement: Gold-free supported repository assistance
The CLI SHALL preflight and assist current sqlite-utils/csvkit copies without gold or qualification, defaulting to N and allowing explicit F. Unsupported fields, layouts or missing resources MUST fail before Agent launch. N/F MUST not load retrieval dependencies.

#### Scenario: Current dirty source
- **WHEN** tracked source has staged/unstaged changes and declared untracked inputs
- **THEN** assist MUST snapshot current bytes in an independent copy, export only subsequent Agent changes, and detect rather than restore external source changes

### Requirement: Versioned operation policy
New profiles SHALL explicitly authorize paths and add/modify/delete operations. Legacy profiles MUST keep their original semantics. Prompt, preflight, capture and verification SHALL use the same policy.

#### Scenario: Ordinary and unsafe fixtures
- **WHEN** a candidate adds permitted bounded CSV/JSON data under examples
- **THEN** new policy SHALL accept it while rejecting unapproved deletion, executable or unsafe/escaping paths, and preserving rejected patches without functional certification

### Requirement: Independent bounded checks
Assist SHALL rebuild captured patches and pair immutable existing/requirement checks on baseline and candidate. Candidate-authored tests MUST not replace protected checks. Empty, skipped, errored, timed-out and wrong-import checks SHALL not count as passes; overall resolution SHALL remain unknown.

#### Scenario: Limited evidence
- **WHEN** existing tests pass but an explicit request has no executable check
- **THEN** the result SHALL show passing existing checks and NOT_VERIFIED for that requirement, with actual timing/usage and missing values preserved

### Requirement: Real installed positive path
The delivered wheel SHALL support real N and F assist smokes across both repositories, retain all starts, and produce at least one nonempty rebuilt patch passing reasonable declared checks without changing the original source.

#### Scenario: Smoke is not research
- **WHEN** developer-defined smokes execute
- **THEN** reports SHALL preserve their requests, patches and check scope without combining them into N/F research win rates
