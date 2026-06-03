## Context

Diagnostic artifacts intentionally include `generated_at` metadata. That is
useful for local provenance, but it makes direct `git diff` or byte-for-byte CI
comparison noisy after regeneration. The existing CI gate therefore validates
committed demo artifacts rather than regenerating and diffing them.

This phase adds a local semantic comparison layer. It does not change how scan,
lint, inspect, route, dashboard, CI gate, or PR review packet artifacts are
generated. Instead, it normalizes a small allowlist of volatile fields before
comparison.

## Goals / Non-Goals

**Goals:**

- Compare expected and actual diagnostic artifacts after removing approved
  volatile fields such as `generated_at` and local artifact path displays.
- Report deterministic JSON and Markdown drift results.
- Support individual files and directory-level comparison for the committed
  diagnostic demo pack.
- Keep output suitable for local review and CI logs.

**Non-Goals:**

- Changing artifact schemas or removing `generated_at` from generated outputs.
- Re-running scan/lint/inspect/route inside the drift command.
- Posting PR comments, writing annotations, publishing a Marketplace Action, or
  blocking merges beyond normal CI command failure.
- Treating drift check results as benchmark or runtime-router proof.

## Decisions

- **Normalize before compare.** The drift check parses artifacts and removes
  allowlisted volatile fields recursively before comparing JSON structures.
  Local artifact path displays are normalized to file names so regeneration in
  a temporary directory does not create false drift.
- **File-pair and directory modes.** Directory mode compares known diagnostic
  artifact filenames under two directories. File-pair mode keeps the core
  behavior testable and useful outside the demo pack.
- **HTML payload extraction for dashboard.** The diagnostic dashboard embeds a
  JSON payload in `window.__SKILLEVAL_DIAGNOSTIC_DASHBOARD__`; comparing that
  payload is more stable than comparing surrounding HTML bytes.
- **Reports mirror gate style.** JSON is the stable machine-readable surface;
  Markdown is a compact human-readable summary.

## Risks / Trade-offs

- **Risk: Normalization hides meaningful changes.** Mitigation: v1 ignores only
  `generated_at` and local artifact path displays, and reports the normalized
  field classes in output.
- **Risk: HTML parsing grows brittle.** Mitigation: support the known dashboard
  payload marker only and fail clearly when it is absent.
- **Risk: Users confuse drift check with release approval.** Mitigation: docs
  and reports frame it as artifact drift detection, not release or runtime
  approval.
