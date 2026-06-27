# Hermes SkillEval Contributor Instructions

- Read `CONTEXT.md`, `README.md`, the relevant `docs/v0.3/` protocol, and the
  nearest existing implementation or docs before editing.
- Keep one PR scope at a time. Do not bundle unrelated refactors or release
  work into protocol, benchmark, runtime, or documentation changes.
- Preserve existing CLI behavior, release gates, tests, and historical Phase
  10-18 artifacts unless a later approved change explicitly updates them.
- Do not modify `src/hermes_skilleval/**`, `tests/**`, historical phase docs, or
  release logic for v0.3 PR-0.
- Treat the SkillRouter scored set as evaluation-only: no training, tuning,
  threshold selection, variant selection, or hard-negative mining on final
  scored labels.
- Preserve Phase 10 as deterministic offline replay evidence. Do not describe
  it as live-agent evidence.
- Use deterministic verifiers as the primary live-agent success judge. LLM or
  human review may diagnose failures but must not replace verifier outcomes.
- Keep `VALID_EVIDENCE`, `INVALID_EVIDENCE`, and `REVIEW_REQUIRED` separate
  from router promotion decisions such as `KEEP_BASELINE` and
  `PROMOTE_CANDIDATE`.
- Never commit external full datasets, model checkpoints, embedding caches,
  credentials, raw auth files, private host details, or unsanitized agent traces.
- Mark unavailable evidence as `UNAVAILABLE`; do not fabricate source,
  temporal, cost, token, activation, or verifier fields.
- Do not claim a benchmark result, live-agent result, release decision, or
  public-readiness posture that was not produced by a committed command and
  recorded artifact.
