## Why

Skill Library Maintainers can now fail CI on diagnostic artifact risk, but a
failing or noisy gate still needs a concise reviewer-facing summary for pull
request discussion. The next bounded step is a local PR review surface that
turns gate/artifact evidence into Markdown and JSON without calling GitHub APIs
or claiming Marketplace Action behavior.

## What Changes

- Add a deterministic PR review surface command that reads diagnostic gate and
  artifact outputs and writes a compact JSON/Markdown review packet.
- Summarize the CI verdict, lint findings, conflict clusters, route risk flags,
  evidence gaps, and non-overclaim boundaries for human review.
- Add demo review packet artifacts generated from the committed diagnostic demo
  pack.
- Document local usage as a copy/paste or CI artifact surface only.
- No breaking changes.

## Capabilities

### New Capabilities

- `diagnostic-pr-review-surface`: Local reviewer-facing packets for
  diagnostic CI evidence.

### Modified Capabilities

- None.

## Impact

- Affected code: CLI parser, a small review-surface module, diagnostic demo
  docs, and tests.
- Affected artifacts: diagnostic demo PR review JSON/Markdown reports.
- Dependencies: no new third-party dependencies.
- Non-goals: no GitHub API calls, no PR comments or annotations, no Marketplace
  Action release, no merge automation, no SaaS backend, and no runtime MCP
  router.
