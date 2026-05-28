---
name: Slash Command Workflow
description: Follow explicit slash-command workflows for proposal, apply, review,
  or archive steps.
migration_source: claude-code
original_path: hermes/autonomous-ai-agents/claude-code/SKILL.md
migration_date: '2026-05-28'
adapter_kind: claude-code-style-adapter
source_collection: hermes-autonomous-ai-agents
adapter_notes: Claude Code-style adapter derived from the Hermes Claude Code orchestration
  guide; the committed corpus does not copy Anthropic runtime internals.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 36
source_snapshot_label: Hermes Claude Code orchestration guide, slash commands
---
# Slash Command Workflow

Use when the user invokes a named command workflow. Resolve the command, follow its required sequence, avoid parallel process documents, and report the command-specific artifacts produced.

## Evidence

- Command name and phase.
- Required artifacts or checks.
- Next command in the lifecycle.

## Source Snapshot

Source: Hermes Claude Code orchestration guide, slash commands

Short excerpt used for provenance, not a full source copy.

````text
Interactive mode gives you a full conversational REPL where you can send follow-up
prompts, use slash commands, and watch Claude work in real time. Slash commands include
`/review`, `/plan [description]`, `/model [model]`, `/permissions`, `/agents`, and
`/mcp`.
````
