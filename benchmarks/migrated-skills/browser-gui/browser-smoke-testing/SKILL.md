---
name: Browser Smoke Testing
description: Open a local web target and verify that the main page renders and core
  controls respond.
migration_source: browser-gui
original_path: openai-bundled/browser/skills/browser/SKILL.md
migration_date: '2026-05-28'
adapter_kind: browser-gui-adapter
source_collection: openai-bundled-browser
adapter_notes: Migrated browser automation checks into deterministic GUI evaluation
  language.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 44
source_snapshot_label: Browser plugin skill, local browser testing workflow
---
# Browser Smoke Testing

Use after frontend or dashboard changes when a browser check is needed. Open the target URL, confirm the page is not blank, exercise the main interaction, and capture any visible error.

## Evidence

- URL or file opened.
- Rendered page check.
- Interaction result or screenshot note.

## Source Snapshot

Source: Browser plugin skill, local browser testing workflow

Short excerpt used for provenance, not a full source copy.

````text
# Browser Use this skill for browser automation tasks such as inspecting pages,
navigating, testing local apps, clicking, typing, taking screenshots, and reading
visible page state. After setup, select the `iab` browser. Keep browser work in the
background by default. Show the browser when the
````
