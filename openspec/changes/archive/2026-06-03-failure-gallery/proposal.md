## Why

The project now has release-gate, diagnostic, external validation, CI summary,
and evidence-map artifacts, but reviewers still need to jump across many files
to understand the most important failure examples. A bounded Failure Gallery
will make those examples easier to audit without changing the underlying
release decision or diagnostic behavior.

## What Changes

- Add a reviewer-facing Markdown Failure Gallery that groups committed failure
  evidence by source and explains what each example can and cannot prove.
- Link the gallery from README, docs usage, and the evidence map so it is easy
  to find from public entry points.
- Add tests that verify gallery link integrity, required evidence groups, stable
  boundary wording, and overclaim avoidance.
- Add a Chinese Human Brief for this phase and a loop-level closeout report.

## Capabilities

### New Capabilities
- `failure-gallery`: A bounded documentation surface that indexes committed
  release-gate and diagnostic failure examples for reviewer inspection.

### Modified Capabilities
- None.

## Impact

- Affects documentation and project-surface tests only.
- Does not change router behavior, diagnostic artifact schemas, CI semantics,
  release-check logic, GitHub API behavior, Marketplace packaging, SaaS
  surfaces, or runtime MCP routing.
