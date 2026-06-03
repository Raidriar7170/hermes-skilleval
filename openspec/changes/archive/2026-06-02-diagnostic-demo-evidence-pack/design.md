## Context

The previous phase added the zero-label diagnostic CLI and stable diagnostic
artifacts. The next gap is presentation and reproducibility: users can read the
commands, but they cannot yet inspect a committed, small, end-to-end diagnostic
run that demonstrates the workflow without preparing their own skill library.

The demo pack should stay inside the Diagnostic Onboarding Path. It is evidence
for the local CLI workflow, not a CI gate, runtime MCP router, hosted dashboard,
or benchmark leaderboard.

## Goals / Non-Goals

**Goals:**

- Add a small demo skill library and/or MCP schema that exercises scan warnings,
  routing-readiness lint, conflict risk clusters, route evidence, and risk flags.
- Generate committed diagnostic artifacts under a dedicated `docs/demo/`
  directory.
- Include a short README with exact regeneration commands.
- Add tests that verify artifact presence, schema versions, dashboard
  self-containment, and bounded wording.
- Link the demo from README/usage without expanding the experiment timeline.

**Non-Goals:**

- No GitHub Action, PR annotation, or merge blocking.
- No runtime MCP server or agent plugin.
- No public benchmark, leaderboard, or SOTA claim.
- No hosted SaaS dashboard or browser server.
- No model download, embedding dependency, or network access.

## Decisions

### Decision: Commit generated artifacts instead of only documenting commands

The demo should include `scan.json`, `lint.json`, `inspect.json`, one or more
`route-*.json` files, and `dashboard.html`. This gives users immediate files to
open and gives tests concrete artifacts to verify.

Alternative considered: document commands only. Rejected because the project
already has command documentation; the gap is inspectable evidence.

### Decision: Use a small local demo library

Use a bounded fixture-style skill library under the demo directory rather than
the full benchmark skill corpus. The small library can intentionally include
nearby browser/MCP/debug skills so the Conflict Risk Cluster and route risk
flags are visible in a compact dashboard.

Alternative considered: generate artifacts from `benchmarks/skills`. Rejected
because the full corpus is noisier and makes the demo harder to audit quickly.

### Decision: Treat the demo README as the regeneration contract

The demo directory README should be the source of truth for reproduction
commands. Tests should assert key artifacts and wording, but not overfit to the
entire generated JSON formatting.

Alternative considered: add a separate script. Rejected for P0 unless repeated
manual command drift becomes a problem.

## Risks / Trade-offs

- [Risk] Committed generated artifacts can drift from the CLI. -> Mitigation:
  add artifact tests and regeneration commands.
- [Risk] Demo findings may look like definitive judgments. -> Mitigation: use
  review-worthy risk wording and test against overclaim terms.
- [Risk] README could become too long again. -> Mitigation: add a compact link
  and keep detailed commands in `docs/usage.md` and the demo README.
- [Risk] Demo library may be mistaken for a public benchmark. -> Mitigation:
  explicitly call it a demo/evidence pack, not a benchmark split.

## Migration Plan

Add the demo pack as documentation/evidence alongside the newly implemented
diagnostic CLI. No existing artifacts are removed. Existing release-check roots
remain unchanged unless later phases intentionally add diagnostic demo evidence
to release packaging.

## Open Questions

- None for this bounded phase. Future phases can decide whether diagnostic demo
  artifacts should enter the release-check public roots.
