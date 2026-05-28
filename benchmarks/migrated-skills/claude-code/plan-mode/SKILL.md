---
name: Plan Mode
description: Clarify requirements and produce an implementation plan before changing
  files.
migration_source: claude-code
original_path: hermes/autonomous-ai-agents/claude-code/SKILL.md
migration_date: '2026-05-28'
adapter_kind: claude-code-style-adapter
source_collection: hermes-autonomous-ai-agents
adapter_notes: Claude Code-style adapter derived from the Hermes Claude Code orchestration
  guide; the committed corpus does not copy Anthropic runtime internals.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 30
source_snapshot_label: Hermes Claude Code orchestration guide, plan mode controls
---
# Plan Mode

Use when a task is broad, ambiguous, or risky enough to need a written plan before edits. Gather context, state assumptions, identify files and validation, and wait for approval when required.

## Evidence

- Task understanding.
- Step plan with validation.
- Open questions or approval checkpoint.

## Source Snapshot

Source: Hermes Claude Code orchestration guide, plan mode controls

Short excerpt used for provenance, not a full source copy.

````text
`--permission-mode <mode>` supports `default`, `acceptEdits`, `plan`, `auto`,
`dontAsk`, and `bypassPermissions`. `/plan [description]` enters Plan mode with
auto-start for task planning. Shift+Tab cycles permission modes, including Plan, when
running interactively.
````
