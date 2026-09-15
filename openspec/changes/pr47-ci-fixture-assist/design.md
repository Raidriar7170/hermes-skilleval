## Context

The active Goal is decision-complete. This change follows C1 → C2 → A1/A2 → A3 → G1 on the existing PR. Prior replay evidence is immutable. CI currently generates reports into frozen directories and ties historical assertions to a changing homepage.

## Goals / Non-Goals

**Goals:** trustworthy current CI, explicit compatible file operations, current dirty-worktree snapshot and gold-free assist, paired bounded checks, real N/F smokes and clean wheel.

**Non-Goals:** research expansion, training, selector promotion, arbitrary repositories, automatic application/commit to user sources, merge or release.

## Decisions

- Generate current release reports outside frozen roots; bind historical tests to recorded historical inputs. Preserve evidence-status and model-promotion distinctions instead of rewriting artifacts.
- Classify overclaim occurrences at clause boundaries, with explicit negative patterns and review-required ambiguity; never use whole-paragraph negation bypass.
- Parse a versioned operation policy for new profiles. Missing version retains legacy root semantics. Validate one captured change description for both preflight disclosure and acceptance.
- Extract callable replay execution primitives, then compose assist without qualification/oracle fields. Snapshot declared tracked current bytes and explicitly included untracked files, reject unsafe paths, create independent Git context and protect original index/branch/content.
- Freeze checks before execution; run baseline and reconstructed candidate through isolated candidate import checking. Report existing/new failures and per-requirement NOT_VERIFIED; overall resolved stays unknown.

## Risks / Trade-offs

- Historical source links may predate the current checkout → inspect recorded manifests and use explicit snapshots with side notes for drift.
- Candidate code is untrusted → retain existing container/transport boundaries and protect controller tests; document weaker self-tests separately.
- Client/backend details are not fully fixed → record actual runtime and unknowns; smoke is engineering evidence only.
- OAuth may not allow workflow edits → retain necessary check changes locally and report the exact publish boundary if existing legal credentials cannot push them.

## Scope and validation

Read scope: current project and task-specific public upstream copies/local runtime. Write scope: CI/release and maintenance code, focused tests, current docs, new configs/product-closeout artifacts and this change. Frozen scope: all pre-existing experimental records, model/skill/task configs and historical evidence. Final scope: complete tracked diff from 10f8aa65 plus explicit new smoke evidence. Use focused checks followed by full lightweight suite/CI, not repeated model matrices or broad hashing loops.
