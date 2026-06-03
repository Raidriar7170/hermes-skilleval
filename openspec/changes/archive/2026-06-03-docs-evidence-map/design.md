## Context

Hermes SkillEval now has several evidence surfaces: README recruiter path,
Phase 16-18 release handoff, diagnostic onboarding artifacts, external-style
validation pack, PR-facing CI summary, Human Briefs, and OpenSpec specs. These
surfaces are authoritative in different ways, but reviewers currently need to
know where to look before they can follow the full proof chain.

The evidence map is a documentation navigation layer only. It should point to
source artifacts and explain what each artifact proves, while preserving the
project language in `CONTEXT.md`: developer-facing routing reliability toolkit,
not SaaS, not a leaderboard, and not production-readiness or runtime-router
claims.

## Goals / Non-Goals

**Goals:**

- Add one concise Markdown evidence map under `docs/`.
- Group evidence by reviewer task: project positioning, release gate,
  diagnostic onboarding, external-style validation, CI summary, specs, and
  human-readable phase briefs.
- Link only to committed repository artifacts or stable GitHub workflow pages.
- Add tests that catch missing links, missing categories, and overclaim-prone
  wording.
- Link the map from README and `docs/usage.md` without making it the source of
  truth.

**Non-Goals:**

- No new benchmark, router, diagnostic artifact schema, CI permission, or
  release-gate behavior.
- No live GitHub API PR comments, PR annotations, Marketplace Action, SaaS,
  runtime MCP router, production readiness, or SOTA benchmark claims.
- No attempt to rewrite old phase docs or duplicate their evidence content.

## Decisions

1. **Use Markdown rather than generated HTML.** The map is primarily a stable
   repository index. Markdown keeps diffs simple and makes link tests easy.

2. **Use purpose-based categories.** A reviewer thinks in questions such as
   "what proves the release gate worked?" and "what proves diagnostic CI is
   bounded?" rather than in chronological phase numbers only.

3. **Treat the map as a pointer layer.** Each row should name the artifact, what
   it proves, and what it does not prove. It should not restate full results or
   become a second source of truth.

4. **Protect public wording with tests.** Since this is a packaging phase, tests
   should check both link existence and forbidden phrases.

## Risks / Trade-offs

- **Risk: duplicated evidence drifts from source artifacts** -> keep the map to
  short purpose/proof/boundary rows and link to source artifacts.
- **Risk: navigation becomes marketing copy** -> include explicit boundary
  language and tests for disallowed claims.
- **Risk: broken relative links** -> add project-surface tests that resolve map
  links against the repository root.
