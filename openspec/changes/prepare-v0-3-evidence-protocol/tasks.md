## 1. Protocol and Contributor Surface

- [x] 1.1 Add `AGENTS.md` with Hermes contributor constraints for scoped work,
  historical phase boundaries, evaluation-only scored labels, verifier primacy,
  and artifact retention.
- [x] 1.2 Add `docs/v0.3/action-guide.md` as the PR sequence and repo-local
  execution guide.
- [x] 1.3 Add `docs/v0.3/protocol.md` with frozen research questions,
  preregistration, evidence boundaries, stop conditions, retention policy, and
  PR sequence.

## 2. Placeholder Configs

- [x] 2.1 Add `configs/v0.3/external-skillrouter.yaml` as a SkillRouter
  evaluation template with seed `20260625` and evaluation-only scored-set
  policy.
- [x] 2.2 Add `configs/v0.3/live-agent.yaml` as a live-agent template with
  verifier-first judging and no-credential task constraints.
- [x] 2.3 Add `configs/v0.3/release-gate.yaml` with separate Benchmark
  Validity Gate and Router Promotion Gate placeholders.

## 3. OpenSpec

- [x] 3.1 Create OpenSpec change `prepare-v0-3-evidence-protocol`.
- [x] 3.2 Add proposal, design, tasks, and `v0-3-evidence-protocol` spec delta.
- [x] 3.3 Keep the OpenSpec change limited to protocol/config/documentation.

## 4. Human Brief

- [x] 4.1 Add
  `docs/human-briefs/2026-06-26-prepare-v0-3-evidence-protocol.html`.
- [x] 4.2 Link source docs and state that no v0.3 benchmark/runtime result is
  claimed.

## 5. Validation

- [x] 5.1 Run `python -m pytest -q`.
- [x] 5.2 Run `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`.
- [x] 5.3 Run `PYTHONPATH=src python -m hermes_skilleval.cli release-check --phase17-output-dir docs/demo/phase17-calibrated-release-selector --release-output-dir docs/demo/phase18-ci-release-reproducibility`.
- [x] 5.4 Run `git diff --check`.
- [x] 5.5 Confirm no `src/hermes_skilleval/**`, `tests/**`, historical phase
  docs, or existing release logic were modified.
