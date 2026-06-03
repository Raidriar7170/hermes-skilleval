## Why

The project now has strong release, diagnostic, CI, and external-style
validation evidence, but reviewers still have to discover those artifacts by
moving across README sections, demo folders, Human Briefs, and OpenSpec specs.
This phase adds a bounded evidence map so a Skill Library Maintainer or
interviewer can follow the proof chain without mistaking it for a product
claim.

## What Changes

- Add a reviewer-facing documentation evidence map that groups canonical
  artifacts by purpose: release gate, diagnostic onboarding, external validation
  pack, PR-facing CI summary, OpenSpec specs, and Human Briefs.
- Link the evidence map from README and usage/docs surfaces without replacing
  existing authoritative source files.
- Add tests that verify links exist, core evidence categories are present, and
  public wording stays bounded.
- Generate a phase Human Brief and archive this OpenSpec change after
  validation.

## Capabilities

### New Capabilities

- `docs-evidence-map`: bounded reviewer-facing evidence navigation for the
  current SkillEval proof chain.

### Modified Capabilities

- None.

## Impact

- Affected docs: README, `docs/usage.md`, and a new evidence map document.
- Affected tests: project-surface checks for link integrity and claim
  boundaries.
- No changes to routing algorithms, diagnostic artifact schemas, release-check
  behavior, GitHub permissions, external services, or workflow token scopes.
