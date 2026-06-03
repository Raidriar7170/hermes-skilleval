## ADDED Requirements

### Requirement: Generate PR-facing CI summaries
The system SHALL provide a deterministic CI summary command that writes JSON and
Markdown summaries for SkillEval validation checks.

#### Scenario: Summarize required checks
- **WHEN** a maintainer provides explicit check outcomes for pytest, OpenSpec
  validation, release-check, diagnostic CI gate, diagnostic artifact drift, and
  overclaim scanning
- **THEN** the system MUST write a Markdown summary that lists each check and a
  machine-readable JSON summary with a final decision

#### Scenario: Block on failed required checks
- **WHEN** any required check outcome is failed, cancelled, timed out, missing,
  or otherwise not passing
- **THEN** the system MUST set the final decision to `BLOCK_MERGE`

#### Scenario: Allow when required checks pass
- **WHEN** all required check outcomes are passing and the overclaim scan has no
  positive matches
- **THEN** the system MUST set the final decision to `ALLOW_MERGE`

### Requirement: Group changed files for review
The system SHALL group changed files from an explicit changed-file list into
stable review categories.

#### Scenario: Group known repository surfaces
- **WHEN** the changed-file list includes workflow, source, test, documentation,
  OpenSpec, diagnostic demo, or other files
- **THEN** the system MUST report deterministic group counts and paths without
  requiring GitHub API access

### Requirement: Preserve bounded PR-facing claims
The system SHALL describe the CI summary as a local and GitHub Actions summary
surface only.

#### Scenario: Avoid automation product claims
- **WHEN** docs, Markdown summaries, workflow examples, or reports describe the
  PR-facing CI summary
- **THEN** they MUST NOT claim GitHub API PR comments, PR annotations,
  Marketplace Action release, SaaS, runtime MCP routing, benchmark SOTA,
  production readiness, automatic merge approval, or release approval

### Requirement: Write summary in GitHub Actions
The repository validation workflow SHALL publish the CI summary through
`$GITHUB_STEP_SUMMARY`.

#### Scenario: Always publish summary after validation checks
- **WHEN** GitHub Actions runs the validate workflow
- **THEN** it MUST run the CI summary step with `if: always()`, append Markdown
  to `$GITHUB_STEP_SUMMARY`, and enforce the final decision without requiring
  tokens or GitHub API calls
