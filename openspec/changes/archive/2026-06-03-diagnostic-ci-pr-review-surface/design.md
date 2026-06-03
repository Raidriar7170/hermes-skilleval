## Context

The repository already has a Diagnostic Onboarding Path, committed demo
artifacts, and `skilleval diagnostic-ci-gate`. The gate is good for local or CI
pass/fail semantics, but its JSON output is still too mechanical for a pull
request reviewer who needs to understand what changed, which risks deserve
attention, and which claims remain out of scope.

`CONTEXT.md` defines PR annotations and Marketplace Action packaging as later
productization. This phase therefore stops at local reviewer-facing artifacts:
JSON for machines and Markdown for copy/paste or CI artifact upload.

## Goals / Non-Goals

**Goals:**

- Provide a deterministic command that writes a compact PR review packet from
  diagnostic CI gate and diagnostic artifact evidence.
- Preserve the existing artifact contract and gate semantics.
- Highlight reviewer-relevant evidence: verdict, policy failures, lint finding
  counts, conflict clusters, route risk flags, missing route evidence, and
  bounded next steps.
- Add committed demo review packet artifacts and tests to prevent drift.

**Non-Goals:**

- Calling GitHub APIs, posting PR comments, writing annotations, or checking
  pull request metadata.
- Publishing a Marketplace Action or changing workflow permissions.
- Regenerating diagnostic scan/lint/inspect/route artifacts inside the review
  command.
- Adding a runtime MCP router, hosted UI, SaaS backend, or new benchmark claim.

## Decisions

- **Review packet over annotation API.** The command writes local files only.
  This gives maintainers an inspectable surface now without requiring account,
  token, permission, or release decisions.
- **Consume the existing gate report.** The command reads the diagnostic CI gate
  report and uses the artifact references and summaries already recorded there
  instead of recomputing scan/lint/inspect/route evidence. This keeps review
  output tied to the evidence that CI already validated.
- **Bounded Markdown structure.** The Markdown output uses stable sections such
  as verdict, must review, evidence gaps, and boundaries not to overstate. This
  makes it useful in PR discussions while avoiding product claims.
- **JSON mirrors Markdown.** The JSON output carries the same summary data so
  future phases can reuse it for annotations or richer CI surfaces without
  scraping Markdown.

## Risks / Trade-offs

- **Risk: Users confuse the packet with live PR integration.** Mitigation:
  docs, specs, and generated Markdown must state that this is a local artifact,
  not GitHub API integration.
- **Risk: Review packets get noisy for large libraries.** Mitigation: v1 reports
  counts and top evidence examples rather than dumping all artifact contents.
- **Risk: Gate report and artifact inputs disagree.** Mitigation: the command
  treats the gate report as the verdict source and uses diagnostic artifacts for
  evidence summaries only.
- **Risk: External consumers depend on Markdown wording.** Mitigation: JSON is
  the stable machine-readable surface; Markdown is for humans.
