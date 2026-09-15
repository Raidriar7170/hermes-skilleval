## ADDED Requirements

### Requirement: Separate current generators and frozen evidence
Current generation SHALL use temporary/new output locations and reject writes to protected historical roots before mutation. Historical checks SHALL validate original bound evidence without substituting current README inputs or changing frozen results.

#### Scenario: Reordered checks
- **WHEN** release generation and historical checks run in either order
- **THEN** the same outcomes SHALL occur and original protected bytes/Git state SHALL remain unchanged

### Requirement: Current and historical documentation contracts
Current homepages SHALL expose working install/use/support/history links in both languages. Historical claims SHALL be checked against identified historical documents or snapshots, not forced into current homepages.

#### Scenario: Changed homepage
- **WHEN** a current homepage drops an obsolete phase checkbox or test total
- **THEN** current navigation checks and independently retained historical fact checks SHALL still protect their intended semantics
