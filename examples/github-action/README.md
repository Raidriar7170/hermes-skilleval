# Reusable GitHub Action RC Example

This directory is a public-safe fixture for trying the Reusable GitHub Action RC
from a fresh checkout. It includes two small skills, two labeled benchmark
tasks, and a workflow that references `Raidriar7170/hermes-skilleval@main`
rather than an unpublished version tag.

Run the same gate locally:

```bash
python -m pip install -e "."
skilleval github-action-gate \
  --skill-path examples/github-action/skills \
  --benchmark-path examples/github-action/benchmark \
  --min-recall-at-k 1.0 \
  --max-negative-hit-rate 0.0 \
  --output-dir runtime/github-action-gate
```

Boundary: this is a Reusable GitHub Action RC, not a Marketplace Action release,
not GitHub API PR comments, not PR annotations, not SaaS, not a runtime MCP
router, not a SOTA claim, not benchmark status, not production readiness, not
release approval, not automatic merge approval, and not a v0.2.0 release.
