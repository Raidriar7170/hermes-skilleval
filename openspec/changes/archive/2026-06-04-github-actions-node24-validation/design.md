## Context

The Validate workflow currently uses GitHub-hosted `ubuntu-latest` and standard
JavaScript actions such as checkout, setup-python, and upload-artifact. GitHub's
Node 20 deprecation path allows workflow owners to set
`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` to test JavaScript actions with Node 24
before the default runner runtime changes.

The repository already treats Validate as a public trust surface: pytest,
OpenSpec validation, release-check, diagnostic drift, external validation, CI
summary, and artifact upload all run there. A runtime migration should preserve
those checks rather than refactor the workflow.

## Goals / Non-Goals

**Goals:**
- Preflight the existing Validate workflow under GitHub Actions JavaScript
  action Node 24 runtime.
- Keep the change local to CI configuration, docs, tests, and the Human Brief.
- Preserve conservative public wording and existing merge/release boundaries.

**Non-Goals:**
- No GitHub Marketplace Action.
- No GitHub API PR comments, PR annotations, or bot integration.
- No new token permissions, external services, SaaS, deployment, or release
  publication.
- No runtime MCP router or production-readiness claim.
- No change to SkillEval evaluation semantics, diagnostic artifact contracts, or
  release gate decisions.

## Decisions

- Use a workflow-level `env` key with
  `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` so every JavaScript action in the
  Validate job is exercised consistently. This is smaller than editing each
  action step and matches the GitHub migration mechanism.
- Keep existing action versions (`actions/checkout@v4`, `actions/setup-python@v5`,
  and `actions/upload-artifact@v4`) and validate them remotely. Updating action
  versions is a separate maintenance decision if remote validation exposes a
  compatibility issue.
- Add project-surface tests that assert the env key is present, no insecure
  Node 20 opt-out is configured, docs mention Node 24 preflight, and public
  wording remains bounded.

## Risks / Trade-offs

- [Risk] A third-party action could fail under Node 24. -> Mitigation: run local
  tests first, then push and inspect the remote Validate workflow before calling
  the phase closed.
- [Risk] Docs could overstate the result as a Marketplace Action or future-proof
  guarantee. -> Mitigation: keep the docs to "preflight" wording and reuse the
  existing overclaim boundaries.
- [Risk] GitHub may change runtime migration details later. -> Mitigation: cite
  the current official changelog in docs and treat this as a validation step,
  not a permanent compatibility guarantee.
