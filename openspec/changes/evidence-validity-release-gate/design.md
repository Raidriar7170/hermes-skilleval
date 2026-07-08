## Context

PR-1 through PR-6 created bounded inputs: SkillRouter adapter/provenance, official scorer parity, frozen external matrix reports, live-agent runtime contracts, Codex runner isolation, and SkillsBench live-agent plans/reports. PR-7 must consume those artifacts as evidence, not rerun benchmark logic or promote routers.

## Goals / Non-Goals

**Goals:**

- Produce one v0.3 evidence packet with separate validity and promotion sections.
- Keep Benchmark Validity Gate statuses limited to `VALID_EVIDENCE`, `INVALID_EVIDENCE`, and `REVIEW_REQUIRED`.
- Keep `UNAVAILABLE` field-level only, with reasons.
- Default Router Promotion Gate to `KEEP_BASELINE`.
- Fail closed on missing/corrupted frozen inputs, mismatched digests, invalid overlap claims, prompt-hash mismatch, incomplete verifier evidence, no-skill leakage, trace incompleteness, or redaction failures.
- Report external routing metrics and live-agent outcomes without merging the namespaces.

**Non-Goals:**

- No model inference, router training, threshold tuning, hard-negative mining, full live-agent benchmark execution, Phase 10 changes, or release promotion.
- No changes to SkillRouter official scorer, external matrix, live-agent runtime, or Codex runner unless a validator integration bug proves a contract issue.

## Decisions

1. **Validator consumes artifacts by path.** The CLI accepts optional external matrix report/plan and live-agent report/plan paths, plus an output path. Missing optional groups become field-level `UNAVAILABLE`; malformed provided artifacts fail closed.

2. **Validity and promotion are independent report sections.** Validity answers whether the evidence can support the preregistered question. Promotion defaults to `KEEP_BASELINE`; invalid evidence blocks promotion even if metrics look favorable.

3. **Checks are explicit records.** Each check emits a stable ID, status, severity, summary, and optional details. Top-level validity is derived from check severities rather than free-form prose.

4. **Earlier PR contracts remain source of truth.** PR-7 validates existing plan/report fields and hashes; it does not recompute official metrics, rerun routers, rerun live agents, or mutate evidence artifacts.

5. **Stage 2 real Codex artifacts are adapted, not reinterpreted.** The gate can consume the frozen Stage 2 pilot plan plus the full real Codex execution artifact by normalizing them into the existing live-agent evidence contract. The adapter preserves deterministic verifier output as the only task-success source, keeps process exit code and LLM judge disabled as success sources, and does not change promotion logic.

6. **Reports are conservative.** Linked-transfer overlap, missing optional diagnostics, and partial evidence are surfaced as caveats or review requirements. Public numeric claims are not generated unless backing artifacts are present.

## Risks / Trade-offs

- **Risk: validator becomes a second scorer.** Mitigation: read and summarize scorer outputs only; never recompute router metrics beyond structural checks.
- **Risk: missing optional artifacts produce a misleading PASS.** Mitigation: optional groups are field-level `UNAVAILABLE`; required provided artifacts still fail closed when corrupt.
- **Risk: promotion status leaks into validity.** Mitigation: separate enums and tests that reject top-level `UNAVAILABLE`.
- **Risk: trace validation grows too broad.** Mitigation: check core schema-like fields and redaction markers without changing runtime trace schema.
