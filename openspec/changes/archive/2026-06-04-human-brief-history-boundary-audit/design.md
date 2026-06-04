## Context

The repository now has two valid kinds of count-bearing documentation:
current reviewer entry points that should reflect the latest full-suite count,
and historical autonomous-loop Human Briefs that record what happened during a
specific phase. Recent public-evidence work already updated the current
surfaces to `394 passed`; this phase handles the remaining ambiguity around old
loop reports that still mention `384` or `391` run counts.

## Goals / Non-Goals

**Goals:**
- Make historical loop briefs explicit when they retain original run or
  baseline counts.
- Keep current public reviewer surfaces on the latest validation count.
- Add tests so future count refreshes do not accidentally rewrite history or
  expose stale counts as current proof.
- Generate a phase Human Brief from the OpenSpec artifacts, diff, and
  validation output.

**Non-Goals:**
- No release, tag, Marketplace Action, PR comment bot, PR annotation, SaaS, or
  runtime MCP router work.
- No broad rewrite of every older Human Brief.
- No change to runtime CLI behavior or benchmark claims.

## Decisions

1. Treat exact counts in older autonomous-loop reports as historical evidence,
   not stale current-count surfaces. This avoids falsifying the report of what
   happened in that bounded phase.
2. Add wording near the old count in the affected briefs instead of replacing
   the old count with `394 passed`. Replacing it would erase useful run
   provenance.
3. Keep the current-count regression test focused on public entry points,
   evidence-map-linked briefs, and active/synced OpenSpec artifacts, then add a
   separate test for historical brief count boundary wording.
4. Use docs/tests only. The change should remain safe to archive and should not
   imply release readiness.

## Risks / Trade-offs

- Historical brief wording could make old counts look current if placed too far
  from the count. Mitigation: put explicit "historical/original/baseline" text
  in the same affected brief section.
- Updating too many old reports could create a second source of truth. Mitigation:
  only touch reports with old exact counts that are visible from the audit.
- Tests could become brittle if they hard-code every historical report forever.
  Mitigation: use a small stale-count scanner over Human Brief HTML files rather
  than a long per-file assertion list.
