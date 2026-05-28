---
name: Task Tool Delegation
description: Delegate independent investigation or implementation work to specialized
  subagents and review their outputs.
migration_source: claude-code
original_path: hermes/autonomous-ai-agents/claude-code/SKILL.md
migration_date: '2026-05-28'
adapter_kind: claude-code-style-adapter
source_collection: hermes-autonomous-ai-agents
adapter_notes: Claude Code-style adapter derived from the Hermes Claude Code orchestration
  guide; the committed corpus does not copy Anthropic runtime internals.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 38
source_snapshot_label: Hermes Claude Code orchestration guide, custom subagents
---
# Task Tool Delegation

Use when multiple independent workstreams can be delegated. Define each subtask, constrain write scope, collect outputs, verify claims, and integrate findings in the main thread.

## Evidence

- Subtask prompts and boundaries.
- Agent outputs reviewed by the coordinator.
- Integration or follow-up decisions.

## Source Snapshot

Source: Hermes Claude Code orchestration guide, custom subagents

Short excerpt used for provenance, not a full source copy.

````text
Claude Code v2.x can read files, write code, run shell commands, spawn subagents, and
manage git workflows autonomously. Custom subagents can be defined in
`.claude/agents/`, `~/.claude/agents/`, or via the `--agents` CLI flag for
session-specific teams.
````
