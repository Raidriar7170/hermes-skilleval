---
name: Subagent Worker Protocol
description: Execute an assigned implementation task as a Worker with scoped edits,
  validation, and handoff notes.
migration_source: codex
original_path: .codex/AGENTS.md#codex-orchestrator-apply-protocol
migration_date: '2026-05-28'
adapter_kind: codex-orchestrator-adapter
source_collection: codex-global-routing
adapter_notes: Transforms the user's Codex Orchestrator Worker rules into a benchmark
  skill.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 40
source_snapshot_label: global Codex AGENTS.md Codex Orchestrator Apply Protocol
---
# Subagent Worker Protocol

Use when acting as a Worker under an orchestrator. Confirm the assignment, run pre-edit repository checks, modify only owned files, validate the change, and report changed files, commands, and risks.

## Evidence

- Pre-edit repository checks.
- Scoped implementation diff.
- Validation commands and remaining risks.

## Source Snapshot

Source: global Codex AGENTS.md Codex Orchestrator Apply Protocol

Short excerpt used for provenance, not a full source copy.

````text
## Codex Orchestrator Apply Protocol Use this protocol whenever the user asks for Codex
Orchestrator, or when a non-trivial `/opsx:apply` / implementation task needs agent
separation, worktree isolation, or review before merge. Start by outputting: ```markdown
## Task Understanding ## Proposed Subagents ## Worktree /
````
