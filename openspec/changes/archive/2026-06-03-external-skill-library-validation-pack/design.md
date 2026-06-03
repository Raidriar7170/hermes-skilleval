## Context

The current diagnostic onboarding demo validates a small local Markdown skill
folder through scan, lint, inspect, route, dashboard, CI gate, PR review packet,
and artifact drift check. The project context defines the first user as a Skill
Library Maintainer who needs to inspect real or real-shaped skill sources before
adding benchmark labels.

This phase adds a second committed evidence pack that looks more like an
external maintainer library. It must stay offline, public-safe, deterministic,
and bounded to diagnostic evidence. It must not claim that the project has a
hosted service, Marketplace Action, GitHub API PR comment bot, PR annotation
system, runtime MCP router, or release approval automation.

## Goals / Non-Goals

**Goals:**

- Provide a committed external-style evidence pack using both Markdown skill
  sources and an MCP-style tool schema source.
- Regenerate the pack from repo-local sources without network access, labels,
  model downloads, servers, or tokens.
- Validate the pack in tests and GitHub Actions with semantic drift checks.
- Make the PR-facing CI summary show the external pack check and group its
  changed files as diagnostic evidence.
- Document local simulation commands for maintainers.

**Non-Goals:**

- No live third-party repository clone or private source ingestion.
- No Marketplace Action, GitHub API comment, PR annotation, SaaS dashboard, or
  runtime MCP router.
- No new router model, benchmark promotion, or release approval claim.
- No broad rewrite of the diagnostic artifact schema.

## Decisions

1. **Use committed external-style fixtures instead of live external downloads.**
   This keeps validation deterministic and public-safe while still exercising
   the adapter on source shapes a maintainer would recognize.

2. **Represent mixed source shapes as two adjacent validation tracks.**
   The existing `scan` command intentionally accepts one supported source shape
   per invocation. Rather than changing the scan artifact schema to merge
   unrelated source types, this pack contains a Markdown track and an MCP track
   with separate scan/lint/inspect/route artifacts and separate CI gate reports.

3. **Keep drift comparison directory-based and explicit.**
   The drift check will learn an explicit external pack artifact list. This is
   lower risk than comparing every file recursively, because source files and
   Markdown documentation are not diagnostic artifacts and should remain
   reviewed by tests and normal git diff.

4. **Expose external validation as another required check in CI summary.**
   The validate workflow will pass `external-pack=${{ steps.external_pack.outcome
   }}` to `skilleval ci-summary`, keeping the final ALLOW/BLOCK decision inside
   the existing summary mechanism.

## Risks / Trade-offs

- **Fixture drift becomes noisy** -> tests regenerate into temp directories and
  compare semantic artifacts while ignoring approved volatile fields.
- **External wording overclaims real integration** -> docs and tests assert
  bounded language and forbidden product claims.
- **CI workflow grows longer** -> pack size stays tiny and uses only existing
  offline diagnostic commands.
- **Mixed-source support is mistaken for a universal adapter release** -> docs
  describe the pack as external-style validation evidence, not exhaustive
  platform support.
