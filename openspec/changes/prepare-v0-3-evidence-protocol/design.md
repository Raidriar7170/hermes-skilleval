## Context

Hermes SkillEval already records a conservative default-router release decision
from Phase 16-18: the baseline remains default and the fine-tuned embedding
router is not approved as default. v0.3 is intended to raise evidence quality
through external SkillRouter evaluation and deterministic live-agent execution,
but those later phases carry higher risk than ordinary docs cleanup.

PR-0 therefore creates a protocol first. It is intentionally a non-runtime
change.

## Goals / Non-Goals

**Goals:**

- Freeze v0.3 research questions before external or live-agent results exist.
- Separate official external benchmark metrics from Hermes diagnostics.
- Treat SkillRouter scored labels as evaluation-only.
- Preserve Phase 10 as historical deterministic replay, not live-agent proof.
- Require deterministic verifiers as the primary live-agent success judge.
- Separate evidence validity statuses from router promotion decisions.
- Define data and artifact retention rules before traces or external data are
  produced.
- Provide placeholder configs that later PRs can fill without claiming current
  execution.

**Non-Goals:**

- No external adapter, scorer, runtime, verifier, or live-agent implementation.
- No training, fine-tuning, threshold selection, or model promotion.
- No edits to `src/hermes_skilleval/**`, `tests/**`, historical phase docs, or
  release logic.
- No external full data, model weights, embedding caches, raw traces, or
  credentials in Git.

## Decisions

1. **Make `docs/v0.3/protocol.md` authoritative for v0.3 PR-1 through PR-7.**

   Later implementation PRs should cite the protocol when deciding whether data
   is evaluation-only, how candidate pools are sampled, how live-agent success
   is judged, and which gate owns a decision.

   `docs/v0.3/codex-implementation-guide.md` provides the detailed Codex
   execution guide for those later PRs. It is subordinate to the protocol and
   must not be treated as evidence that PR-1 implementation has started.

2. **Use placeholder configs instead of executable configs in PR-0.**

   The v0.3 config files include `FILL_BEFORE_RUN`, environment placeholders,
   literal `{run_id}` artifact roots, and explicit placeholder schema names.
   This keeps useful structure in Git without implying a benchmark or
   live-agent run exists.

3. **Split evidence status from router promotion.**

   `VALID_EVIDENCE`, `INVALID_EVIDENCE`, and `REVIEW_REQUIRED` answer whether
   the evidence packet can support a question. `KEEP_BASELINE` and
   `PROMOTE_CANDIDATE` answer whether the default router changes. The protocol
   requires the evidence gate before promotion.

4. **Keep Phase 10 historically intact.**

   Phase 10 remains deterministic offline replay. v0.3 live-agent work must use
   a distinct contract such as `live-agent.v1` and deterministic verifiers.

5. **Pin seed `20260625` while allowing unavailable deterministic controls.**

   Candidate sampling and any local randomized choices should use the seed.
   Agent runtimes may not expose full seed control; in that case manifests must
   record `UNAVAILABLE` instead of pretending the run is deterministic.

## Risks / Trade-offs

- [Risk] Placeholder configs may look executable. -> Mitigation: schema names,
  comments, and `FILL_BEFORE_RUN` fields state they are templates only.
- [Risk] Protocol docs could drift from later implementation. -> Mitigation:
  later PRs should update OpenSpec and protocol intentionally when scope changes.
- [Risk] External benchmark and live-agent evidence may conflict. ->
  Mitigation: split Benchmark Validity Gate from Router Promotion Gate and keep
  `REVIEW_REQUIRED` available.
- [Risk] Retention rules could hide useful debug traces. -> Mitigation: raw
  traces may remain under ignored artifact roots; Git stores redacted summaries
  and hashes.
