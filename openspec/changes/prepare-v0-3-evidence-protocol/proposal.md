## Why

The existing release evidence chain is strong for the current self-built
Hermes-style benchmark and release gate, but v0.3 needs stricter rules before
external SkillRouter scoring or live-agent execution work begins. Without a
frozen protocol, later PRs could mix official metrics with Hermes diagnostics,
tune on scored labels, treat Phase 10 replay as live-agent proof, or merge
evidence validity with default-router promotion.

This change freezes the evidence protocol before any v0.3 result is produced.

## What Changes

- Add contributor instructions in `AGENTS.md` for scoped PR work, data
  retention, historical phase boundaries, and claim limits.
- Add `docs/v0.3/action-guide.md` as the repo-local PR sequence and execution
  guide.
- Add `docs/v0.3/protocol.md` as the authoritative v0.3 evidence protocol for
  later PR-1 through PR-7 work.
- Add `docs/v0.3/codex-implementation-guide.md` as the detailed Codex guide
  for PR-1 through PR-7 without starting PR-1 implementation.
- Add placeholder configuration templates under `configs/v0.3/` for
  SkillRouter external evaluation, live-agent execution, and release gates.
- Define separate Benchmark Validity Gate statuses:
  `VALID_EVIDENCE`, `INVALID_EVIDENCE`, `REVIEW_REQUIRED`, and field-level
  `UNAVAILABLE`.
- Define separate Router Promotion Gate decisions:
  `KEEP_BASELINE`, `PROMOTE_CANDIDATE`, and `REVIEW_REQUIRED`.
- Freeze seed `20260625`, evaluation-only use of SkillRouter scored labels,
  deterministic verifier primacy for live-agent success, and artifact retention
  constraints.
- Add a concise Chinese Human Brief for review.
- Do not implement benchmark adapters, runtime logic, tests, release logic,
  data ingestion, or router promotion.

## Capabilities

### New Capabilities

- `v0-3-evidence-protocol`: Defines the frozen v0.3 research questions,
  preregistration requirements, evidence boundaries, placeholder config
  contract, retention policy, stop conditions, and PR sequence.

### Modified Capabilities

- None. This PR-0 change intentionally avoids runtime, test, release, and
  historical phase modifications.

## Impact

- Affected docs: `AGENTS.md`, `docs/v0.3/action-guide.md`,
  `docs/v0.3/protocol.md`, `docs/v0.3/codex-implementation-guide.md`, and the
  new Human Brief.
- Affected configs: placeholder-only files under `configs/v0.3/`.
- Affected OpenSpec artifacts:
  `openspec/changes/prepare-v0-3-evidence-protocol/`.
- No `src/hermes_skilleval/**`, `tests/**`, historical phase docs, release
  logic, external data, model weights, embedding cache, raw traces, or
  credentials are in scope.
