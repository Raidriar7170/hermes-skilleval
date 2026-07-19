## Why

The preregistered Agent-configuration smoke terminated before candidate generation because the Codex host did not expose provider-returned model metadata, two dummy responses missed the exact canary contract, and one role launched an unplanned nested Agent. No candidate, Commit B, Arm A/C load, model score, attempt marker, or formal evaluation exists, so the research blind remains intact; however, the terminalized protocol cannot be resumed without an explicit, auditable successor contract.

## What Changes

- Add one bounded, pre-data Stage 0 that qualifies the Codex Agent runtime before any new blind-v2 preregistration, candidate generation, model load, or formal Goal.
- **BREAKING** Replace mandatory provider-returned model identity with host invocation-envelope attestation: exact requested model alias, reasoning effort, `fork_context=false`, returned Agent identifier, response hash, and observable invocation lineage are authoritative; unavailable provider-return metadata is disclosed as `INTERFACE_UNAVAILABLE`, never fabricated or treated as proof.
- Carry the same host-envelope authority into every later formal Generator/Reviewer call: nullable provider metadata and positive zero-tool/zero-descendant lineage must survive external metadata, sanitized records, freeze, and evaluation replay; response self-report and retry reclassification remain non-authoritative.
- Require exactly three top-level dummy-text calls for Generator `gpt-5.6-sol/max`, Reviewer A `gpt-5.6-sol/ultra`, and Reviewer B `gpt-5.6-luna/max`, with strict JSON canaries, no tools, no nested Agents, no imported memory, and no retry of any kind.
- Permit one superseding Commit A2 only after Stage 0 passes and only because the terminal evidence proves zero candidate/model/attempt exposure. Commit A2 preserves the failed smoke and supersedes Commit A-agent `50069a124a8d129e11926e78d1bcc2388bc91a22`; it is not attempt-2, `blind-v2-002`, blind-v3, or a replacement dataset.
- Keep the approved Agent-only construction and evaluation contract unchanged: 256 first-round candidates, 128/96 freeze, two role-isolated unanimous reviewers, deterministic contamination and selection, frozen Arm A/C models, unchanged pilot-002 gate, one formal attempt, and `KEEP_BASELINE` on every terminal path.
- Separate later execution into two Goals: a short Stage 0 qualification Goal and, only after Stage 0 plus Commit A2 approval, the full blind-v2 Goal.
- Preserve zero-human claims and same-provider limitations; evidence remains `AGENT_GENERATED / DUAL_AGENT_UNANIMOUS_REVIEWED`, never human-reviewed or statistically independent.
- This proposal phase creates planning artifacts only. It does not call an Agent, generate/read candidate data, load Arm A/C, create Commit A2 or Commit B, write an attempt marker, commit, push, update PR #39, or alter public result surfaces.

## Capabilities

### New Capabilities

- `router-v2-blind-v2-agent-runtime-requalification`: One-time, pre-data Codex-host qualification and auditable Commit A2 authorization for the existing Agent-only Router V2 blind-v2 protocol.

### Modified Capabilities

None. `router-v2-final-blind-v2` remains an unarchived change rather than a main-spec capability; this successor capability changes only its runtime-entry authority and explicitly preserves every data, review, model, metric, gate, attempt, and claim boundary.

## Impact

- Planning scope: this OpenSpec change only during the current proposal phase.
- Later implementation scope, if separately approved: the dedicated blind-v2 runner/CLI tests, Agent smoke receipt schema, protocol, preregistration, and terminal-lineage validation.
- Preserved evidence: Draft PR #39, terminal commit `c208ddde330b408e571df0e315ee3f688bff32e8`, exact-head fixes through `b756a411cc8910999ae1c05d4b5c7a05868302ad`, and the canonical smoke terminal artifact remain immutable history.
- No impact on training inputs, frozen checkpoints, old pilot artifacts, Router defaults, README/resume/interview wording, release state, or deployment state.
- No Human Brief, dashboard, generic qualification framework, third reviewer, adjudicator, training, mining, tuning, merge, tag, release, deploy, or archive is introduced.
