# Demo Run

This directory contains a committed demo run for Hermes SkillEval.

The demo uses the tiny fixture skill library in `tests/fixtures/skills` against
the 30 built-in benchmark tasks. It is intended to show the CLI/reporting
workflow, not to represent production routing performance.

Regenerate the demo from the repository root:

```bash
skilleval index --skills-path tests/fixtures/skills --output docs/demo/skills.json
skilleval eval --index docs/demo/skills.json --tasks benchmarks/tasks --router hybrid --top-k 5 --output-dir docs/demo/benchmark-hybrid
skilleval report --runs docs/demo/benchmark-hybrid
skilleval compare --index docs/demo/skills.json --tasks benchmarks/tasks --routers keyword,hybrid,embedding --top-k 5 --output-dir docs/demo/router-comparison
```

Artifacts:

- `skills.json`: parsed fixture skill index.
- `benchmark-hybrid/results.jsonl`: per-task routing records and metrics.
- `benchmark-hybrid/report.md`: Markdown summary report.
- `router-comparison/comparison.md`: keyword, hybrid, and embedding router
  comparison table.
- `router-comparison/*/report.md`: per-router Markdown reports.
- `phase3b-real-embedding/comparison.md`: four-way benchmark over the generated
  20-skill library, comparing keyword, hybrid, hashing embedding, and MiniLM
  sentence-transformer routing.
- `phase3b-real-embedding/*/report.md`: per-router reports for the Phase 3B
  real embedding experiment.
