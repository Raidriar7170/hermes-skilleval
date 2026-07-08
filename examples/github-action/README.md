# Reusable GitHub Action Example

This directory is a public-safe fixture for trying the Reusable GitHub Action
from a fresh checkout. It includes two small skills, two labeled benchmark
tasks, and a workflow that references the published
`Raidriar7170/hermes-skilleval@v0.3.0` repository Action.

Run the same gate locally:

```bash
python -m pip install -e ".[dev]"
skilleval github-action-gate \
  --skill-path examples/github-action/skills \
  --benchmark-path examples/github-action/benchmark \
  --min-recall-at-k 1.0 \
  --max-negative-hit-rate 0.0 \
  --output-dir runtime/github-action-gate
```

Boundary: this is a reusable repository Action, not a Marketplace-published
Action, not a GitHub API PR comment bot, not a SaaS dashboard, and not a
runtime MCP router. It writes GitHub Actions step summary content and
uploadable artifacts, but it does not post PR comments, write PR annotations,
approve merges automatically, publish releases, or promote
`finetuned-embedding` as the default router.
