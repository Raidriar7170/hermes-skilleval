## Context

The active Agent-only blind-v2 change froze three configurations: Generator `gpt-5.6-sol/max`, Reviewer A `gpt-5.6-sol/ultra`, and Reviewer B `gpt-5.6-luna/max`. Its pre-generation smoke terminalized at `AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE` because provider-returned model metadata was unavailable, two responses did not exactly match the expected dummy text, and Reviewer B launched one unplanned nested Agent. The canonical terminal evidence binds Commit A-agent `50069a124a8d129e11926e78d1bcc2388bc91a22` and proves zero candidates, no Commit B, no Arm A/C load, no model score, no attempt marker, and no formal evaluation.

The current runtime entry contract is therefore unsatisfiable as written: the Codex host accepts requested model and reasoning overrides and returns an Agent identifier, but the invocation result does not guarantee provider-returned resolved-model metadata. Trusting an Agent to self-report its own configuration would not repair that evidence gap. Directly continuing Task 11 would also violate the recorded terminal state.

This change defines a one-time administrative successor before any blind data or evaluated model exposure. It does not reopen a consumed attempt or authorize candidate generation by itself. The user has authorized only proposal artifacts in the current phase and explicitly forbids Agent calls, candidate generation, commits, and pushes.

## Goals / Non-Goals

**Goals:**

- Prove that the Codex host can invoke the three approved configuration requests with a minimal, machine-checkable, tool-free canary before another preregistration is created.
- Replace impossible provider-return metadata as the sole identity gate with explicit host-envelope evidence while preserving honest disclosure of what the interface cannot attest.
- Preserve the failed smoke as immutable audit history and allow a superseding Commit A2 only under the exact zero-exposure invariant.
- Keep all dataset, review, contamination, model, metric, gate, attempt, and claim boundaries byte- or semantic-equivalent to the approved 128/96 protocol.
- Split the short runtime qualification from the long candidate/review/evaluation Goal so infrastructure incompatibility terminates early.

**Non-Goals:**

- Calling any Agent, reading or generating any candidate, loading Arm A/C, scoring, creating Commit A2/Commit B, writing an attempt marker, committing, pushing, or changing PR #39 during this proposal phase.
- Relaxing aliases, reasoning efforts, role isolation, unanimous acceptance, contamination thresholds, quotas, deterministic selection, model/checkpoint authority, metrics, gate, seeds, or one-attempt semantics.
- Accepting Agent self-report as model identity proof, adding a fallback model, lowering reasoning effort, or retrying a failed Stage 0 call.
- Human authoring/review, an adjudicator, third reviewer, generic qualification framework, Human Brief, dashboard, training, mining, tuning, blind-v2-002, blind-v3, release, or default-router promotion.

## Decisions

### Stage 0 is a separate pre-data qualification, not a blind-v2 attempt

Stage 0 runs only after this change is approved and applied under a dedicated short Goal. Before any call, the controller revalidates the canonical terminal artifact and requires all zero-exposure fields to remain true: candidate count zero, no Commit B, no Arm A/C load, no model score, no formal evaluation, and no attempt marker. It also requires the existing failed terminal and Commit A-agent to remain reachable and unchanged.

Stage 0 has exactly three top-level role calls and no retry of any kind. It receives dummy text only and cannot open repository prompts beyond the frozen role/config contract, private candidate roots, model files, or evaluation namespaces. Its success state is runtime qualification, not a research conclusion.

Alternative rejected: treat the absence of an attempt marker as permission to continue the old change. That would erase the semantic force of its pre-evaluation terminal state.

The fixed logical private root remains
`/tmp/hermes-router-v2-blind-v2-stage0`. On hosts such as macOS, the
platform-owned `/tmp` entry may itself resolve through an operating-system
symlink only when its target is an existing sticky directory. This is a narrow
logical-to-physical alias allowance, not a general symlink relaxation: every
component below `/tmp`, including the Stage 0 directory, ledger, receipt
directory, and receipt file, remains non-symlinked. The Stage 0 directory and
receipt directory remain `0700`; both the ledger and every terminal receipt
file remain regular files at `0600`. Receipt creation uses exclusive
`O_CREAT|O_EXCL` semantics with mode `0600`, and validation fails closed on
any parent-mode, file-mode, file-type, or symlink drift before reading bytes.
The existing outside-repository and hash-bound requirements remain unchanged.

Alternative rejected: rewrite the frozen path to `/private/tmp`, `$TMPDIR`,
or a home-directory fallback after the three calls. That would mutate
predeclared host authority instead of repairing the platform alias validator.

### Host invocation envelopes are the configuration authority

For each role, the receipt records the controller-supplied `model`, `reasoning_effort`, `fork_context=false`, role, invocation timestamp, returned Agent identifier, response hash, canonical canary payload, and observable invocation lineage. These fields come from the host call boundary rather than from the Agent's response.

`provider_returned_model` is nullable. When the host does not expose it, the receipt records `model_identity_evidence=HOST_REQUEST_ENVELOPE` and `provider_returned_model_status=INTERFACE_UNAVAILABLE`. If provider metadata is present, it must match the requested alias; conflicting metadata is terminal. The final report must state that host-envelope attestation does not independently prove backend alias resolution.

Alternative rejected: ask the Agent to report its own model or reasoning effort. Self-report is prompt output, not runtime attestation. A direct provider API that returns resolved metadata would be stronger, but it is a different execution interface and is outside this change.

The qualified Stage 0 contract remains immutable. Later formal Generator and
Reviewer calls apply a separate hash-bound v2 host-envelope schema with exactly
two legal provider-metadata combinations: the exact requested alias with
`AVAILABLE`, or null with `INTERFACE_UNAVAILABLE`. Every success and transport
failure also requires host-observed `lineage_observed=true`,
`tool_call_count=0`, and `descendant_agent_count=0`. Provider status and lineage
must remain bound through external metadata, sanitized attempt/terminal and
retry records, the frozen ledger, and evaluation replay. Any response bytes are
substantive regardless of provider-metadata availability, so invalid output or a
refusal cannot acquire a transport retry. The legacy strict returned-model smoke
validator remains readable only for immutable failed audit history and is not a
formal-call authority.

### The canary validates structured compliance, not byte formatting

Each role receives a frozen role-specific nonce and an instruction to return one JSON object containing exactly `protocol`, `role`, `nonce`, and `status=READY`. Validation parses strict JSON with duplicate-key rejection, rejects extra or missing fields, and compares the canonical object to the preregistered expectation. Whitespace and object-key order do not matter; semantic content does.

The canary explicitly forbids tools, delegation, nested Agents, repository access, memory imports, and explanatory prose. Qualification requires a fresh non-forked session, empty history, no imported memory, one response, and exactly one observable top-level invocation for that role. Any observed descendant, extra call, tool use, malformed object, refusal, timeout, transport error, or mismatch terminates Stage 0. If the host cannot expose enough lineage to prove the required boundary, the result is `AGENT_RUNTIME_STAGE0_LINEAGE_UNVERIFIABLE`, not a pass.

Alternative rejected: exact response-byte hashes as the primary assertion. The prior smoke showed that harmless formatting and prose differences can fail a byte contract; strict canonical JSON preserves the intended semantic check without accepting extra content.

### Stage 0 has a small, explicit terminal vocabulary

The only success state is `AGENT_RUNTIME_STAGE0_QUALIFIED`. Failures use one of:

- `AGENT_RUNTIME_STAGE0_CONFIG_UNAVAILABLE`
- `AGENT_RUNTIME_STAGE0_CANARY_MISMATCH`
- `AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION`
- `AGENT_RUNTIME_STAGE0_LINEAGE_UNVERIFIABLE`
- `AGENT_RUNTIME_STAGE0_TRANSPORT_FAILURE`
- `AGENT_RUNTIME_STAGE0_AUTHORITY_DRIFT`

Every state records `router_decision=KEEP_BASELINE`, `production_ready=false`, `release_authorized=false`, and `default_router_unchanged=true`. Failure authorizes no repair loop, fallback, candidate generation, or Commit A2.

### Commit A2 is conditional administrative supersession

Only a qualified Stage 0 receipt plus a fresh zero-exposure audit can authorize preparation of Commit A2. Commit A2 must bind:

- the prior Commit A-agent and terminal commit/artifact hashes;
- the Stage 0 change/spec and qualification receipt hashes;
- the exact host-envelope evidence model and its limitation disclosure;
- the unchanged Generator/Reviewer aliases and reasoning efforts;
- every unchanged 128/96 construction, isolation, contamination, selection, model, gate, metric, seed, attempt, and claim contract;
- `supersession_reason=PRE_DATA_HOST_ATTESTATION_CONTRACT_REPAIR`;
- `candidate_data_seen_before_commit_a2=false`, `model_scores_observed_before_commit_a2=false`, and `formal_attempt_started_before_commit_a2=false`.

Commit A2 is not attempt-2, `blind-v2-002`, blind-v3, or a new dataset because no dataset or attempt existed. It cannot be created in the Stage 0 Goal without separate commit authorization. Candidate generation remains blocked until Commit A2 exists on a clean worktree and a later full-execution Goal is explicitly approved.

### Execution is split into two Goals

Goal A performs only Stage 0 and focused receipt validation, with a fifteen-minute wall-clock target and exactly three top-level role calls. It closes immediately on any terminal state. Full repository CI is not a prerequisite for deciding runtime qualification; only focused schema/authority tests and `git diff --check` are in scope.

Goal B can be created only after Stage 0 qualifies, the written Commit A2 plan is reviewed, and Commit A2 creation plus full blind-v2 execution are separately authorized. Goal B retains the existing sequence: generation, deterministic scan, two fresh reviewers per candidate, optional deficit-only round 2, Commit B, A/C model smoke, and the unique formal attempt. The potentially hundreds of review sessions therefore cannot hide a three-call runtime incompatibility.

### Proposal-only scope remains inert

The current change-creation phase writes only `proposal.md`, `design.md`, one delta spec, and `tasks.md`. No implementation file, protocol, preregistration, runtime receipt, terminal artifact, private ledger, public result surface, Git history, or remote state changes.

## Risks / Trade-offs

- **Host-envelope evidence does not prove backend alias resolution** → Disclose this exact limitation in Commit A2, manifests, and result wording; fail if provider metadata is present and conflicts.
- **Lineage observability may be insufficient** → Require positive lineage evidence; classify unavailable evidence as `AGENT_RUNTIME_STAGE0_LINEAGE_UNVERIFIABLE` rather than assuming isolation.
- **A successor after a terminal state could look like result-driven retrying** → Permit it only under machine-verified zero candidate/model/attempt exposure and bind both terminal histories in Commit A2.
- **The canary may test instruction compliance more than model identity** → Treat it only as callability/isolation evidence; identity authority remains the host request envelope.
- **Same-provider Generator/Reviewer correlation remains** → Preserve role/input isolation and prohibit claims of statistical independence or human review.
- **Strict no-retry Stage 0 can fail on transient transport** → Accept early inconclusive termination as the cost of a small, auditable qualification boundary.
- **Two Goals add process overhead** → Keep Goal A to three calls and focused checks; the separation prevents another long execution from masking an immediate infrastructure failure.

## Migration Plan

1. Complete and review this proposal-only OpenSpec change; do not invoke Agents or alter Git history.
2. Under separate apply authorization, add RED tests for zero-exposure eligibility, host-envelope receipts, canonical canaries, lineage isolation, terminal states, and Commit A2 gating.
3. Update only the dedicated blind-v2 runner/CLI tests, protocol, and preregistration surfaces needed for runtime qualification; retain all frozen experiment contracts.
4. Validate focused tests, applicable lint/type checks, OpenSpec strict, terminal/frozen-authority guards, and `git diff --check`; obtain read-only review without invoking the three experimental roles.
5. After separate authorization, run Goal A once. Stop on any failure; do not generate candidates.
6. If qualified, prepare the exact Commit A2 diff and request explicit commit/full-execution authorization.
7. Only after Commit A2 and Goal B authorization, resume at candidate generation under the unchanged 128/96 protocol.

Rollback before Commit A2 is deletion or abandonment of the uncommitted successor work. After Commit A2, rollback is branch abandonment; no historical terminal, candidate ledger, model, pilot, default-router, release, or public claim may be rewritten.

## Open Questions

None. If the implementation cannot obtain positive host invocation-lineage evidence, the preregistered outcome is `AGENT_RUNTIME_STAGE0_LINEAGE_UNVERIFIABLE`; it is not an implementation choice to weaken the requirement.
