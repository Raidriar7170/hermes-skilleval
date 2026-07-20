## Context

The terminalized Router V2 blind-v2 run reached the Codex host and the first Generator call returned a 16-candidate response, but the protocol terminated during incomplete Round-1 generation before dataset construction, review, scoring, or evaluation. Subsequent exact-host calls exposed schema incompatibility: the historical Generator schema contains a `const` without `type`; the historical Reviewer schema contains untyped `const`/`enum` nodes and cross-field `allOf`/`if`/`then`/`else` composition that is outside the strict Structured Outputs subset accepted by the provider. Existing tests assert local schema shape but do not recursively check the provider dialect.

The repair must not reinterpret the old run. Its 16 exposed candidates, prompts, private responses, frozen schema hashes, and terminal record remain historical evidence and cannot be used as successor canary inputs. The new phase is allowed to perform exactly one synthetic exact-host call for each of the three fixed roles, but it has no authority to generate formal candidates or evaluate a Router.

## Goals / Non-Goals

**Goals:**

- Define versioned Generator and Reviewer schemas accepted by the strict `codex exec --output-schema` interface.
- Detect unsupported schema nodes recursively before launching a model call.
- Exercise the actual production-shaped successor schemas through one synthetic call per frozen role/configuration.
- Freeze enough host, command, schema, request, response, and lineage evidence to reproduce or audit the preflight boundary.
- End only at `PREFLIGHT_READY / KEEP_BASELINE` or a fail-closed blocker with `KEEP_BASELINE`.

**Non-Goals:**

- Resuming, retrying, repairing in place, or reusing any portion of the 16-candidate terminalized protocol.
- Formal candidate generation, candidate review, Arm A/C model loading, scoring, Commit B, formal evaluation, training, mining, tuning, Router promotion, or public metric claims.
- Commit, push, PR, merge, archive, release, deploy, or any remote write.
- Proving backend alias resolution or scientific independence between same-provider roles.

## Decisions

### Historical schemas remain immutable and successor schemas are versioned

The existing `GENERATOR_RESPONSE_SCHEMA` and `REVIEWER_RESPONSE_SCHEMA` constants remain byte-semantic historical authorities for the old terminalized protocol. New constants carry explicit successor/version names and are the only schemas the new preflight may write to `--output-schema`.

Alternative rejected: edit the old constants in place. Their values are already hash-bound into preregistration and terminal evidence, so in-place repair would blur the distinction between failed history and successor qualification.

### Strict schema shape and semantic review validation are separate layers

Every successor `const` and enum-bearing node declares an explicit JSON type. Objects set `additionalProperties=false`, require every declared property, and use only the provider-supported strict subset. String fields retain `pattern: r"\S"` where nonblank text is required but remove unsupported `minLength`/`maxLength`. The Reviewer successor schema removes `allOf`, `oneOf`, `if`, `then`, and `else`; its fields stay flat and its `decision`/`confidence` domains stay typed enums. Existing deterministic post-parse validation continues to enforce decision/rubric coupling, including null-negative semantics.

Alternative rejected: encode all cross-field rules in JSON Schema composition. The exact provider interface does not support the existing conditional keywords, and a nested tagged-union wrapper would change the formal response shape unnecessarily.

### One recursive compatibility validator is the launch gate

A pure validator traverses object properties, array items, and every supported `anyOf[index]` schema branch with stable JSONPath-like locations. It rejects at least:

- `const` without an explicit matching `type`;
- `enum` without an explicit compatible `type`;
- unsupported composition/conditional keywords, including `allOf`, `oneOf`, `not`, `if`, `then`, `else`, `dependentRequired`, and `dependentSchemas`;
- unsupported reusable-definition branches through fail-closed `$defs` rejection rather than silently skipping their nested schemas;
- unsupported string-length keywords `minLength` and `maxLength`; successor schemas retain supported `pattern` constraints instead;
- an object whose `required` set differs from its declared property set or whose `additionalProperties` is not false;
- an array without an `items` schema; and
- a non-object root.

Tests first demonstrate recursive rejection at nested paths and then demonstrate acceptance of both successor schemas. The preflight calls the same validator immediately before materializing schema files; validation failure launches zero model processes.

Alternative rejected: rely only on a live 400 response. That consumes external calls to detect deterministic local defects and cannot prove nested branches were checked.

### The canaries use production-shaped schemas but synthetic values

The Generator prompt requests exactly `{"candidates":[]}`. Each Reviewer prompt requests one fixed, synthetic, semantically valid review using identifiers `schema-canary-primary` and `schema-canary-negative`; no canonical skill ID or candidate is present. Reviewer A and Reviewer B use the same harmless payload but separate fresh processes and private directories.

Prompts explicitly prohibit repository inspection, tools, delegation, old blind prompts/candidates, skill catalogs, Router/model scores, evaluation inputs, and explanatory prose. A local exact-object validator checks each response after strict-schema parsing.

Alternative rejected: use a smaller canary-only schema. That would prove the transport but not the actual successor Generator/Reviewer schemas.

### The host interface and three invocations are frozen exactly

The controller freezes `/Users/raidriar/.local/bin/codex`, its resolved `0.144.5-aarch64-apple-darwin` release binary and exact binary SHA-256, the observed `codex-cli 0.144.5` version, `exec --json --ephemeral --ignore-user-config --ignore-rules --skip-git-repo-check`, a fresh isolated `-C` directory, exact `-m` and `model_reasoning_effort`, `-s read-only`, the fixed feature-disable list, `--output-schema`, `-o`, and stdin `-`. The public interface path is a package-managed pointer used only to verify the expected CLI authority; each role argv executes the frozen resolved regular file directly, and the real launcher re-hashes it immediately before and after every role process. The public CLI exposes no path or host-injection arguments. The roles are:

- Generator: `gpt-5.6-sol`, `max`;
- Reviewer A: `gpt-5.6-sol`, `ultra`;
- Reviewer B: `gpt-5.6-luna`, `max`.

Each role launcher is attempted exactly once, with no retry, fallback, fork, or descendant-agent facility. The receipt distinguishes `launch_attempt_count` (controller-to-launcher calls) from `process_count` (launcher-confirmed started subprocesses), so a pre-spawn failure cannot claim a process ran. `-s read-only` is not treated as sufficient isolation: the controller parses every JSONL event with a strict state machine requiring `thread.started` first, then `turn.started`, items only inside that turn, exactly one completed `agent_message`, and `turn.completed` last. The canonical JSON in that final message must equal `response.json`, and all three successful roles must have distinct thread IDs. Any command, tool, MCP, unknown item, reordered/post-completion event, malformed lifecycle, or unavailable event truth yields a fail-closed result; an unavailable tool count is represented as null rather than a fabricated zero. Private call roots are newly created with `0700`; schema, prompt, event, and response files are regular `0600` files. Raw prompts/events/responses remain outside the repository.

Alternative rejected: route through the old runner's candidate-generation command. That surface is bound to exposed experiment data and grants broader behavior than a schema transport canary needs.

### The public receipt is sanitized, hash-bound, and non-authorizing

The repository receipt records the source/base commit, interface and resolved executable paths, executable SHA-256, frozen authority SHA-256, CLI version, independently pinned complete argument-template hashes with only private absolute paths replaced by stable role tokens, model/effort, timeout, launcher-attempt count, confirmed process count, retry count zero, schema canonical SHA-256, stdin SHA-256, event/output raw hashes, event validation status, final-message hash, host-authority status, exit status, thread ID, nullable tool-call count, parsed-object hash, and per-role validation result. It records only hashes and synthetic canary metadata, never raw private event streams or old experimental content. Before any host probe, runtime gates revalidate the historical schema hashes and the immutable public terminal bytes/self-hash/state, without reading old private evidence. The frozen public receipt target is also checked before calls. The successor CLI writes validated canonical bytes once with exclusive creation; an existing path or symlink blocks launch rather than being overwritten.

The receipt also freezes `formal_candidate_generation_authorized=false`, `arm_a_c_load_authorized=false`, `scoring_authorized=false`, `commit_b_authorized=false`, `formal_evaluation_authorized=false`, `training_authorized=false`, and all Git/publication authorities false. A canonical `receipt_sha256` binds the document excluding that field.

Alternative rejected: publish raw Codex event logs. They are unnecessary for the public truth surface and could accidentally expose environment or provider details.

### Terminal states fail closed

All three calls, event-isolation checks, and receipt validations must pass for `preflight_state=PREFLIGHT_READY`. Deterministic local schema rejection, historical/frozen authority drift, CLI/version/argv drift, process failure, timeout, event/tool isolation violation, missing/invalid output, evidence permission drift, or receipt hash mismatch yields a specific `PREFLIGHT_*_BLOCKED` state. Every state sets `router_decision=KEEP_BASELINE`, `production_ready=false`, `default_router_unchanged=true`, and `old_protocol_state=AGENT_BLIND_V2_PROTOCOL_INVALID`.

`PREFLIGHT_READY` means only that the frozen schema/host path was compatible at the recorded time. It does not authorize the next experiment phase.

## Risks / Trade-offs

- **The provider strict subset can drift after the canary** → Freeze CLI/schema/argv hashes and require a new successor preflight rather than silently reusing the receipt after drift.
- **Removing schema-level cross-field conditions weakens provider-side semantic enforcement** → Keep deterministic post-parse review validation mandatory; the strict schema still closes shape, types, and value domains.
- **Synthetic success could be mistaken for experiment readiness** → Preserve `KEEP_BASELINE` and explicit false authorization flags in the receipt, spec, and Human Brief.
- **Same-provider canaries do not prove independent reviewers** → Make no independence claim; this phase qualifies only transport/schema compatibility.
- **A transient host failure can block the phase** → Accept fail-closed termination; the no-retry rule is part of the preflight evidence contract.

## Migration Plan

1. Add RED tests for nested untyped constants/enums, forbidden composition, strict object rules, and launch-before-validation protection.
2. Add versioned schemas and the recursive validator, then make focused schema tests GREEN without changing historical constants.
3. Add the successor-only preflight entry point and mocked process/receipt tests, including exact argv, synthetic-data boundary, file modes, no retry, and terminal truth fields.
4. Run focused tests, lint/type checks for touched Python, full applicable tests, strict OpenSpec validation, and `git diff --check`.
5. Invoke the three exact-host canaries once and write the sanitized receipt. Do not rerun a failed role in this change.
6. Generate the Chinese Human Brief from the final receipt and obtain read-only Reviewer findings.

Rollback is abandonment of the uncommitted successor worktree. No historical terminal artifact, remote branch, or public experiment result is rewritten.

## Open Questions

None. Any newly discovered provider incompatibility is a fail-closed preflight result, not permission to loosen the schema or retry a role during this change.
