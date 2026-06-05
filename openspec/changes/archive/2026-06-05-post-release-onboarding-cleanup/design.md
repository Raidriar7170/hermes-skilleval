## Context

`v0.2.0` is now a published GitHub Release, but several current public surfaces
still describe the repository as if the release is pending: package metadata is
`0.1.0`, the reusable Action is labeled RC, examples point to `@main`, and the
README front door emphasizes reviewer evidence before external-user
onboarding.

The cleanup spans metadata, README structure, usage docs, Action examples,
evidence navigation, and tests. The important distinction is temporal:
pre-publish review artifacts should remain truthful historical evidence, while
current public docs should not present pre-publish state as the current release
state.

## Goals / Non-Goals

**Goals:**

- Make the GitHub homepage read as a developer tool first and an evidence pack
  second.
- Align version metadata, release notes, docs, examples, and Action metadata
  with published `v0.2.0`.
- Provide copy/paste local and GitHub Action onboarding for external users.
- Keep only 3-5 high-signal evidence links in the README and move longer
  phase-history navigation to docs.
- Add tests that catch stale `@main`, RC, "not a v0.2.0 release", and
  forbidden-product-claim wording in current public surfaces.

**Non-Goals:**

- No MCP runtime router, router experiment, or router promotion.
- No Marketplace Action publication or claim.
- No GitHub API PR comment bot, PR annotations, SaaS dashboard, public
  leaderboard, SOTA benchmark claim, automatic release publication, or new
  fine-tuning promotion.
- No external demo repository creation in this phase.
- No rewriting historical evidence artifacts to hide their original
  pre-release state.

## Decisions

1. **Treat README as the developer front door.**

   The README first screen should answer "what problem does this solve, how do
   I run it, and what does it output?" before long phase history. Evidence links
   stay present but compact, with `docs/evidence-map.md` and
   `docs/release-handoff.md` carrying detailed navigation.

   Alternative considered: keep the recruiter/evidence-first README and only
   patch stale strings. That would fix correctness but leave the project
   feeling like an internal release dossier rather than a reusable tool.

2. **Pin current Action examples to `@v0.2.0`.**

   Current user-facing reusable Action examples should use
   `Raidriar7170/hermes-skilleval@v0.2.0`. Historical smoke artifacts may retain
   captured refs such as `@main` when they are explicitly described as
   historical evidence, not current onboarding.

   Alternative considered: recommend a commit SHA. That is precise, but the
   published release tag is the clearer external onboarding path after
   `v0.2.0`.

3. **Update RC language only on current public surfaces.**

   Root `action.yml`, README, examples, docs/usage, release notes, and evidence
   map should describe the released capability as "Reusable GitHub Action".
   Archived OpenSpec changes, old Human Briefs, and captured smoke artifacts can
   preserve RC wording if clearly historical.

   Alternative considered: rename the OpenSpec capability directory from
   `reusable-github-action-rc` to `reusable-github-action`. That is cleaner
   semantically but would create unnecessary spec churn. This change updates
   the requirements and user-facing naming without forcing a capability rename.

4. **Use tests as public-surface guardrails.**

   Existing project-surface tests are the right place to enforce current README
   sections, version metadata, Action refs, forbidden claims, and link
   integrity. Fresh-clone smoke coverage should use repository-relative paths
   and temporary directories only.

   Alternative considered: rely on manual grep during release closeout. That is
   too easy to regress as docs evolve.

## Risks / Trade-offs

- [Risk] Updating "not a v0.2.0 release" too broadly could corrupt historical
  pre-publish artifacts. -> Mitigation: restrict cleanup assertions to current
  public surfaces and label historical artifacts as historical when linked.
- [Risk] Pinning docs to `@v0.2.0` could conflict with local smoke evidence
  captured against `@main`. -> Mitigation: distinguish current copy/paste usage
  from captured historical smoke metadata.
- [Risk] README simplification could remove useful reviewer context. ->
  Mitigation: keep 3-5 high-signal links and move the long evidence chain to
  `docs/evidence-map.md` / `docs/release-handoff.md`.
- [Risk] Boundary wording may become noisy. -> Mitigation: standardize on one
  concise public boundary sentence and keep expanded boundaries in docs.
- [Risk] A patch release might be needed because metadata changes after
  `v0.2.0` publication. -> Mitigation: document a `v0.2.1` patch candidate
  note if warranted, but do not tag or publish automatically.
