---
name: Form Interaction Flow
description: Drive browser forms and controls through realistic user interactions.
migration_source: browser-gui
original_path: openai-bundled/chrome/skills/chrome/SKILL.md
migration_date: '2026-05-28'
adapter_kind: browser-gui-adapter
source_collection: openai-bundled-chrome
adapter_notes: Represents click, type, select, and submit flows as a browser GUI migration
  skill.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 42
source_snapshot_label: Chrome plugin skill, authenticated browser interaction workflow
---
# Form Interaction Flow

Use when a web task requires entering values, changing controls, submitting forms, or verifying validation messages. Prefer visible labels and stable selectors, then confirm the resulting state.

## Evidence

- Fields or controls touched.
- Submitted values or validation state.
- Resulting page state.

## Source Snapshot

Source: Chrome plugin skill, authenticated browser interaction workflow

Short excerpt used for provenance, not a full source copy.

````text
# Chrome Use this skill when the user mentions `@chrome`. Chrome is the routing
touchpoint for the Codex Chrome Extension: - Use Chrome directly for browser automation
requests and for Chrome setup, detection, repair, or profile checks. - For bare or
general `@chrome` requests, do
````
