---
name: Workspace Git Hygiene
description: Inspect branch and status, protect user edits, and avoid destructive
  git commands.
migration_source: codex
original_path: .codex/AGENTS.md#codex-orchestrator-apply-protocol
migration_date: '2026-05-28'
adapter_kind: codex-orchestrator-adapter
source_collection: codex-global-routing
adapter_notes: Captures Codex repository-safety rules as a routable skill for dirty
  worktrees.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 40
source_snapshot_label: global Codex AGENTS.md worktree and git hygiene rules
---
# Workspace Git Hygiene

Use when working in a shared repository or dirty worktree. Check current path, branch, and status, identify unrelated changes, and never revert or overwrite work that was not part of the assignment.

## Evidence

- `pwd`, branch, and status output.
- Explicit note about unrelated changes.
- No destructive git operations.

## Source Snapshot

Source: global Codex AGENTS.md worktree and git hygiene rules

Short excerpt used for provenance, not a full source copy.

````text
## Codex Orchestrator Apply Protocol Use this protocol whenever the user asks for Codex
Orchestrator, or when a non-trivial `/opsx:apply` / implementation task needs agent
separation, worktree isolation, or review before merge. Start by outputting: ```markdown
## Task Understanding ## Proposed Subagents ## Worktree /
````
