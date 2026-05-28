---
name: Accessibility Tree Inspection
description: Inspect accessible names, roles, and tree structure to drive or audit
  browser UI behavior.
migration_source: browser-gui
original_path: openai-bundled/computer-use/skills/computer-use/SKILL.md
migration_date: '2026-05-28'
adapter_kind: browser-gui-adapter
source_collection: openai-bundled-computer-use
adapter_notes: Captures GUI agent reliance on accessibility structure for robust browser
  control.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 44
source_snapshot_label: Computer Use plugin skill, accessibility tree workflow
---
# Accessibility Tree Inspection

Use when visual state is ambiguous or selectors are brittle. Read the accessibility tree, identify controls by role and name, and verify that important UI elements are exposed to assistive tooling.

## Evidence

- Role and name observations.
- Missing or ambiguous accessible elements.
- Interaction target chosen from the tree.

## Source Snapshot

Source: Computer Use plugin skill, accessibility tree workflow

Short excerpt used for provenance, not a full source copy.

````text
# Computer Use Computer Use lets Codex interact with local Mac apps by reading the
screen and performing UI actions. Prefer a dedicated plugin or skill when it can
complete the task; use Computer Use for app interactions that are not exposed through a
more
````
