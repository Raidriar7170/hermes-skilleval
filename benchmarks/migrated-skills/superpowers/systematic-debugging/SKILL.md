---
name: Systematic Debugging
description: Reproduce a bug, isolate the cause, and fix it only after evidence identifies
  the failure path.
migration_source: superpowers
original_path: superpowers/systematic-debugging/SKILL.md
migration_date: '2026-05-28'
adapter_notes: Mapped Superpowers debugging discipline into a Hermes SkillEval routing
  skill with explicit reproduction and evidence language.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 42
source_snapshot_label: superpowers/systematic-debugging/SKILL.md
---
# Systematic Debugging

Use when a failure, flaky test, runtime error, or unexpected behavior needs investigation before implementation. Reproduce the symptom, gather observations, form one hypothesis at a time, and verify the root cause before changing code.

## Evidence

- Reproduction command and observed failure.
- Narrowed cause with file or interface evidence.
- Fix validation and remaining risk.

## Source Snapshot

Source: superpowers/systematic-debugging/SKILL.md

Short excerpt used for provenance, not a full source copy.

````text
# Systematic Debugging ## Overview Random fixes waste time and create new bugs. Quick
patches mask underlying issues. **Core principle:** ALWAYS find root cause before
attempting fixes. Symptom fixes are failure. **Violating the letter of this process is
violating the spirit of debugging.** ## The
````
