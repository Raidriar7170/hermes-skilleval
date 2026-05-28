---
name: Using Git Worktrees
description: Create or use an isolated worktree for feature work so concurrent edits
  do not collide.
migration_source: superpowers
original_path: superpowers/using-git-worktrees/SKILL.md
migration_date: '2026-05-28'
adapter_notes: Kept isolation, branch, and directory checks as routing cues for multi-agent
  implementation.
source_snapshot_kind: short-verbatim-excerpt
source_snapshot_words: 44
source_snapshot_label: superpowers/using-git-worktrees/SKILL.md
---
# Using Git Worktrees

Use when implementation should be isolated from the main checkout or when multiple agents may work at once. Confirm the directory, branch, and git status before editing, then keep changes scoped to the assigned task.

## Evidence

- Worktree path and branch.
- Initial git status.
- Changed files limited to the assignment.

## Source Snapshot

Source: superpowers/using-git-worktrees/SKILL.md

Short excerpt used for provenance, not a full source copy.

````text
# Using Git Worktrees ## Overview Ensure work happens in an isolated workspace. Prefer
your platform's native worktree tools. Fall back to manual git worktrees only when no
native tool is available. **Core principle:** Detect existing isolation first. Then use
native tools. Then fall back
````
