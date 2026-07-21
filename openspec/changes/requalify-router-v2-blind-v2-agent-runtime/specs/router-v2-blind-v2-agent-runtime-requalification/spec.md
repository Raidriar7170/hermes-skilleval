## ADDED Requirements

### Requirement: Requalification is eligible only before any blind data or evaluated-model exposure
The system SHALL permit Router V2 blind-v2 Agent runtime requalification only when canonical evidence proves that the prior workflow terminalized at `failure_stage=agent_config_smoke`, candidate count is zero, Commit B does not exist, Arm A/C was not loaded, no model score was observed, no formal evaluation started, and no attempt marker exists. The system MUST bind the unchanged prior Commit A-agent and terminal artifact hashes before any Stage 0 call.

#### Scenario: Prior terminal preserved with zero exposure
- **WHEN** every canonical zero-exposure field is true and the prior Commit A-agent plus terminal artifact hashes match
- **THEN** the system marks Stage 0 eligible without authorizing candidate generation, model loading, scoring, Commit A2, or a formal attempt

#### Scenario: Exposure or authority drift exists
- **WHEN** any candidate, Commit B, Arm A/C load, model score, formal evaluation, attempt marker, or prior-authority hash mismatch is observed
- **THEN** the system records `AGENT_RUNTIME_STAGE0_AUTHORITY_DRIFT`, keeps `KEEP_BASELINE`, invokes no Agent, and forbids requalification and Commit A2

### Requirement: Stage 0 invokes exactly the three approved configurations once
The system SHALL make exactly three top-level dummy-text calls: Generator `gpt-5.6-sol/max`, Reviewer A `gpt-5.6-sol/ultra`, and Reviewer B `gpt-5.6-luna/max`. Each call SHALL use `fork_context=false`, a fresh session, empty history, zero imported memory, and no retry of any kind.

#### Scenario: Three approved calls complete
- **WHEN** each approved role receives exactly one top-level invocation and no other Agent invocation occurs
- **THEN** the system evaluates the three receipts for configuration, canary, and isolation qualification

#### Scenario: Call is unavailable or transport fails
- **WHEN** an approved alias/reasoning pair is rejected, times out, disconnects, or otherwise fails to return a valid response
- **THEN** the system records `AGENT_RUNTIME_STAGE0_CONFIG_UNAVAILABLE` or `AGENT_RUNTIME_STAGE0_TRANSPORT_FAILURE`, performs no retry or fallback, and stops before candidate generation

### Requirement: Host invocation envelopes attest requested configuration honestly
The system SHALL treat the host invocation envelope, not Agent self-report, as authority for requested model alias, reasoning effort, `fork_context`, role, invocation time, returned Agent identifier, response hash, and observable lineage. `provider_returned_model` SHALL be nullable; absent provider metadata SHALL be recorded as `provider_returned_model_status=INTERFACE_UNAVAILABLE` and `model_identity_evidence=HOST_REQUEST_ENVELOPE`.

#### Scenario: Provider metadata is unavailable
- **WHEN** the host accepts the exact requested configuration but exposes no provider-returned resolved-model metadata
- **THEN** the system may continue qualification using host-envelope evidence only and MUST disclose that backend alias resolution is not independently proven

#### Scenario: Provider metadata conflicts
- **WHEN** provider-returned metadata is available and does not match the requested alias or reasoning contract
- **THEN** the system records `AGENT_RUNTIME_STAGE0_CONFIG_UNAVAILABLE`, rejects the role receipt, uses no Agent self-report or fallback, and stops

#### Scenario: Agent claims its own configuration
- **WHEN** an Agent response contains a model or reasoning-effort claim
- **THEN** the system MUST NOT use that claim as identity evidence or to override the host invocation envelope

### Requirement: Canonical JSON canaries prove bounded response compliance
The system SHALL preregister one role-specific nonce per approved role and require exactly one strict JSON object with only `protocol`, `role`, `nonce`, and `status=READY`. Validation MUST reject duplicate keys, extra fields, missing fields, explanatory prose, invalid UTF-8, or semantic mismatch, while ignoring JSON key order and insignificant whitespace.

#### Scenario: Canonical canary matches
- **WHEN** a response parses as strict JSON and its canonical object exactly matches the preregistered role expectation
- **THEN** the system marks that role's canary valid and records the raw-response and canonical-response hashes

#### Scenario: Canary is malformed or semantically different
- **WHEN** strict parsing fails or any field, value, count, or surrounding content differs from the preregistered object
- **THEN** the system records `AGENT_RUNTIME_STAGE0_CANARY_MISMATCH`, performs no repair or retry, and stops

### Requirement: Stage 0 proves no tools, delegation, or hidden context
The system SHALL require positive observable evidence that each role used a fresh non-forked session with empty history, no imported memory, no tool call, no delegation, no nested Agent, one response, and exactly one top-level role invocation. Inability to observe enough lineage SHALL be terminal rather than presumed safe.

#### Scenario: Isolation lineage is complete and clean
- **WHEN** host evidence proves all required isolation fields and contains no descendant or tool invocation
- **THEN** the system marks that role's isolation receipt valid

#### Scenario: Nested Agent or tool use is observed
- **WHEN** any role invokes a tool, delegates work, spawns a descendant, reuses context, imports memory, or emits multiple responses
- **THEN** the system records `AGENT_RUNTIME_STAGE0_ISOLATION_VIOLATION`, preserves the lineage, and stops without a retry

#### Scenario: Lineage cannot prove isolation
- **WHEN** the host cannot expose the session, history, memory, tool, descendant, or response-count evidence required by the contract
- **THEN** the system records `AGENT_RUNTIME_STAGE0_LINEAGE_UNVERIFIABLE` and MUST NOT infer a pass

### Requirement: Stage 0 preserves the fixed private path across platform temp aliases
The system SHALL keep the logical Stage 0 root fixed at
`/tmp/hermes-router-v2-blind-v2-stage0`. It MAY accept the operating-system
`/tmp` entry itself as a trusted logical-to-physical alias only when it
resolves to an existing sticky directory. The system MUST reject every symlink
below that trusted entry and MUST preserve the existing outside-repository,
`0700` Stage 0 and receipt directories, regular `0600` ledger and receipt
files, hash-bound receipt, and exclusive-create requirements. Receipt creation
MUST use mode `0600`; receipt validation MUST reject non-regular files,
symlinks, parent modes other than `0700`, and file modes other than `0600`
before reading bytes. It MUST NOT relocate the ledger or receipt to
`/private/tmp`, `$TMPDIR`, a home directory, or another fallback after role
invocation.

#### Scenario: Platform temp entry is an operating-system alias
- **WHEN** the fixed `/tmp` entry resolves through a platform symlink to a real sticky temporary directory and every Stage 0 descendant is non-symlinked
- **THEN** the system validates the original logical ledger path without changing its authority string, ledger bytes, or contract hash

#### Scenario: A descendant or fallback path is substituted
- **WHEN** the Stage 0 directory, ledger, receipt directory, or receipt file is a symlink, or a different logical root is substituted as a fallback
- **THEN** the system rejects the path before reading or writing a terminal receipt and keeps `KEEP_BASELINE`

#### Scenario: Ledger or receipt permissions drift
- **WHEN** the ledger or receipt is not a regular `0600` file, or its private parent directory is not `0700`
- **THEN** the system rejects the artifact before reading its bytes and keeps `KEEP_BASELINE`

### Requirement: Stage 0 success and failure remain non-research terminal states
The system SHALL emit `AGENT_RUNTIME_STAGE0_QUALIFIED` only when all three configuration, canary, and isolation receipts pass. Every Stage 0 state SHALL record `router_decision=KEEP_BASELINE`, `production_ready=false`, `release_authorized=false`, and `default_router_unchanged=true`; no Stage 0 state is a blind-v2 metric or research conclusion.

#### Scenario: All three roles qualify
- **WHEN** the three exact role receipts pass every authority, configuration, canary, and isolation check
- **THEN** the system records `AGENT_RUNTIME_STAGE0_QUALIFIED` and authorizes only preparation of a proposed Commit A2 diff

#### Scenario: Any role fails
- **WHEN** any one role fails any Stage 0 requirement
- **THEN** the system records the exact failure state, keeps `KEEP_BASELINE`, and forbids Commit A2, candidate generation, model loading, scoring, and formal evaluation

### Requirement: Formal Agent records preserve host identity and isolation authority
The system SHALL bind every formal Generator and Reviewer invocation to the host-requested model alias and reasoning effort. Provider-returned model metadata MUST be either null with `provider_returned_model_status=INTERFACE_UNAVAILABLE` or the exact requested alias with `provider_returned_model_status=AVAILABLE`. Every substantive and transport-failure record MUST contain host-observed `lineage_observed=true`, `tool_call_count=0`, and `descendant_agent_count=0`; these fields MUST survive external metadata validation, sanitization, retry records, freeze, and evaluation replay.

#### Scenario: Provider metadata is unavailable but host isolation is proven
- **WHEN** the host records the exact requested alias/effort, `returned_model=null`, `provider_returned_model_status=INTERFACE_UNAVAILABLE`, and positive zero-tool/zero-descendant lineage
- **THEN** the invocation remains eligible for substantive validation without claiming independent backend alias resolution

#### Scenario: Provider metadata or lineage conflicts
- **WHEN** provider status and returned model form any other combination, provider metadata conflicts with the requested alias, lineage is missing/unobserved, or any tool/descendant count is nonzero
- **THEN** the pack or replay fails closed before freeze or scoring

#### Scenario: Response content attempts to establish identity or obtain a retry
- **WHEN** Agent response text self-reports a model/reasoning value or returns refusal/invalid-schema bytes while provider metadata is unavailable
- **THEN** self-report establishes no identity authority and the response remains substantive with no transport retry

### Requirement: Commit A2 requires qualified runtime evidence and fresh authorization
The system SHALL permit Commit A2 preparation only after `AGENT_RUNTIME_STAGE0_QUALIFIED` and a fresh zero-exposure audit. Commit A2 SHALL supersede Commit A-agent `50069a124a8d129e11926e78d1bcc2388bc91a22`, bind the failed terminal and Stage 0 receipt hashes, set `supersession_reason=PRE_DATA_HOST_ATTESTATION_CONTRACT_REPAIR`, and preserve every approved blind-v2 data, review, model, metric, gate, attempt, and claim boundary. Creating Commit A2 SHALL require separate explicit commit authorization.

#### Scenario: Qualified successor is prepared
- **WHEN** Stage 0 qualified, zero exposure still holds, the worktree is clean, and the user separately authorizes Commit A2 creation
- **THEN** Commit A2 binds both histories and becomes the only authority for later candidate generation

#### Scenario: Commit A2 is requested without all gates
- **WHEN** Stage 0 is absent/failed, zero exposure no longer holds, the worktree is not clean, or commit authorization is absent
- **THEN** the system refuses Commit A2 and performs no candidate generation

#### Scenario: Successor classification is reported
- **WHEN** Commit A2 is described in any artifact or report
- **THEN** it is classified as a pre-data host-attestation contract repair, not attempt-2, `blind-v2-002`, blind-v3, a replacement dataset, or a repeated formal evaluation

### Requirement: Original blind-v2 scientific and fairness contracts remain unchanged
The system MUST preserve the approved 256-candidate first round, optional deficit-only round 2, 128-task/96-negative freeze, 16 skills, 128 families, role-isolated dual-review unanimity, contamination thresholds, deterministic selection, frozen Arm A/C identities, seeds `7170/7171/7172`, unchanged pilot-002 gate, one formal attempt, and bounded Agent-only claims. Human authoring/review, adjudication, a third reviewer, training, tuning, fallback models, release, and default-router promotion remain prohibited.

#### Scenario: Commit A2 or implementation changes scientific content
- **WHEN** a proposed change alters any candidate quota, review input, acceptance rule, contamination threshold, selection rule, model/checkpoint, metric, gate, seed, attempt rule, or claim boundary
- **THEN** the system classifies the change as out of scope and blocks requalification apply

#### Scenario: Later result wording is produced
- **WHEN** a later full blind-v2 run produces any terminal result
- **THEN** evidence is described as `AGENT_GENERATED / DUAL_AGENT_UNANIMOUS_REVIEWED` with `human_author_count=0`, `human_reviewer_count=0`, same-provider correlation disclosed, and no human-reviewed or statistically-independent claim

### Requirement: Qualification and full execution use separate authorized Goals
The system SHALL execute Stage 0 in a short Goal containing only the zero-exposure audit, three top-level dummy calls, receipt validation, and focused checks. A full blind-v2 Goal SHALL be created only after Stage 0 qualifies, Commit A2 is separately approved and created, and the user explicitly authorizes candidate generation and formal execution.

#### Scenario: Stage 0 Goal begins
- **WHEN** the proposal/apply artifacts are approved and the user explicitly starts runtime qualification
- **THEN** the Goal excludes candidate data, Arm A/C access, Commit A2 creation, full evaluation, commit, push, and PR mutation unless separately authorized

#### Scenario: Full Goal is requested too early
- **WHEN** Stage 0 is not qualified or Commit A2 does not exist as clean authority
- **THEN** the system refuses to start candidate generation or formal blind-v2 execution

### Requirement: Proposal-only creation is inert
The system SHALL limit the currently authorized proposal phase to `proposal.md`, `design.md`, this capability spec, and `tasks.md`. It MUST NOT call any Agent, read or generate candidate data, load Arm A/C, create runtime receipts, modify implementation/protocol/preregistration files, create commits, push, or mutate GitHub state.

#### Scenario: Proposal artifacts are generated
- **WHEN** this OpenSpec change is created under the current authorization
- **THEN** only the four planning surfaces are added locally and all prohibited runtime, Git, and external actions remain absent
