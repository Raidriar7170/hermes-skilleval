## MODIFIED Requirements

### Requirement: Generate PR-facing CI summaries
The system SHALL provide a deterministic CI summary command that writes JSON and Markdown summaries for SkillEval validation checks, preserving actual underlying outcomes and overclaim ambiguity.

#### Scenario: Summarize required checks
- **WHEN** a maintainer provides explicit check outcomes for pytest, OpenSpec validation, release-check, diagnostic CI gate, diagnostic artifact drift, and overclaim scanning
- **THEN** the system MUST write a Markdown summary listing each check and a machine-readable final decision

#### Scenario: Block on failed required checks
- **WHEN** any required outcome is failed, cancelled, timed out, missing, ambiguous or otherwise not passing
- **THEN** the final decision MUST be BLOCK_MERGE even when a wrapper step succeeded

#### Scenario: Allow when required checks pass
- **WHEN** all required outcomes pass and overclaim scanning contains no affirmative or unresolved ambiguous matches
- **THEN** the final decision MUST be ALLOW_MERGE

#### Scenario: Scope negation to its claim
- **WHEN** explicit English/Chinese negation denies SOTA while a separate clause asserts superiority
- **THEN** the negative claim MUST not trigger an affirmative match and the separate affirmative claim MUST remain detected
