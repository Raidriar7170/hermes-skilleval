## Context

`docs/demo/v0.2.0-release-decision/` records the current decision as
`NEEDS_REVIEW`, `Published: false`, and `KEEP_BASELINE`. That package is enough
to support a human release review, but it is not itself a release note or a
publish approval. The repository also has Reusable GitHub Action RC evidence
from local and hosted consumer smoke runs, which should be described as RC
support evidence rather than Marketplace publication or release approval.

The remaining review gap is a bounded release-notes draft plus a final human
approval checklist. Both should help the user decide whether to publish
`v0.2.0`; neither should perform or imply publication.

## Goals / Non-Goals

**Goals:**

- Add a `v0.2.0` release-notes draft that describes only committed
  capabilities and links the authoritative evidence chain.
- Add a machine-readable and reviewer-readable final approval checklist with
  current GO/NO-GO status and explicit hard stops.
- Preserve `NEEDS_REVIEW`, `Published: false`, and `KEEP_BASELINE` until the
  user explicitly authorizes a later publish phase.
- Add tests that fail on release notes/checklist drift, missing evidence links,
  missing final-approval boundaries, or positive release/product overclaims.
- Add a concise Chinese Human Brief generated from the same source artifacts.

**Non-Goals:**

- No tag, GitHub Release, Marketplace publication, version bump, deployment, PR,
  PR comment bot, SaaS dashboard, MCP runtime router, or automatic publication.
- No approval of `finetuned-embedding` as the default router.
- No new hosted smoke run or external repository mutation.
- No rewriting historical release evidence.

## Decisions

1. **Use a separate final-approval artifact directory.**  
   `docs/demo/v0.2.0-release-decision/` remains the authoritative decision
   package. The new `docs/demo/v0.2.0-final-approval/` directory will hold the
   final approval checklist and manifest so the release-notes phase does not
   mutate the existing decision into a release action.

2. **Keep release notes as a draft file, not a release record.**  
   `docs/release-notes/v0.2.0.md` will be phrased as release notes prepared for
   human approval. It can describe implemented capabilities, but it must not say
   a `v0.2.0` tag or GitHub Release exists.

3. **Represent the checklist in both JSON and Markdown.**  
   JSON supports tests and drift checks. Markdown supports a reviewer-readable
   GO/NO-GO summary. Both should carry the same decision: `NEEDS_REVIEW` and
   "not published."

4. **Link final approval from public surfaces without changing the public
   release state.**  
   README, usage, evidence map, and release handoff should link the release
   notes/checklist as review artifacts. They must not treat the checklist as
   release approval.

## Risks / Trade-offs

- [Risk] Readers may treat `docs/release-notes/v0.2.0.md` as proof that the
  release exists. -> Mitigation: title and boundary text must say prepared
  release notes / not published, and tests must reject positive release claims.
- [Risk] The checklist could become a second source of truth. -> Mitigation:
  it links and hashes source artifacts, while release-decision and Phase 16-18
  artifacts remain authoritative.
- [Risk] The action RC success could be overread as Marketplace readiness. ->
  Mitigation: release notes and checklist must describe local/hosted smoke as
  RC support evidence only.
