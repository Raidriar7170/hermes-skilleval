---
name: Apply Patch Discipline
description: Make small, reviewable file edits with patch-style changes and avoid
  unrelated rewrites.
migration_source: codex
original_path: .codex/AGENTS.md#codex-orchestrator-apply-protocol
migration_date: '2026-05-28'
adapter_kind: codex-orchestrator-adapter
source_collection: codex-global-routing
adapter_notes: Migrated Codex editing constraints into a skill that routes minimal
  manual code changes.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 40
source_snapshot_label: global Codex AGENTS.md minimal-diff and worker ownership rules
---
# Apply Patch Discipline

Use when a coding agent must edit existing files carefully. Read the surrounding code, apply a minimal patch, preserve unrelated user changes, and avoid formatting churn outside the target area.

## Evidence

- Focused diff.
- No unrelated file rewrites.
- Note explaining any unavoidable broad change.

## Source Snapshot

Source: global Codex AGENTS.md minimal-diff and worker ownership rules

Short excerpt used for provenance, not a full source copy.

````text
## Codex Orchestrator Apply Protocol Use this protocol whenever the user asks for Codex
Orchestrator, or when a non-trivial `/opsx:apply` / implementation task needs agent
separation, worktree isolation, or review before merge. Start by outputting: ```markdown
## Task Understanding ## Proposed Subagents ## Worktree /
````
