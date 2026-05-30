# Hermes SkillEval Release Handoff

## One-line Positioning

Hermes SkillEval is a verification-gated skill routing and self-improvement
harness for Hermes-style agent skills, with reproducible JSONL, Markdown, and
HTML artifacts.

## Evidence Chain

| Phase | Evidence | Artifact |
|---|---|---|
| Phase 9 | Real skill-library migration protocol | `docs/phase9.md` |
| Phase 10 | Agent-in-the-loop migration traces | `docs/phase10.md` |
| Phase 11 | Deterministic evidence judge calibration | `docs/phase11.md` |
| Phase 12 | Offline skill metadata patch ranking | `docs/phase12.md` |
| Phase 13 | Patch simulation regression guard | `docs/phase13.md` |
| Phase 14 | Fine-tuned embedding router path | `docs/phase14.md` |
| Phase 15 | Held-out provenance pack | `docs/phase15.md` |
| Phase 16 | Blind validation and release gate | `docs/phase16.md` |

## Reviewer Entry Points

- Dashboard: `docs/demo/phase16-blind-validation/dashboard.html`
- Blind validation summary: `docs/demo/phase16-blind-validation/regression-summary.json`
- Phase 16 comparison: `docs/demo/phase16-blind-validation/comparison.md`
- Provenance: `docs/demo/phase15-held-out-generalization/provenance.md`
- Release check: `docs/demo/phase16-blind-validation/release-check-summary.json`

## Current Release Reading

Phase 16 is intentionally conservative. It reports `REVIEW_REQUIRED` rather
than a pass because the fine-tuned router preserved Recall@5 but worsened
negative-hit behavior on the blind task pack. This is useful release evidence:
the project can show both positive provenance and a guard that refuses to hide a
blind regression.

## Boundaries

The repository does not commit model checkpoints, private machine details, or
claims beyond self-built Hermes-style evidence.
