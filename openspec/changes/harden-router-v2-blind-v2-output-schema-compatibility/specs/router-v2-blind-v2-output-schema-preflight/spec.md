## ADDED Requirements

### Requirement: Historical blind-v2 authority remains terminal and isolated
The successor preflight SHALL preserve the old run as `AGENT_BLIND_V2_PROTOCOL_INVALID / KEEP_BASELINE` and SHALL NOT read or reuse its 16 exposed candidates, blind prompts, private model responses, schema files, Router scores, or evaluation inputs as canary content.

#### Scenario: Successor starts from terminal history
- **WHEN** the successor preflight prepares its local authority
- **THEN** it revalidates the historical schema hashes and public terminal bytes, self-hash, terminal state, and `KEEP_BASELINE` decision without changing historical artifacts or reading old private evidence
- **AND** every canary input is independently synthetic

#### Scenario: Old experiment content is offered as input
- **WHEN** a requested preflight path or payload points at old candidate, prompt, response, score, or evaluation content
- **THEN** the controller fails closed before launching a model process
- **AND** records `KEEP_BASELINE`

### Requirement: Successor schemas satisfy recursive strict compatibility
The system SHALL define versioned Generator and Reviewer successor schemas in which every `const` and enum-bearing node declares an explicit compatible type, every object is closed and fully required, every array declares items, supported `anyOf` branches are traversed recursively, supported string `pattern` constraints are retained, and no unsupported composition, conditional, `$defs`, `minLength`, or `maxLength` keyword is present.

#### Scenario: Nested untyped constant is checked
- **WHEN** a `const` without explicit `type` appears at any nesting depth
- **THEN** the recursive validator rejects the schema with the stable nested path
- **AND** no host call is launched

#### Scenario: Nested untyped enum is checked
- **WHEN** an enum-bearing node lacks an explicit compatible `type` at any nesting depth
- **THEN** the recursive validator rejects the schema with the stable nested path
- **AND** no host call is launched

#### Scenario: Supported anyOf branches are checked
- **WHEN** an invalid schema node appears within any indexed `anyOf` branch
- **THEN** the recursive validator rejects it with the stable indexed path
- **AND** no host call is launched

#### Scenario: Unsupported composition is checked
- **WHEN** any schema branch contains `allOf`, `oneOf`, `not`, `if`, `then`, `else`, `dependentRequired`, `dependentSchemas`, `$defs`, `minLength`, or `maxLength`
- **THEN** the recursive validator rejects the exact keyword path before launch

#### Scenario: Successor schemas pass locally
- **WHEN** the validator traverses the versioned Generator and Reviewer schemas
- **THEN** both schemas pass with zero compatibility findings
- **AND** the historical schemas remain unchanged

### Requirement: Reviewer semantic consistency remains deterministic
The successor Reviewer schema SHALL close the flat response shape and type/value domains, while deterministic post-parse validation SHALL enforce decision/rubric and null-negative consistency that the provider strict subset cannot express.

#### Scenario: Provider-shaped review is semantically valid
- **WHEN** a parsed response uses an allowed decision and confidence and satisfies all decision/rubric rules
- **THEN** deterministic validation accepts it

#### Scenario: Typed review violates decision semantics
- **WHEN** a parsed response satisfies schema types but contradicts its decision/rubric or negative-null rules
- **THEN** deterministic validation rejects it
- **AND** no successful preflight receipt can be produced from that response

### Requirement: Exact-host canaries are synthetic and one-shot
The preflight SHALL invoke exactly one fresh `codex exec --output-schema` process for Generator, Reviewer A, and Reviewer B using the frozen interface pointer, the directly executed resolved regular-file target, executable SHA-256 revalidated around each process, CLI version, model, reasoning effort, read-only sandbox, feature-disable set, isolated working directory, and stdin interface. It MUST NOT retry, fall back, fork context, enable descendant agents, or expose caller-selectable path/host injection.

#### Scenario: Three compatible role calls
- **WHEN** local schema validation passes and the frozen host interface matches
- **THEN** the controller launches exactly one process for each of the three roles
- **AND** each receives only its fixed synthetic canary prompt and successor schema
- **AND** the event lifecycle is strictly ordered, each final agent-message JSON equals its response file, and the three thread IDs are distinct

#### Scenario: A role call fails
- **WHEN** any exact-host process times out, exits nonzero, lacks a response, returns an invalid object, or emits a command/tool/unknown/malformed JSONL event lifecycle
- **THEN** that role is not retried
- **AND** the overall preflight fails closed with `KEEP_BASELINE`

#### Scenario: A launcher fails before process creation
- **WHEN** a controller-to-launcher call fails before a subprocess is confirmed started
- **THEN** its launch-attempt count is one and its process count is zero
- **AND** unavailable thread or tool-use truth is represented explicitly rather than as a fabricated successful or zero-tool result

#### Scenario: Host authority drifts before launch
- **WHEN** the executable, CLI version, argument contract, schema hash, or role configuration differs from the frozen values
- **THEN** the controller launches no call under the drifted authority
- **AND** records a fail-closed preflight state

### Requirement: Preflight evidence is private by default and publicly sanitized
The system SHALL keep raw schema materializations, prompts, event streams, and outputs in a new outside-repository private root with directory mode `0700` and regular-file mode `0600`. The repository SHALL contain only a sanitized canonical receipt with frozen hashes, non-sensitive host metadata, role results, terminal truth fields, and a self-hash; that receipt MUST be created exclusively as a regular file and MUST NOT overwrite an existing path or follow a symlink.

#### Scenario: Compatible preflight is frozen
- **WHEN** all three roles pass and private evidence permissions validate
- **THEN** the public receipt binds executable, CLI, argv template, schema, prompt, event, final-message, response, and parsed-object hashes plus actual launcher/process counts for every role
- **AND** raw private events and responses are absent from the repository

#### Scenario: Evidence permissions or hashes drift
- **WHEN** a private evidence path is symlinked, has an unexpected mode/type, or a frozen hash fails validation
- **THEN** the preflight fails closed
- **AND** cannot claim `PREFLIGHT_READY`

### Requirement: Preflight terminal truth never authorizes experiment execution
The only successful compatibility state SHALL be `PREFLIGHT_READY`, and it SHALL always be paired with `router_decision=KEEP_BASELINE`. Every success or failure receipt SHALL keep production, candidate generation, Arm A/C loading, scoring, Commit B, formal evaluation, training, Git publication, release, and archive authority false.

#### Scenario: All compatibility gates pass
- **WHEN** all local, host, output, evidence, and receipt gates pass
- **THEN** the receipt records `PREFLIGHT_READY / KEEP_BASELINE`
- **AND** explicitly states that a separate successor phase and authorization are required before formal candidate generation

#### Scenario: Any compatibility gate fails
- **WHEN** one or more required gates do not pass
- **THEN** the receipt records a specific fail-closed `PREFLIGHT_*_BLOCKED` state and `KEEP_BASELINE`
- **AND** no downstream experiment action is authorized
