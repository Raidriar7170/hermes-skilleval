## Why

The first Router V2 blind-v2 Agent run terminated during incomplete Round-1 generation after one Generator response exposed 16 candidates, before dataset construction, review, scoring, or evaluation. The remaining exact `codex exec --output-schema` calls were blocked by frozen schemas that the host rejected as invalid strict Structured Outputs schemas. The old run must remain `AGENT_BLIND_V2_PROTOCOL_INVALID / KEEP_BASELINE`; a new, pre-data successor is needed to prove schema and host compatibility without reopening or reusing the exposed 16-candidate protocol.

## What Changes

- Add versioned successor output schemas for Generator, Reviewer A, and Reviewer B without mutating the historical schemas bound to the terminalized run.
- Require every `const` and enum-bearing node to declare an explicit JSON type, and reject unsupported strict-schema composition such as `allOf`, `if`, `then`, and `else`.
- Add one recursive compatibility validator and RED/GREEN tests that traverse every nested schema branch before any host call.
- Add a one-shot, three-role exact-host preflight using the same `codex exec --output-schema` interface, fixed CLI version, fixed model/reasoning configuration, fixed working-directory policy, and frozen schema/prompt hashes.
- Keep all canary prompts and outputs synthetic and pre-data: no old blind prompts, exposed candidates, skill labels, router/model scores, Arm A/C inputs, or evaluation artifacts may enter the calls.
- Emit a sanitized, hash-bound public receipt and a Chinese Human Brief. The only successful terminal state is `PREFLIGHT_READY / KEEP_BASELINE`; every incompatible, drifting, or incomplete path fails closed with `KEEP_BASELINE`.
- Explicitly withhold formal candidate generation, Arm A/C loading, scoring, Commit B, formal evaluation, training, commit, push, PR, merge, release, and archive authority.

## Capabilities

### New Capabilities

- `router-v2-blind-v2-output-schema-preflight`: Versioned strict-output schemas, recursive provider-compatibility validation, and a three-role exact-host canary that can establish only preflight readiness.

### Modified Capabilities

None. The terminalized blind-v2 run and its historical schema/preregistration artifacts remain immutable; this successor adds a new pre-data qualification boundary rather than changing an existing main-spec capability.

## Impact

- Affected implementation: the dedicated Router V2 blind-v2 runner schema definitions, a successor-only preflight entry point, and focused unit/runtime tests.
- New evidence: a successor OpenSpec change, sanitized preflight receipt, and `docs/human-briefs/2026-07-20-harden-router-v2-blind-v2-output-schema-compatibility.html`.
- Frozen interface authority: `/Users/raidriar/.local/bin/codex` resolves to one hash-pinned `0.144.5-aarch64-apple-darwin` regular file; the actual role argv executes that resolved file directly with `codex exec --output-schema`, Generator `gpt-5.6-sol/max`, Reviewer A `gpt-5.6-sol/ultra`, and Reviewer B `gpt-5.6-luna/max`.
- Preserved history: terminal commit `aff4e569e90fa30f5a96b212970ad1331d5c7c6e`, the old 16 exposed candidates, old private outputs, historical schema hashes, and `AGENT_BLIND_V2_PROTOCOL_INVALID / KEEP_BASELINE` remain unchanged and are not inputs to the successor canaries.
- No Router default, training data, checkpoint, metric, README, resume, interview, release, deployment, or remote state is changed.
