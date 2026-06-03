## Context

Hermes SkillEval is framed as a developer-facing routing reliability toolkit.
Recent phases added a docs evidence map, PR-facing CI summary, diagnostic
artifact drift checks, and external-style validation packs. Those artifacts
prove the project can reject unsafe routing changes and surface diagnostic
signals, but the best failure examples are still spread across release,
diagnostic, and CI docs.

The Failure Gallery is a documentation index for reviewers. It must point to
committed artifacts and keep the canonical evidence in those artifacts. It must
not generate new verdicts, change release-check logic, or imply hosted or
runtime product capabilities.

## Goals / Non-Goals

**Goals:**
- Add `docs/failure-gallery.md` as a reviewer-facing navigation page.
- Group examples from Phase 16/17/18 release-gate evidence, diagnostic
  onboarding artifacts, external-style validation artifacts, and CI summary
  boundaries.
- Link the gallery from public entry points so reviewers can find it quickly.
- Protect the gallery with project-surface tests for link integrity, required
  sections, stable boundary wording, and overclaim avoidance.

**Non-Goals:**
- No new router, runtime MCP router, hosted SaaS surface, Marketplace Action,
  GitHub API PR comment bot, PR annotation system, benchmark leaderboard, or
  release approval mechanism.
- No changes to committed release decisions, CI gates, diagnostic artifact
  schemas, or generated demo artifacts.
- No claim that every possible failure mode is covered.

## Decisions

- **Use Markdown instead of generated JSON or HTML.** Markdown matches the
  existing evidence-map pattern, is easy to review in diffs, and can link
  directly to committed artifacts. A generated gallery would add another source
  of truth without improving current reviewer needs.
- **Group by reviewer question, not phase number alone.** Sections should
  explain why the failure matters: release-blocking regression, diagnostic
  conflict signal, external-shape drift risk, CI boundary/overclaim risk. This
  helps interview and maintainer review without rewriting artifact facts.
- **Test the gallery as a public surface.** Existing project-surface tests
  already guard README, usage docs, evidence-map links, stale test counts, and
  overclaim wording. Extending that file keeps the change narrow.
- **Keep examples bounded.** The gallery can quote committed decisions like
  `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `ALLOW_MERGE`, but must explain those
  as local artifact decisions, not product launch or automatic merge approval.

## Risks / Trade-offs

- [Risk] The gallery could become a second source of truth. → Mitigation:
  require explicit wording that canonical evidence remains in linked artifacts.
- [Risk] Failure examples could sound like benchmark leadership or production
  claims. → Mitigation: reuse the current boundary language and add tests for
  forbidden terms.
- [Risk] Links may drift as artifacts move. → Mitigation: project-surface tests
  resolve local Markdown links.
- [Risk] Older Human Briefs can contain stale test-count snapshots. →
  Mitigation: keep counts synchronized in guarded public docs during the phase.
