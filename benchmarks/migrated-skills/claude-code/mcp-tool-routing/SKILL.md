---
name: MCP Tool Routing
description: Select local MCP tools for files, browser, documents, spreadsheets, or
  app control based on the requested task.
migration_source: claude-code
original_path: hermes/autonomous-ai-agents/claude-code/SKILL.md
migration_date: '2026-05-28'
adapter_kind: claude-code-style-adapter
source_collection: hermes-autonomous-ai-agents
adapter_notes: Claude Code-style adapter derived from the Hermes Claude Code orchestration
  guide; the committed corpus does not copy Anthropic runtime internals.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 39
source_snapshot_label: Hermes Claude Code orchestration guide, MCP integration
---
# MCP Tool Routing

Use when a task depends on choosing the correct local tool or connector. Prefer the most specific available tool, inspect schemas before use, and keep tool actions aligned with user permissions.

## Evidence

- Tool selected and why.
- Inputs or target app checked.
- Output used in the final decision.

## Source Snapshot

Source: Hermes Claude Code orchestration guide, MCP integration

Short excerpt used for provenance, not a full source copy.

````text
Add external tool servers for databases, APIs, and services. `--strict-mcp-config`
ignores all MCP servers except those from `--mcp-config`. Reference MCP resources in
chat with resource URIs. Tool descriptions have a 2KB cap per server for descriptions
and server instructions.
````
