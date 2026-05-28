# Phase 9: Real Skill-Library Migration Evaluation

Phase 9 adds a small real skill-library migration protocol over four source
families: `superpowers`, `codex`, `claude-code`, and `browser-gui`.

## Corpus

- 16 migrated skills under `benchmarks/migrated-skills`.
- 12 migration tasks under `benchmarks/migration-tasks`.
- Every migrated skill preserves `migration_source`, `original_path`,
  `migration_date`, `adapter_notes`, and source snapshot frontmatter for audit.
  The committed benchmark body is adapted for routing, while the `Source
  Snapshot` section keeps a short provenance excerpt from the originating local
  skill, protocol, or plugin guidance. This avoids publishing full upstream
  instructions while still showing that the corpus came from real workflow
  material.
- The `claude-code` family is a Claude Code-style adapter set derived from the
  Hermes Claude Code orchestration guide (`hermes/autonomous-ai-agents/claude-code/SKILL.md`);
  it is not represented as copied Anthropic runtime text.
- Every migration task includes source coverage, gold skills, negative skills,
  expected evidence, migration dimensions, and the `migration-evaluation`
  robustness tag.

## Offline Evaluation

Committed Phase 9 artifacts use offline deterministic routers:

- `hybrid`
- `embedding-hashing`
- `gated-hashing-selective`

The generated artifacts are stored in
`docs/demo/phase9-real-skill-library-migration/` and include `skills.json`,
router `results.jsonl`, router `report.md`, `comparison.md`,
`failure-analysis.md`, `dashboard.html`, and `migration-summary.json`.

## Migration Failure Taxonomy

- `routing_miss`: the router fails to retrieve one or more gold migrated
  skills.
- `tool_adaptation_failure`: browser or MCP-adjacent skills are confused with
  implementation-only skills.
- `instruction_drift`: process-specific instructions are routed to a generic
  coding skill.
- `evidence_gap`: final reporting or verification evidence is omitted or
  selected too late.

## Metadata Policy

`migration_source`, `expected_evidence`, and `migration_dimensions` are Phase 9
audit metadata in `task.yaml`. The current router result schema does not score
these fields directly; `migration-summary.json` preserves them beside each
task's selected skills, gold-hit status, negative-hit status, and aggregate
router metrics. First-class dimension scoring is reserved for the runtime
adapter follow-up, where task execution evidence can be judged rather than
inferred from routing alone.

## Limitation

Neural MiniLM and cross-encoder migration runs are documented as follow-up work;
committed Phase 9 artifacts use offline deterministic routers.
