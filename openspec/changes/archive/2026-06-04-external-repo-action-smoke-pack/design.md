## Context

The reusable GitHub Action RC currently ships `action.yml`, a public-safe
example fixture, and a fresh-copy smoke test. The remaining reviewer gap is an
external-consumer view: a separate repository layout with its own `skills/`,
`benchmark/`, workflow, and output directory that runs the same gate behavior
without relying on this repository's internal example paths.

## Goals / Non-Goals

**Goals:**
- Prove local external-consumer path behavior without requiring GitHub accounts,
  secrets, remote repositories, `act`, tags, releases, or Marketplace
  publication.
- Exercise the action's actual gate shell script with `SKILLEVAL_*` environment
  variables and `GITHUB_STEP_SUMMARY`, rather than only calling the Python
  helper directly.
- Commit a compact evidence pack that reviewers can inspect without rerunning
  the smoke.
- Keep all wording as RC evidence, not release approval.

**Non-Goals:**
- No hosted GitHub Actions consumer run.
- No remote repository creation or PR workflow.
- No Marketplace Action, release, tag, PR comments, annotations, SaaS, or
  runtime MCP router behavior.
- No new router or benchmark metric claims.

## Decisions

1. Generate a temporary `consumer-repo` in tests instead of committing a second
   full fixture tree. This keeps the permanent repo surface small while proving
   independent consumer paths.
2. Add a committed smoke evidence pack under
   `docs/demo/external-repo-action-smoke-pack/` with the commands, workflow
   snippet, generated gate artifacts, and boundary notes. This is durable
   evidence, not a runtime fixture source of truth.
3. Parse the action run step from `action.yml` in the test and execute it from
   the consumer repository with environment variables populated to consumer
   paths. This catches shell/env regressions closer to the composite action than
   a CLI-only test.
4. Link the pack from README/usage/evidence map so reviewers can find it without
   treating it as release publication.

## Risks / Trade-offs

- Local shell execution cannot prove GitHub-hosted runner behavior. Mitigation:
  say this is a local consumer smoke, and require a later confirmed phase for a
  remote hosted run.
- Committed generated artifacts can drift. Mitigation: project-surface tests
  check the pack structure and generated decisions.
- Shell-step parsing can become brittle if `action.yml` changes shape.
  Mitigation: scope the test to the existing named "Run SkillEval gate" step.
