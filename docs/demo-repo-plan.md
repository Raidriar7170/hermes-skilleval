# Future Demo Repository Plan

This is a plan for a future `Raidriar7170/hermes-skilleval-demo` repository.
It does not claim that the repository already exists.

## Goal

Provide a tiny external consumer repository that copies the public
`examples/github-action/skills/` and `examples/github-action/benchmark/`
fixtures, then calls `Raidriar7170/hermes-skilleval@v0.3.0` from GitHub
Actions.

## Good PR Scenario

A Good PR changes skill copy or metadata while preserving the expected gold
skill choices and avoiding negative skills. The Action summary should report
`ALLOW_MERGE`, with `recall_at_5` at `1.0` and `negative_hit_rate` at `0.0`.

## Bad PR Scenario

A Bad PR introduces a routing regression by weakening a gold skill, adding a
confusing near-miss negative, or changing benchmark labels so the gate misses a
gold skill or selects a negative skill. The Action summary should report
`BLOCK_MERGE`.

## Boundaries

This future demo would be a reusable repository Action example, not a
Marketplace-published Action, not a GitHub API PR comment bot, not a SaaS
dashboard, and not a runtime MCP router. It would not approve merges
automatically.
