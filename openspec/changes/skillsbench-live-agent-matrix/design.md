# Design: SkillsBench Live-Agent Matrix

## Context

PR-6 sits after the fake live-agent runtime and isolated Codex runner. It should
connect SkillsBench-shaped task metadata to the existing runtime contract while
avoiding live benchmark claims. The deliverable is deterministic infrastructure:
adapter validation, task freeze plans, oracle qualification records, global skill
registry construction, three-condition run planning, and trace/report envelopes.

## Goals / Non-Goals

**Goals:**

- Validate SkillsBench-shaped task, skill, and verifier metadata from local
  files without credentials.
- Select only tasks with deterministic verifier metadata, no private
  credentials, and controlled network requirements.
- Require oracle qualification before frozen evaluation selection.
- Build one global skill registry across all selected tasks.
- Enforce routed top-k mounting from stable de-duplicated prediction rankings.
- Freeze plan self-integrity and derived selected-task/registry/matrix fields.
- Generate comparable no-skill, routed-skill, and oracle-skill matrix entries
  with identical prompt hashes and fresh run workspaces.
- Report SkillRouter/SkillsBench overlap decisions separately from independent
  generalization claims.
- Preserve verifier pass/fail as the only task-success source.
- Record trace/report metadata including skill inventory, mounted/read/unknown
  evidence, timeout, process exit, verifier result, and redacted events.
- Separate pilot plans from frozen evaluation plans.

**Non-Goals:**

- No SkillsBench full benchmark run, router promotion, release promotion,
  threshold tuning, hard-negative mining, external SkillRouter scorer/matrix
  edits, or Phase 10 replay changes.

## Decisions

1. **Adapter is local and fail-closed.** The adapter reads local JSON/JSONL
   files and rejects malformed tasks, duplicate IDs, missing deterministic
   verifier metadata, private credential requirements, and uncontrolled network
   requirements.

2. **Freeze plans are explicit and self-checked.** Plans record mode (`pilot` or
   `frozen`), input file SHA-256/size provenance, upstream reference, license
   note, selected task IDs, global skill registry, oracle qualification
   references, and matrix run entries. Plan writing also emits a digest sidecar
   and derived hashes for selected tasks, prompt/verifier fields, registry,
   oracle qualification records, and matrix entries. Frozen plans require
   qualifying oracle records for every selected task.

3. **Conditions reuse PR-4 builders.** Matrix generation uses
   `build_condition`, `prepare_live_agent_workspace`, `AgentRequest`, and
   `execute_live_agent` instead of defining a parallel trace/runtime format.

4. **Routed skills are supplied, not trained.** PR-6 accepts frozen routed
   skill predictions as deterministic input, de-duplicates rankings, and mounts
   only configured routed top-k skills. It does not train routers, tune
   thresholds, infer embeddings, mine negatives, or run model inference.

5. **Overlap evidence is a gate on claims.** Optional SkillRouter task inputs
   are used only to report exact ID overlap, normalized text-hash overlap, and
   declared metadata links. Missing inputs produce `UNAVAILABLE` and set
   `independent_generalization_claim=false`.

6. **Trace reports summarize, not score.** Matrix reports collect process and
   verifier evidence from `live-agent.v1` traces. They do not calculate Hermes
   Negative Hit Rate unless explicit negative labels exist.

## Risks / Trade-offs

- **Risk: task selection becomes benchmark evidence.** Mitigation: separate
  pilot and frozen plan modes and avoid claiming full benchmark results.
- **Risk: router logic leaks into PR-6.** Mitigation: consume routed predictions
  as frozen inputs and keep SkillRouter scorer/matrix untouched.
- **Risk: credentials/network assumptions leak.** Mitigation: adapter rejects
  private credentials and uncontrolled network requirements before selection.
- **Risk: per-task registries overstate routing realism.** Mitigation: build a
  single global registry across all selected tasks.
- **Risk: frozen plan JSON is edited after selection.** Mitigation: verify plan
  digest sidecars, frozen source hashes, and recomputed derived-field hashes
  before matrix execution.

## Migration Plan

PR-6 is additive. Rollback is removing the new SkillsBench adapter/matrix module,
CLI commands, fixtures, tests, OpenSpec change, and Human Brief.
