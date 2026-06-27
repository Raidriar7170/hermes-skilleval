# Hermes SkillEval v0.3 Action Guide

Date: 2026-06-26

This guide freezes the v0.3 working sequence for future PRs. PR-0 only adds
protocol, OpenSpec, contribution constraints, and placeholder configuration.
It does not implement external benchmark adapters, live-agent runtime,
scoring, training, release promotion, or new benchmark results.

## Execution Summary

Hermes SkillEval already has an offline skill-routing evaluation and release
gate chain. v0.3 is a stricter evidence phase with two future workstreams:

1. External SkillRouter evaluation with frozen routers and evaluation-only
   scored labels.
2. Live-agent execution evaluation using deterministic verifiers on selected
   no-credential tasks.

The phase principle is: freeze evidence rules first, then run experiments.
Later PRs must cite `docs/v0.3/protocol.md` instead of inventing new standards
after seeing results.

## Current PR Sequence

| PR | Scope | Runtime changes |
|---|---|---:|
| PR-0 | Protocol, OpenSpec, contributor constraints, placeholder configs | No |
| PR-1 | External benchmark adapter and provenance manifest | Yes |
| PR-2 | Official metric reproduction and scorer parity checks | Yes |
| PR-3 | Frozen zero-shot routing matrix, strict generalization, field ablations, candidate scaling, bootstrap, and overlap reporting | Yes |
| PR-4 | Live-agent runtime abstraction, fake runner, workspace isolation, verifier contract, and `live-agent.v1` trace schema | Yes |
| PR-5 | Codex CLI runner, isolated execution, skill mounting, JSONL trace parsing, and redaction | Yes |
| PR-6 | SkillsBench adapter, task freezing, global E2E skill registry, and three-condition experiment matrix | Yes |
| PR-7 | Unified evidence validator, Benchmark Validity Gate, optional Router Promotion Gate, and decision report | Yes |

## PR-0 Deliverables

- `AGENTS.md`
- `docs/v0.3/action-guide.md`
- `docs/v0.3/protocol.md`
- `configs/v0.3/external-skillrouter.yaml`
- `configs/v0.3/live-agent.yaml`
- `configs/v0.3/release-gate.yaml`
- OpenSpec change `prepare-v0-3-evidence-protocol`
- `docs/v0.3/codex-implementation-guide.md`
- Chinese Human Brief at
  `docs/human-briefs/2026-06-26-prepare-v0-3-evidence-protocol.html`

## Research Questions

- RQ1: Do frozen Hermes routers preserve routing quality on external skill
  libraries and large candidate pools that were not used for training?
- RQ2: Does full skill body text improve routing compared with name or
  metadata-only views?
- RQ3: Do routed skills improve deterministic live-agent task pass rates
  compared with no-skill execution?
- RQ4: Do routing metric changes transfer to task success, or is there a
  route-to-execution gap?
- RQ5: Can the release gate keep the safer baseline when external routing
  metrics and live execution evidence conflict?

## Evidence Boundaries

- SkillRouter scored labels are evaluation-only. Do not train, tune, select
  thresholds, or choose variants on final scored labels.
- External benchmark metrics and Hermes diagnostics must be reported separately.
- Do not compute Hermes negative-hit metrics for external data unless explicit
  negative labels exist.
- Phase 10 remains historical deterministic replay, not live-agent evidence.
- Live-agent success is judged by deterministic verifiers. Other review signals
  are diagnostics only.
- Agent configuration and task selection must be frozen before final live-agent
  runs. Agent randomness may not be fully controlled; record what can be
  pinned and mark the rest as `UNAVAILABLE`.
- Default router promotion is not automatic. Evidence validity and router
  promotion are separate gates.

## Frozen Defaults for Later PRs

- Random seed: `20260625`.
- Minimum router comparison: `baseline-minilm` and `finetuned-embedding`.
- Candidate router status: diagnostic candidate until a promotion gate says
  otherwise.
- External candidate tiers: Easy and Hard when available from SkillRouter.
- Live-agent conditions: `no-skill`, `routed-skill`, `oracle-skill`.
- Planned live-agent repetitions: 3 per condition per selected task.
- Planned live-agent timeout placeholder: 1200 seconds until final
  preregistration overrides it.
- Artifact root pattern: `artifacts/v0.3/{run_id}/`.
- Codex implementation details for PR-1 through PR-7 are in
  `docs/v0.3/codex-implementation-guide.md`.

## Data and Artifact Rules

Commit only small, reviewable, redacted artifacts: summaries, manifests,
hashes, small fixtures, documentation, and reproducible commands. Do not commit
external full data, model weights, embedding caches, credentials, raw traces,
unredacted logs, or private machine details.

## Required Validation for PR-0

```bash
python -m pytest -q
OPENSPEC_TELEMETRY=0 openspec validate --all --strict
PYTHONPATH=src python -m hermes_skilleval.cli release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
git diff --check
```

PR-0 success means the protocol is reviewable and validation remains green. It
does not mean v0.3 benchmark or live-agent evidence exists.
