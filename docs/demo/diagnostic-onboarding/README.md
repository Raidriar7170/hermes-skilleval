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

## Regenerate

Run these commands from the repository root:

```bash
ROOT=docs/demo/diagnostic-onboarding

PYTHONPATH=src python -m hermes_skilleval.cli scan \
  "$ROOT/source/skills" \
  --output "$ROOT/scan.json"

PYTHONPATH=src python -m hermes_skilleval.cli lint \
  --index "$ROOT/scan.json" \
  --output "$ROOT/lint.json"

PYTHONPATH=src python -m hermes_skilleval.cli inspect \
  --index "$ROOT/scan.json" \
  --output "$ROOT/inspect.json"

PYTHONPATH=src python -m hermes_skilleval.cli route \
  "smoke test a local browser page and check console errors" \
  --index "$ROOT/scan.json" \
  --inspect "$ROOT/inspect.json" \
  --top-k 3 \
  --output "$ROOT/route-browser-smoke.json"

PYTHONPATH=src python -m hermes_skilleval.cli route \
  "debug failing tests with a red-green loop" \
  --index "$ROOT/scan.json" \
  --inspect "$ROOT/inspect.json" \
  --top-k 3 \
  --output "$ROOT/route-debug-red-green.json"

PYTHONPATH=src python -m hermes_skilleval.cli diagnostic-dashboard \
  --scan "$ROOT/scan.json" \
  --lint "$ROOT/lint.json" \
  --inspect "$ROOT/inspect.json" \
  --route "$ROOT/route-browser-smoke.json" \
  --route "$ROOT/route-debug-red-green.json" \
  --output "$ROOT/dashboard.html"

PYTHONPATH=src python -m hermes_skilleval.cli diagnostic-ci-gate \
  --scan "$ROOT/scan.json" \
  --lint "$ROOT/lint.json" \
  --inspect "$ROOT/inspect.json" \
  --route "$ROOT/route-browser-smoke.json" \
  --route "$ROOT/route-debug-red-green.json" \
  --output "$ROOT/ci-gate-report.json" \
  --markdown-output "$ROOT/ci-gate-report.md" \
  --max-lint-findings 5 \
  --max-conflict-clusters 4 \
  --max-route-risk-flags 15 \
  --min-route-candidates 3
```

The threshold values above match this intentionally noisy demo pack: five lint
findings, four review-worthy conflict clusters, and fifteen route risk flags.
