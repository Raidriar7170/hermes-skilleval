# External Skill Library Validation Pack

This directory is a committed evidence pack for validating the diagnostic
workflow against external-style skill source shapes. It stays small,
repo-local, deterministic, and public-safe.

Boundary: not a Marketplace Action, not GitHub API PR comments, not PR annotations,
not SaaS, not a runtime MCP router, not a SOTA claim, not benchmark status,
not production readiness, and not release approval.

## Tracks

- `source/markdown-skills/`: public-safe Markdown `SKILL.md` fixtures that look
  like a maintainer-owned skill library.
- `source/mcp-tool-schema/tools.json`: public-safe MCP-style tool schema
  fixture.
- `markdown-skills/`: scan, lint, inspect, route, dashboard, CI gate, and PR
  review packet artifacts regenerated from the Markdown source.
- `mcp-tool-schema/`: scan, lint, inspect, route, dashboard, CI gate, and PR
  review packet artifacts regenerated from the MCP tool schema source.

## Regenerate

Run the documented local simulation from the repository root. The commands
write regenerated artifacts outside the checkout and then compare them with the
committed pack:

```bash
ROOT=docs/demo/external-skill-library-validation
TMP_ROOT="${TMPDIR:-/tmp}/external-skill-library-validation"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT/markdown-skills" "$TMP_ROOT/mcp-tool-schema"

skilleval scan "$ROOT/source/markdown-skills" \
  --output "$TMP_ROOT/markdown-skills/scan.json"
skilleval lint --index "$TMP_ROOT/markdown-skills/scan.json" \
  --output "$TMP_ROOT/markdown-skills/lint.json"
skilleval inspect --index "$TMP_ROOT/markdown-skills/scan.json" \
  --output "$TMP_ROOT/markdown-skills/inspect.json"
skilleval route "review release notes for evidence boundaries and non-goals" \
  --index "$TMP_ROOT/markdown-skills/scan.json" \
  --inspect "$TMP_ROOT/markdown-skills/inspect.json" \
  --top-k 2 \
  --output "$TMP_ROOT/markdown-skills/route-release-note-review.json"
skilleval route "audit validation workflow evidence before a maintainer review" \
  --index "$TMP_ROOT/markdown-skills/scan.json" \
  --inspect "$TMP_ROOT/markdown-skills/inspect.json" \
  --top-k 2 \
  --output "$TMP_ROOT/markdown-skills/route-workflow-evidence.json"
skilleval diagnostic-dashboard \
  --scan "$TMP_ROOT/markdown-skills/scan.json" \
  --lint "$TMP_ROOT/markdown-skills/lint.json" \
  --inspect "$TMP_ROOT/markdown-skills/inspect.json" \
  --route "$TMP_ROOT/markdown-skills/route-release-note-review.json" \
  --route "$TMP_ROOT/markdown-skills/route-workflow-evidence.json" \
  --output "$TMP_ROOT/markdown-skills/dashboard.html"
skilleval diagnostic-ci-gate \
  --scan "$TMP_ROOT/markdown-skills/scan.json" \
  --lint "$TMP_ROOT/markdown-skills/lint.json" \
  --inspect "$TMP_ROOT/markdown-skills/inspect.json" \
  --route "$TMP_ROOT/markdown-skills/route-release-note-review.json" \
  --route "$TMP_ROOT/markdown-skills/route-workflow-evidence.json" \
  --output "$TMP_ROOT/markdown-skills/ci-gate-report.json" \
  --markdown-output "$TMP_ROOT/markdown-skills/ci-gate-report.md" \
  --max-lint-findings 4 \
  --max-conflict-clusters 4 \
  --max-route-risk-flags 20 \
  --min-route-candidates 2
skilleval diagnostic-pr-review-surface \
  --gate-report "$TMP_ROOT/markdown-skills/ci-gate-report.json" \
  --output "$TMP_ROOT/markdown-skills/pr-review-packet.json" \
  --markdown-output "$TMP_ROOT/markdown-skills/pr-review-packet.md"

skilleval scan "$ROOT/source/mcp-tool-schema/tools.json" \
  --output "$TMP_ROOT/mcp-tool-schema/scan.json"
skilleval lint --index "$TMP_ROOT/mcp-tool-schema/scan.json" \
  --output "$TMP_ROOT/mcp-tool-schema/lint.json"
skilleval inspect --index "$TMP_ROOT/mcp-tool-schema/scan.json" \
  --output "$TMP_ROOT/mcp-tool-schema/inspect.json"
skilleval route "capture browser console diagnostics for a local maintainer page" \
  --index "$TMP_ROOT/mcp-tool-schema/scan.json" \
  --inspect "$TMP_ROOT/mcp-tool-schema/inspect.json" \
  --top-k 2 \
  --output "$TMP_ROOT/mcp-tool-schema/route-browser-console.json"
skilleval route "inspect semantic artifact drift between expected and regenerated reports" \
  --index "$TMP_ROOT/mcp-tool-schema/scan.json" \
  --inspect "$TMP_ROOT/mcp-tool-schema/inspect.json" \
  --top-k 2 \
  --output "$TMP_ROOT/mcp-tool-schema/route-artifact-drift.json"
skilleval diagnostic-dashboard \
  --scan "$TMP_ROOT/mcp-tool-schema/scan.json" \
  --lint "$TMP_ROOT/mcp-tool-schema/lint.json" \
  --inspect "$TMP_ROOT/mcp-tool-schema/inspect.json" \
  --route "$TMP_ROOT/mcp-tool-schema/route-browser-console.json" \
  --route "$TMP_ROOT/mcp-tool-schema/route-artifact-drift.json" \
  --output "$TMP_ROOT/mcp-tool-schema/dashboard.html"
skilleval diagnostic-ci-gate \
  --scan "$TMP_ROOT/mcp-tool-schema/scan.json" \
  --lint "$TMP_ROOT/mcp-tool-schema/lint.json" \
  --inspect "$TMP_ROOT/mcp-tool-schema/inspect.json" \
  --route "$TMP_ROOT/mcp-tool-schema/route-browser-console.json" \
  --route "$TMP_ROOT/mcp-tool-schema/route-artifact-drift.json" \
  --output "$TMP_ROOT/mcp-tool-schema/ci-gate-report.json" \
  --markdown-output "$TMP_ROOT/mcp-tool-schema/ci-gate-report.md" \
  --max-lint-findings 4 \
  --max-conflict-clusters 4 \
  --max-route-risk-flags 20 \
  --min-route-candidates 2
skilleval diagnostic-pr-review-surface \
  --gate-report "$TMP_ROOT/mcp-tool-schema/ci-gate-report.json" \
  --output "$TMP_ROOT/mcp-tool-schema/pr-review-packet.json" \
  --markdown-output "$TMP_ROOT/mcp-tool-schema/pr-review-packet.md"

skilleval diagnostic-artifact-drift-check \
  --expected "$ROOT" \
  --actual "$TMP_ROOT" \
  --output "$TMP_ROOT/drift-report.json" \
  --markdown-output "$TMP_ROOT/drift-report.md"
```

The drift check compares the committed diagnostic artifacts for both tracks and
ignores only approved volatile fields such as `generated_at` and local path
displays.
