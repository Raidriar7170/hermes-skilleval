---
name: Visual Regression Review
description: Compare browser-rendered UI state against expected layout, content, and
  responsive behavior.
migration_source: browser-gui
original_path: openai-bundled/browser/skills/browser/SKILL.md
migration_date: '2026-05-28'
adapter_kind: browser-gui-adapter
source_collection: openai-bundled-browser
adapter_notes: Adapts visual QA instructions into a skill for dashboard and web artifact
  review.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 44
source_snapshot_label: Browser plugin skill, screenshot and page verification workflow
---
# Visual Regression Review

Use when verifying that UI changes look correct. Inspect desktop and mobile viewports, check text overflow, confirm key assets render, and flag layout regressions with precise observations.

## Evidence

- Viewports checked.
- Layout or text issues found.
- Screenshot or browser observation.

## Source Snapshot

Source: Browser plugin skill, screenshot and page verification workflow

Short excerpt used for provenance, not a full source copy.

````text
# Browser Use this skill for browser automation tasks such as inspecting pages,
navigating, testing local apps, clicking, typing, taking screenshots, and reading
visible page state. After setup, select the `iab` browser. Keep browser work in the
background by default. Show the browser when the
````
