## Context

PR-0 froze the v0.3 evidence protocol and explicitly made PR-1 responsible for
the external adapter/provenance layer only. The repository already has
evaluation, release, and provenance code, but those are built around the
self-built Hermes benchmark. PR-1 needs a new external namespace so future
SkillRouter evaluation does not contaminate existing internal metric semantics.

## Goals / Non-Goals

**Goals:**

- Define canonical external `ExternalTask`, `ExternalSkill`, and validation
  records.
- Implement a SkillRouter adapter that can run entirely offline on tiny
  fixtures.
- Stream skill shard records where practical.
- Record file hashes, upstream refs, license notes, adapter mapping, and
  generated-at metadata in a manifest.
- Preserve unknown upstream fields in record metadata.
- Fail closed on malformed files and missing relevant skill IDs.
- Provide a CLI validation command for local data roots.

**Non-Goals:**

- No PR-2 official metric implementation.
- No router inference, embeddings, model loading, training, threshold tuning,
  or candidate promotion.
- No full SkillRouter data download or committed external data.
- No live-agent runtime, Codex runner, SkillsBench adapter, or evidence gate.

## Decisions

1. **Use a new external package.**

   Add `src/hermes_skilleval/external/` so external benchmark data contracts do
   not alter internal `BenchmarkTask`, `Skill`, or metrics behavior.

2. **Accept stable fixture shapes and preserve raw metadata.**

   The adapter supports flexible field aliases for tiny fixture realism, but
   only canonicalizes fields required by PR-1. Unrecognized fields remain in
   `metadata` and the manifest records the adapter mapping.

3. **Separate loading from validation.**

   `load_tasks()` and `iter_skills(tier)` expose canonical records. `validate()`
   performs duplicate, empty query, relevance, tier, and provenance checks and
   returns a structured result that the CLI can write.

4. **Hash files, not paths.**

   The manifest records SHA-256 for input files. Paths are included only as
   local run metadata and do not substitute for hashes.

5. **Keep CLI output simple and deterministic.**

   `skilleval external-validate` writes `manifest.json` and
   `validation.json`. It exits non-zero on invalid evidence and does not write
   metrics.

## Risks / Trade-offs

- [Risk] Upstream SkillRouter field names may differ. -> Mitigation: keep field
  aliases narrow, preserve raw metadata, and require PR-1 fixtures to document
  mapping assumptions.
- [Risk] Loading all skill bodies could be memory-heavy. -> Mitigation: expose
  `iter_skills(tier)` as an iterator and only materialize IDs during validation.
- [Risk] Fixture-only validation can overfit. -> Mitigation: tests include
  malformed, duplicate, missing relevance, missing gold, shard directory, and
  gzip cases.
- [Risk] CLI may be mistaken for scoring. -> Mitigation: command name and
  outputs say validation/provenance only.
