# Hosted Consumer Action Smoke

This pack records one GitHub-hosted consumer smoke run for the Reusable GitHub
Action RC. The consumer repository is
[`Raidriar7170/hermes-skilleval-action-consumer-smoke`](https://github.com/Raidriar7170/hermes-skilleval-action-consumer-smoke);
its workflow calls `Raidriar7170/hermes-skilleval@main` from a hosted
`ubuntu-latest` runner with consumer-owned `skills`, `benchmark`, and
`skilleval-output` paths.

The hosted run completed successfully:

- Run URL: <https://github.com/Raidriar7170/hermes-skilleval-action-consumer-smoke/actions/runs/26946490131>
- Workflow: `SkillEval hosted consumer smoke`
- Event: `workflow_dispatch`
- Producer action ref: `Raidriar7170/hermes-skilleval@main`
- Consumer commit: `f7d931f920eee6fa639876c7c038892183e72938`
- Uploaded artifact: `skilleval-action-artifacts`

Boundary: this is one GitHub-hosted consumer smoke run and Reusable GitHub
Action RC evidence, not a Marketplace Action release, not GitHub API PR
comments, not PR annotations, not SaaS, not a runtime MCP router, not a SOTA
claim, not benchmark status, not production readiness, not release approval,
not automatic merge approval, and not a v0.2.0 release.

## Evidence Files

| Artifact | Helps verify | Limit |
|---|---|---|
| [`workflow.yml`](workflow.yml) | Consumer workflow source: manual dispatch, read-only permissions, Python 3.11 setup, and `uses: Raidriar7170/hermes-skilleval@main`. | It is smoke workflow source, not a release workflow. |
| [`run-metadata.json`](run-metadata.json) | Hosted run URL, run id, conclusion, action ref, commit, and artifact names. | Metadata is a captured run record, not ongoing monitoring. |
| [`input-manifest.json`](input-manifest.json) | Fixture source, skill ids, task ids, and SHA-256 hashes for consumer inputs. | It proves fixture provenance, not benchmark generality. |
| [`output/gate-report.json`](output/gate-report.json) | Machine-readable gate decision, thresholds, and metrics from the hosted artifact. | It is hosted smoke evidence only. |
| [`output/gate-report.md`](output/gate-report.md) | Reviewer-readable gate report from the hosted artifact. | The generic gate boundary still says the gate report alone is not hosted proof; hosted provenance is in `run-metadata.json`. |
| [`output/ci-summary.json`](output/ci-summary.json) | Machine-readable CI summary decision from the hosted artifact. | It does not post GitHub API comments. |
| [`output/ci-summary.md`](output/ci-summary.md) | Step-summary style Markdown from the hosted artifact. | It is not a PR annotation. |
| [`output/results.jsonl`](output/results.jsonl) | Per-task route output from the hosted artifact. | It is not benchmark status. |

## Reproduction Shape

The hosted consumer workflow uses this shape:

```yaml
name: SkillEval hosted consumer smoke

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  skilleval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - uses: Raidriar7170/hermes-skilleval@main
        with:
          skill-path: skills
          benchmark-path: benchmark
          min-recall-at-k: "1.0"
          max-negative-hit-rate: "0.0"
          output-dir: skilleval-output
          upload-artifacts: "true"
```
