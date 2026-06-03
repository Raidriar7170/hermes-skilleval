# Diagnostic Onboarding Demo Evidence Pack

This directory is a small committed evidence pack for the zero-label diagnostic
onboarding path. It uses five local Markdown `SKILL.md` files to show scan,
lint, inspect, route, and static dashboard artifacts that a skill library
maintainer can review.

It is a demo evidence pack only: not a public comparison set, not a live agent
integration, not a Marketplace Action, not a PR annotation system, not SaaS,
not a runtime MCP router, and not a SOTA claim.

## Contents

- `source/skills/`: local Markdown skill source used by the demo.
- `scan.json`: source-annotated skill index from the demo source.
- `lint.json`: routing-clarity findings, including the intentionally thin
  `general-helper` skill.
- `inspect.json`: review-worthy conflict risk clusters, including the nearby
  browser smoke and visual review skills.
- `route-browser-smoke.json` and `route-debug-red-green.json`: unlabeled route
  examples with matched evidence terms and risk flags.
- `dashboard.html`: self-contained static diagnostic dashboard.
- `ci-gate-report.json` and `ci-gate-report.md`: artifact-based CI validation
  report generated with explicit demo thresholds.
- `pr-review-packet.json` and `pr-review-packet.md`: local reviewer-facing
  diagnostic packet generated from the CI gate report.

## Regenerate

Run these commands from the repository root:

```bash
ROOT=docs/demo/diagnostic-onboarding
TMP_ROOT="${TMPDIR:-/tmp}/diagnostic-onboarding"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT"

PYTHONPATH=src python -m hermes_skilleval.cli scan \
  "$ROOT/source/skills" \
  --output "$TMP_ROOT/scan.json"

PYTHONPATH=src python -m hermes_skilleval.cli lint \
  --index "$TMP_ROOT/scan.json" \
  --output "$TMP_ROOT/lint.json"

PYTHONPATH=src python -m hermes_skilleval.cli inspect \
  --index "$TMP_ROOT/scan.json" \
  --output "$TMP_ROOT/inspect.json"

PYTHONPATH=src python -m hermes_skilleval.cli route \
  "smoke test a local browser page and check console errors" \
  --index "$TMP_ROOT/scan.json" \
  --inspect "$TMP_ROOT/inspect.json" \
  --top-k 3 \
  --output "$TMP_ROOT/route-browser-smoke.json"

PYTHONPATH=src python -m hermes_skilleval.cli route \
  "debug failing tests with a red-green loop" \
  --index "$TMP_ROOT/scan.json" \
  --inspect "$TMP_ROOT/inspect.json" \
  --top-k 3 \
  --output "$TMP_ROOT/route-debug-red-green.json"

PYTHONPATH=src python -m hermes_skilleval.cli diagnostic-dashboard \
  --scan "$TMP_ROOT/scan.json" \
  --lint "$TMP_ROOT/lint.json" \
  --inspect "$TMP_ROOT/inspect.json" \
  --route "$TMP_ROOT/route-browser-smoke.json" \
  --route "$TMP_ROOT/route-debug-red-green.json" \
  --output "$TMP_ROOT/dashboard.html"

PYTHONPATH=src python -m hermes_skilleval.cli diagnostic-ci-gate \
  --scan "$TMP_ROOT/scan.json" \
  --lint "$TMP_ROOT/lint.json" \
  --inspect "$TMP_ROOT/inspect.json" \
  --route "$TMP_ROOT/route-browser-smoke.json" \
  --route "$TMP_ROOT/route-debug-red-green.json" \
  --output "$TMP_ROOT/ci-gate-report.json" \
  --markdown-output "$TMP_ROOT/ci-gate-report.md" \
  --max-lint-findings 5 \
  --max-conflict-clusters 4 \
  --max-route-risk-flags 15 \
  --min-route-candidates 3

PYTHONPATH=src python -m hermes_skilleval.cli diagnostic-pr-review-surface \
  --gate-report "$TMP_ROOT/ci-gate-report.json" \
  --output "$TMP_ROOT/pr-review-packet.json" \
  --markdown-output "$TMP_ROOT/pr-review-packet.md"

PYTHONPATH=src python -m hermes_skilleval.cli diagnostic-artifact-drift-check \
  --expected "$ROOT" \
  --actual "$TMP_ROOT" \
  --output "$TMP_ROOT/drift-report.json" \
  --markdown-output "$TMP_ROOT/drift-report.md"
```

The threshold values above match this intentionally noisy demo pack: five lint
findings, four review-worthy conflict clusters, and fifteen route risk flags.
The drift check ignores approved volatile fields such as `generated_at` and
local artifact path displays while still reporting semantic artifact changes.
The PR review packet and drift check are local reading/comparison artifacts
only; they do not call the GitHub API, post PR comments, write annotations,
publish a Marketplace Action, run a SaaS service, approve a release, or act as
a runtime MCP router.
