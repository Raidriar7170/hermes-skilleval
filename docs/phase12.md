# Phase 12: Offline Skill Metadata Patch Ranking

Phase 12 ranks metadata patch candidates from Phase 11 failed agent-loop judge
records. It focuses on `negative_skill_selected` failures where the router
retrieved gold skills but also selected a task negative skill.

## Scope

The committed run is offline and deterministic. It does not modify source SKILL.md files,
does not write a patched skill index, and does not claim fine-tuning or learned
model training.

## Inputs

`rank-skill-patches` joins four audited inputs:

- Phase 11 routed-skill judge failures
- Phase 9 hybrid route records
- migration task `task.yaml` and `prompt.md` files
- the migrated skills index

## Artifacts

Artifacts live under `docs/demo/phase12-skill-patch-ranking/`:

- `patch-candidates.jsonl`
- `ranked-patches.jsonl`
- `ranking-summary.json`
- `ranked-patches.md`

| Failed Tasks | Candidates | Top Candidate IDs |
|---:|---:|---|
| 3 | 15 | `browser-local-dashboard::browser-smoke-testing::description::append_sentence`, `browser-local-dashboard::visual-regression-review::description::append_sentence`, `claude-command-routing::slash-command-workflow::description::append_sentence`, `sp-debug-red-green::systematic-debugging::description::append_sentence`, `sp-debug-red-green::test-driven-development::description::append_sentence` |

## Reproduce

Use `skilleval rank-skill-patches` with Phase 11 judge failures, Phase 9
routes, migration tasks, and the migrated skill index:

```bash
PYTHONPATH=src python -m hermes_skilleval.cli rank-skill-patches \
  --judge-results docs/demo/phase11-evidence-judge-calibration/judge-agent-loop-hybrid/judge-results.jsonl \
  --routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --output-dir docs/demo/phase12-skill-patch-ranking
```

The command only writes candidate JSONL, summary JSON, and Markdown report
artifacts under the requested output directory.
