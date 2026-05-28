# Skill Library Migration Protocol

This protocol defines the next small, reproducible experiment for testing
Hermes SkillEval against real skill-library migration work. It is intentionally
small enough to run by hand or in CI-like local validation before scaling to a
larger corpus.

## Goal

Measure whether Hermes SkillEval can route, compare, and diagnose skills adapted
from real agent ecosystems instead of only evaluating generated Hermes-style
skills.

## Skill Sources

The first migration set should include four families:

| Source | Initial sample | Purpose |
|---|---:|---|
| Superpowers skills | 4-6 skills | Process-heavy workflows such as TDD, debugging, verification, and planning |
| Codex skills | 4-6 skills | Codex-native workflows with local repo, browser, document, spreadsheet, or presentation assumptions |
| Claude Code style skills | 4-6 skills | Adapter skills written around Claude Code conventions, command names, and tool affordances, with provenance pointing to the actual guide used |
| browser-use-vision / gui-agent-benchmark skills | 4-6 skills | GUI-agent and browser-automation workflows with visual evidence requirements |

Each imported skill should preserve source identity plus a public-safe source
snapshot and a small migration metadata block that records source, original
path, migration date, and any adapter notes. Full local source text can be kept
outside the public corpus when licensing or publication risk is unclear.
If a family is an ecosystem-style adapter rather than a direct upstream copy,
its metadata must say so explicitly and point `original_path` to the real guide
or source document used for the adaptation.

## Task Set

Start with a 10-20 task migration test set. The tasks should be held out from
the generated benchmark and should each require one migrated skill family:

| Task family | Example task shape | Count |
|---|---|---:|
| Process discipline | Fix a bug with TDD, then verify before completion | 3-5 |
| Repo operations | Modify a small project while preserving local conventions | 2-4 |
| Browser or GUI evidence | Inspect a local page, capture evidence, and summarize failure modes | 2-4 |
| Artifact creation | Produce or validate a document, spreadsheet, presentation, or report artifact | 2-4 |
| Cross-ecosystem ambiguity | Prompt names two ecosystems or tool vocabularies and expects the right adapter | 1-3 |

Every task should include `gold_skills`, tempting `negative_skills`, category,
difficulty, and an expected evidence artifact.

## Evaluation Dimensions

Evaluate every run with both routing metrics and migration-specific checks:

| Dimension | What it measures |
|---|---|
| task success | Whether the selected skill enables the requested task to complete |
| tool adaptation | Whether ecosystem-specific tool names or workflows are mapped correctly |
| instruction fidelity | Whether hard gates, verification requirements, and evidence rules are preserved |
| failure recoverability | Whether the agent can identify and recover from a wrong or incomplete skill choice |
| evidence completeness | Whether the run preserves commands, screenshots, summaries, and artifact paths needed for review |

For the first offline Phase 9 round, these dimensions are preserved as audit
metadata rather than scored as execution metrics. The committed router records
measure routing only; `migration-summary.json` carries each task's expected
evidence and migration dimensions beside selected skills, gold hits, and
negative hits. First-class dimension scoring belongs in the later runtime
adapter experiment, where the harness can inspect actual execution traces.

## Run Matrix

Run the same 10-20 tasks against at least three router configurations:

| Router | Role |
|---|---|
| hybrid | deterministic baseline for migrated vocabulary |
| contrastive gated MiniLM | selective safety baseline |
| cross-encoder calibrated strict | learned reranking with conservative acceptance |

If optional neural dependencies are unavailable, keep the hybrid-only output and
record the missing backend as an environment limitation rather than deleting the
task set.

The committed offline Phase 9 artifact uses `hybrid`, `embedding-hashing`, and
`gated-hashing-selective` as a Mac-local substitution for the neural rows above.
MiniLM and calibrated cross-encoder migration runs remain follow-up work.

## Required Artifacts

Each migration round should produce:

- `summary JSON` with per-task route, selected skill, gold/negative hit, and
  the migration dimensions carried as audit metadata.
- `failure taxonomy` separating routing misses, tool-adapter failures,
  instruction drift, evidence gaps, and irrecoverable environment failures.
- `dashboard comparison` generated through `skilleval dashboard` so migrated
  skill behavior can be inspected beside existing Phase 7B runs.
- Per-run `results.jsonl` and `report.md` files that match the existing
  `docs/demo/**` artifact pattern.

## Acceptance Gate

The first migration experiment is successful when:

- at least 10 tasks run end to end,
- every task has a gold skill and at least one negative skill,
- all run artifacts are committed or deliberately excluded with a documented
  reason,
- dashboard provenance names the migrated skill source and run folders,
- failures are classified by the migration failure taxonomy and retain task
  migration dimensions as audit context, not only by aggregate metric.
