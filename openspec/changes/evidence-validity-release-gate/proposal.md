## Why

v0.3 now has frozen SkillRouter external artifacts and live-agent artifacts, but there is no single fail-closed packet that says whether the evidence is valid or whether router promotion is allowed. PR-7 adds that consolidation without running new models or changing earlier benchmark/runtime logic.

## What Changes

- Add a unified evidence validator and report writer for v0.3 evidence packets.
- Separate Benchmark Validity Gate status from Router Promotion Gate decision.
- Validate frozen plan hashes, plan digests, derived hashes, scorer/report separation, overlap caveats, prompt-hash equality, oracle qualification, verifier evidence, trace completeness, leakage inventory, and field-level `UNAVAILABLE` markers.
- Summarize external routing metrics, live-agent verifier outcomes, oracle gap, routed-vs-no-skill delta, timeout/process errors, skill-use evidence, and per-task regressions separately.
- Accept the Stage 2 real Codex frozen-plan and execution artifact schema through a conservative adapter contract, while preserving the same verifier-only success source and promotion boundaries.
- Default promotion to `KEEP_BASELINE` and block promotion when validity is `INVALID_EVIDENCE`.
- Add focused tests, CLI wiring, OpenSpec artifacts, and a concise Chinese Human Brief.

## Capabilities

### New Capabilities

- `evidence-validity-release-gate`: Unified v0.3 evidence validity and conservative router-promotion reporting.

### Modified Capabilities

- None.

## Impact

- Affected code: new evidence validator module, scoped CLI command, tests, OpenSpec change, and Human Brief.
- Existing SkillRouter adapter/scorer/matrix, live-agent runtime, Codex runner, Phase 10 replay, and Phase 17/18 release artifacts remain unchanged.
- No new runtime dependency, model execution, training, tuning, live benchmark run, or release promotion is introduced.
