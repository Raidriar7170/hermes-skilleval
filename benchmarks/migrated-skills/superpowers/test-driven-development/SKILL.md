---
name: Test Driven Development
description: Add or change behavior by confirming a failing test first, then writing
  the smallest passing implementation.
migration_source: superpowers
original_path: superpowers/test-driven-development/SKILL.md
migration_date: '2026-05-28'
adapter_notes: Preserves the red-green-refactor trigger so routers can distinguish
  implementation from debugging-only work.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 45
source_snapshot_label: superpowers/test-driven-development/SKILL.md
---
# Test Driven Development

Use when implementing a feature, bug fix, or refactor that can be described by a test. Start with a focused failing test, confirm the failure reason, implement the minimal code, and rerun the test until it passes.

## Evidence

- Failing test output before the fix.
- Passing targeted test after implementation.
- Notes on any skipped broader validation.

## Source Snapshot

Source: superpowers/test-driven-development/SKILL.md

Short excerpt used for provenance, not a full source copy.

````text
# Test-Driven Development (TDD) ## Overview Write the test first. Watch it fail. Write
minimal code to pass. **Core principle:** If you didn't watch the test fail, you don't
know if it tests the right thing. **Violating the letter of the rules is violating the
````
