---
name: Evidence Backed Final Response
description: Summarize completed engineering work with changed files, exact validation,
  and known risks.
migration_source: codex
original_path: .codex/AGENTS.md#codex-orchestrator-apply-protocol
migration_date: '2026-05-28'
adapter_kind: codex-orchestrator-adapter
source_collection: codex-global-routing
adapter_notes: Separates final handoff reporting from implementation and testing skills.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 40
source_snapshot_label: global Codex AGENTS.md worker validation and handoff rules
---
# Evidence Backed Final Response

Use at the end of a coding task when the user expects a concise handoff. Report what changed, which commands were run, what passed or failed, and what risk remains without overstating the result.

## Evidence

- Changed file list.
- Exact validation commands.
- Residual risks and limitations.

## Source Snapshot

Source: global Codex AGENTS.md worker validation and handoff rules

Short excerpt used for provenance, not a full source copy.

````text
## Codex Orchestrator Apply Protocol Use this protocol whenever the user asks for Codex
Orchestrator, or when a non-trivial `/opsx:apply` / implementation task needs agent
separation, worktree isolation, or review before merge. Start by outputting: ```markdown
## Task Understanding ## Proposed Subagents ## Worktree /
````
