## ADDED Requirements

### Requirement: Summarize external validation pack checks
The CI summary SHALL include the External Skill Library Validation Pack as an
explicit check and group its changed files as diagnostic evidence.

#### Scenario: Include external pack check outcome
- **WHEN** a maintainer provides an `external-pack` check outcome to the CI
  summary command
- **THEN** the summary MUST list the external pack check and include it in the
  final `ALLOW_MERGE` / `BLOCK_MERGE` decision

#### Scenario: Group external pack files as diagnostics
- **WHEN** changed files include paths under
  `docs/demo/external-skill-library-validation/`
- **THEN** the CI summary MUST group those paths under diagnostics without
  requiring GitHub API access
