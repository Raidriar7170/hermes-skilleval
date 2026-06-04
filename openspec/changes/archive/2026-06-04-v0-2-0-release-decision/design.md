## Context

`v0.2.0` now has two separate evidence tracks:

- Default-router release gate: Phase 16 reports `REVIEW_REQUIRED`, Phase 17
  records `KEEP_BASELINE`, and Phase 18 reproduces that decision with a
  `PASS` manifest.
- Reusable GitHub Action RC: `action.yml`, local external-consumer smoke, and
  one hosted consumer smoke run show the action gate can produce `ALLOW_MERGE`
  artifacts under bounded RC wording.

The risk is that a single "release decision" label could blur these tracks. The
decision package must distinguish "ready for human release review" from
"published" or "approved as default."

## Goals / Non-Goals

**Goals:**

- Produce a durable `v0.2.0` release decision artifact with a machine-readable
  JSON record and a reviewer-readable Markdown summary.
- Mark the overall package decision as `NEEDS_REVIEW`, not `RELEASED`.
- Preserve `KEEP_BASELINE` as the router/default decision.
- Record action RC smoke support as evidence for review, not publication.
- Link the decision from reviewer-facing docs and Human Briefs.

**Non-Goals:**

- No tag, GitHub Release, Marketplace publication, PR, deployment, release
  notes publication, or version bump.
- No approval of `finetuned-embedding` as the default router.
- No new remote workflow run unless later explicitly requested.
- No change to existing Phase 16/17/18 artifacts beyond validation if
  regeneration is required.

## Decisions

1. **Use `NEEDS_REVIEW` for the package decision.**
   `HOLD` alone would hide the positive action-RC evidence, while `APPROVE` or
   `RELEASE` would overstate the repo state. `NEEDS_REVIEW` captures the actual
   posture: enough evidence for a human release decision, no automatic
   publication.

2. **Keep the router/default decision separate.**
   The decision pack will carry `router_decision: KEEP_BASELINE` and
   `default_router: baseline-minilm`. This prevents action RC success from being
   misread as model/router approval.

3. **Commit both JSON and Markdown.**
   JSON supports tests and future automation; Markdown is better for reviewers.
   Both live under `docs/demo/v0.2.0-release-decision/` alongside an input
   manifest so the evidence chain is inspectable.

4. **Treat local and hosted action smoke as support evidence only.**
   Both smoke packs may be cited as `ALLOW_MERGE` RC gate evidence. The decision
   package must still say they are not release approval, Marketplace
   publication, production readiness, or automatic merge approval.

## Risks / Trade-offs

- **Risk: Version wording implies publication.** Mitigation: tests scan for
  release/tag/Marketplace claims and require explicit `not released` wording.
- **Risk: Router and action decisions get merged.** Mitigation: JSON fields and
  tests keep `release_decision`, `router_decision`, and `action_rc_decision`
  separate.
- **Risk: Existing Phase 18 artifacts drift when release-check reruns.**
  Mitigation: run release-check and confirm no unreviewed artifact drift before
  archive.
- **Risk: The decision becomes another source of truth.** Mitigation: the pack
  points back to Phase 16/17/18 and smoke packs; it summarizes rather than
  replacing them.
