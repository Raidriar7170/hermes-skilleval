## Context

The repository already has a strong evaluation backbone: `Skill` models,
`SKILL.md` parsing, skill indexes, benchmark tasks, routers, JSONL results,
reports, dashboards, blind validation, and release checks. The missing product
surface is a zero-label onboarding path where a Skill Library Maintainer can
point the CLI at a real skill/tool library and get useful diagnostic outputs
before writing benchmark labels.

The change should preserve the existing benchmark and release-gate workflow. It
adds a product-facing diagnostic layer over real skill sources and stable JSON
artifacts.

## Goals / Non-Goals

**Goals:**

- Support first-version skill source shapes: Markdown skill folders and MCP tool
  schema files.
- Add a Diagnostic CLI Front Door: `scan`, `lint`, `route`, and `inspect`.
- Produce stable JSON artifacts for scan, lint, route, and inspect workflows.
- Make unlabeled routing useful by returning top-k candidates with route
  evidence and route risk flags.
- Surface explainable conflict risk clusters for maintainers.
- Generate a static diagnostic dashboard from diagnostic artifacts.

**Non-Goals:**

- No runtime MCP server or agent plugin in P0.
- No GitHub Action, PR annotations, or merge blocking in P0.
- No large public benchmark, leaderboard, or SOTA claim in P0.
- No SaaS-like dashboard or hosted UI in P0.
- No general Markdown style linting.

## Decisions

### Decision: Add a diagnostic layer instead of replacing benchmark commands

Keep `index`, `eval`, `compare`, `dashboard`, and release commands as deeper
evaluation machinery. Add `scan`, `lint`, `route`, and `inspect` as the
first-time maintainer workflow.

Alternatives considered:

- Rename existing commands: rejected because it would blur existing benchmark
  behavior and risk regressions in committed phase artifacts.
- Build only documentation around existing commands: rejected because users need
  first-class unlabeled diagnostic outputs, not just a new README path.

### Decision: Normalize sources into source-annotated diagnostic records

Use the existing `Skill` fields as the common routing shape, but add diagnostic
source metadata in the scan artifact: source type, source path, parsed file path,
parser warnings, and extracted routing cues. This keeps routers compatible while
making provenance explicit for real user libraries.

Alternatives considered:

- Add platform-specific models for each assistant brand: rejected because the
  first version should be scoped by stable input shape, not by path-brand
  promises.
- Reuse the current skill index JSON unchanged: rejected because it lacks source
  provenance and warning fields needed by diagnostics and future CI comparison.

### Decision: Treat unlabeled route as a diagnostic query, not a benchmark task

`route` should accept a free-form query and produce a diagnostic route artifact
with top-k candidates, scores, route evidence, and risk flags. Internally it may
reuse existing router scoring helpers, but the output must not require
gold/negative labels.

Alternatives considered:

- Force users to create benchmark task YAML first: rejected because P0 must be
  useful without labels.
- Return only a sorted score list: rejected because maintainers need auditable
  evidence and ambiguity warnings.

### Decision: Use explainable heuristics for lint and conflict clusters

P0 diagnostics should rely on visible signals: missing or weak descriptions,
generic trigger terms, absent use/do-not-use boundaries, token overlap, category
proximity, and repeated co-appearance in route candidates. Heuristics should
produce risk findings, not definitive conflict verdicts.

Alternatives considered:

- Use an LLM judge as the first conflict engine: rejected because it adds API
  dependency, opacity, and cost before the local workflow is proven.
- Use a heavy embedding model by default: rejected because P0 should remain
  offline-first and quick to run.

### Decision: Separate diagnostic dashboard from router-run dashboard

Keep the existing router-run dashboard for benchmark JSONL results. Add a
separate static diagnostic dashboard renderer for source summaries, lint
findings, route examples, and conflict risk clusters.

Alternatives considered:

- Extend the existing dashboard schema to accept diagnostic artifacts: rejected
  because benchmark results and diagnostic artifacts have different semantics.

## Risks / Trade-offs

- [Risk] Diagnostic heuristics may over-warn on broad skills. -> Mitigation:
  label outputs as risk findings, include evidence terms, and avoid definitive
  merge/delete recommendations.
- [Risk] MCP schema shapes vary across projects. -> Mitigation: start with a
  conservative parser that extracts stable tool names, descriptions, and input
  schema summaries, with warnings for unsupported shapes.
- [Risk] New diagnostic indexes may duplicate existing skill index concepts. ->
  Mitigation: keep `Skill` as the common routing shape and make diagnostic
  metadata additive in artifacts.
- [Risk] The CLI front door could drift from benchmark commands. -> Mitigation:
  keep command responsibilities explicit and document how diagnostic artifacts
  feed later labeled regression workflows.

## Migration Plan

Add the diagnostic layer without changing existing committed benchmark artifacts
or release decisions. Existing commands and docs remain valid. New diagnostic
commands can be documented as the recommended first-time user path while deeper
evaluation commands remain available.

## Open Questions

- Should diagnostic artifacts live under `runs/diagnostic/latest` by default, or
  should each command require an explicit output path?
- Should `route` default to the hybrid router, hashing embedding router, or an
  explicit user-provided router choice?
