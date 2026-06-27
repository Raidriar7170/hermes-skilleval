# Hermes SkillEval v0.3 Evidence Protocol

Status: frozen draft for PR-0 review

Date: 2026-06-26

Random seed: `20260625`

## Purpose

v0.3 defines how Hermes SkillEval will evaluate external skill-routing
generalization and live-agent execution transfer without changing standards
after results are visible. This protocol is authoritative for later PR-1
through PR-7 work. It does not claim that any v0.3 benchmark run, live-agent
run, or router promotion has happened.

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

## Scope

### In Scope

- SkillRouter external benchmark adapter, provenance, and official metric
  reproduction in later PRs.
- Frozen zero-shot routing evaluation for `baseline-minilm` and
  `finetuned-embedding`, with optional sanity baselines if preregistered.
- Field views: `name_only`, `metadata`, and `full_body`.
- Candidate pool experiments using deterministic sampling from seed `20260625`.
- Strict split and leakage reports.
- Live-agent task selection from no-credential tasks with deterministic
  verifiers.
- Live-agent conditions: `no-skill`, `routed-skill`, `oracle-skill`.
- Evidence validity and optional router promotion decisions as separate gates.

### Out of Scope

- Training, threshold tuning, model selection, or hard-negative mining on
  SkillRouter final scored labels.
- Rewriting Phase 10-18 historical conclusions.
- Treating Phase 10 deterministic replay as live-agent evidence.
- Committing external full data, model checkpoints, embedding caches,
  credentials, raw traces, unredacted logs, or private infrastructure details.
- Replacing deterministic verifier outcomes with LLM or human preference
  judgments.
- Promoting a candidate router from a single headline metric.

## Preregistration

Before any final v0.3 scored evaluation or live-agent matrix, the run MUST
write a preregistration artifact with:

- git commit and dirty-state summary;
- run ID and timestamp;
- seed `20260625`;
- router IDs, versions, model identifiers, checkpoints or hashes, thresholds,
  top-k values, rerank depth, and text builder versions;
- external data root, upstream refs, file hashes, license notes, and adapter
  version;
- field views and candidate pool sizes;
- live-agent model, CLI/runtime version, sandbox, timeout, retry policy, and
  any unsupported deterministic controls marked `UNAVAILABLE`;
- task selection rules and exclusion reasons;
- success metrics and gate thresholds.

Final scored labels and final live-agent outcomes MUST NOT be used to rewrite
the preregistered router list, thresholds, task list, or gate thresholds.

## External Benchmark Protocol

SkillRouter scored tasks are evaluation-only. Later PRs may implement adapters,
metrics, and manifests, but PR-0 freezes these rules:

- Official metrics are reported in an `official` namespace.
- Hermes diagnostics are reported in a separate `hermes_diagnostics` namespace.
- Unknown or invalid prediction IDs are diagnostics and must not be silently
  ignored.
- Missing task predictions count as empty predictions unless an upstream
  official scorer requires a different preregistered behavior.
- External data without explicit negative labels MUST NOT be reported with
  Hermes Negative Hit Rate or Negative Accepted Rate.
- The Easy and Hard tiers are both required when available; if a tier cannot be
  evaluated, the evidence status becomes `REVIEW_REQUIRED` or
  `INVALID_EVIDENCE` with a reason.
- Candidate pool stress tests must include every relevant skill before adding
  distractors. If a smaller target pool cannot include all relevant skills, that
  pool is `UNAVAILABLE`.

## Candidate Pool Sampling

For non-official stress subsets:

1. Compute the union of all relevant skill IDs for the scored tasks in scope.
2. If the target pool size is smaller than the relevant-skill union, mark the
   subset `UNAVAILABLE`.
3. Sort remaining candidate skill IDs by `sha256("20260625:" + skill_id)`.
4. Select the first IDs needed to reach the target size.
5. Use the same selected candidate list for every router and task in that tier.
6. Record the candidate list hash and sampling config in the manifest.

Stress subsets are Hermes diagnostics only. They must not be described as
official SkillRouter results.

## Field Views

At minimum, later routing runs MUST evaluate:

| View | Input |
|---|---|
| `name_only` | skill name |
| `metadata` | skill name and description |
| `full_body` | skill name, description, and full skill body |

Each text builder MUST be versioned and recorded. Changing a text builder after
seeing final scored results requires a new run ID and an explicit reason.

## Internal Strict Splits

Internal Hermes strict-split checks remain separate from SkillRouter official
scoring:

- `held_out_skill` is required for internal diagnostics when labels permit it.
- `held_out_source` is required only when source metadata is sufficient.
- If metadata is insufficient, output `UNAVAILABLE` with a precise reason.
- Internal strict-split outcomes must not be merged into official external
  metric tables.

## Live-Agent Protocol

Live-agent evidence must be generated by a distinct runtime contract such as
`live-agent.v1`. Phase 10 `agent-loop.v1` remains deterministic offline replay
and historical evidence only.

Task selection MUST satisfy:

- no external credentials or private account state;
- deterministic verifier available and stable in qualification runs;
- oracle-skill condition can pass before the task enters the final matrix;
- task workspace can be isolated and cleaned;
- no access to gold labels, oracle implementation details, expected verifier
  answers, or this protocol by the Evaluation Codex during task execution.

Live-agent conditions:

| Condition | Meaning |
|---|---|
| `no-skill` | Agent receives no injected skill guidance. |
| `routed-skill` | Agent receives the preregistered router output. |
| `oracle-skill` | Agent receives the task's approved oracle skill guidance. |

Planned repetitions are 3 per condition per selected task. If an agent runtime
cannot enforce deterministic seed control, the manifest MUST record the
unsupported control as `UNAVAILABLE` rather than pretending determinism.

Deterministic verifiers are the primary success judge. LLM judges, transcript
review, screenshots, or human review may be diagnostic fields only.

## Evidence Status Gate

The Benchmark Validity Gate decides whether the evidence packet is usable. It
does not decide whether a candidate router becomes default.

Allowed top-level evidence statuses:

| Status | Meaning |
|---|---|
| `VALID_EVIDENCE` | Required artifacts, provenance, metrics, leakage checks, and verifier records are complete enough for the preregistered question. |
| `INVALID_EVIDENCE` | Required evidence is missing, corrupted, contaminated, or inconsistent enough that the run cannot support the question. |
| `REVIEW_REQUIRED` | Evidence is mostly present but contains caveats that require human review before any downstream decision. |

Allowed field-level marker:

| Marker | Meaning |
|---|---|
| `UNAVAILABLE` | A specific evidence field or optional check could not be produced and includes a reason. It is not a top-level Benchmark Validity Gate status. |

The gate MUST check at least:

- required manifests and config snapshots exist;
- external data hashes and upstream refs are recorded;
- official metrics and Hermes diagnostics are separated;
- no final scored-label tuning is detected;
- leakage report exists or marks unavailable checks precisely;
- live-agent verifier records exist for every counted run;
- raw traces and logs are either outside Git or redacted summaries;
- all skipped tasks and failed runs have reasons.

## Router Promotion Gate

The Router Promotion Gate may run only after the Benchmark Validity Gate returns
`VALID_EVIDENCE` or an explicitly accepted `REVIEW_REQUIRED` outcome.

Allowed promotion decisions:

| Decision | Meaning |
|---|---|
| `KEEP_BASELINE` | Keep the current default router. |
| `PROMOTE_CANDIDATE` | Promote the candidate router only if every preregistered safety and transfer condition passes. |
| `REVIEW_REQUIRED` | Defer promotion until a human reviews conflicts, regressions, or incomplete evidence. |

Promotion MUST consider:

- external official metrics;
- Hermes diagnostics;
- live-agent pass rate by condition;
- oracle gap;
- route-to-execution transfer;
- regressions where `routed-skill` is worse than `no-skill`;
- cost, timeout, and failure taxonomy;
- consistency with current default-router release boundaries.

`finetuned-embedding` remains a diagnostic candidate until a future promotion
artifact explicitly approves it.

## Stop Conditions

Stop and mark the current run or phase `REVIEW_REQUIRED` or `INVALID_EVIDENCE`
when any of the following occurs:

- scored labels influence training, threshold selection, task filtering, or
  model selection;
- external data provenance or file hashes cannot be established;
- relevant skills are missing from candidate pools without an upstream reason;
- live-agent verifier instability cannot be resolved;
- oracle-skill condition fails qualification for a selected task;
- credentials, private host details, raw auth files, model weights, embedding
  caches, or unredacted traces would need to enter Git;
- Phase 10 replay artifacts are being used as live-agent proof;
- evidence validity and promotion decisions become conflated.

## Data and Artifact Retention

Git may contain:

- protocol docs, OpenSpec artifacts, and placeholder configs;
- small fixtures;
- redacted summaries;
- manifests with hashes;
- reports with reproducible commands;
- screenshots or HTML summaries that contain no private data.

Git must not contain:

- external full datasets;
- model checkpoints or downloaded model files;
- embedding caches;
- raw live-agent traces;
- credentials, tokens, cookies, private host details, or auth files;
- unredacted stdout/stderr logs.

Large or sensitive artifacts should live under ignored artifact roots such as
`artifacts/v0.3/{run_id}/` and be represented in Git by redacted summaries and
hash manifests only.

## PR Sequence

- PR-0: freeze protocol, OpenSpec, contributor constraints, placeholder configs.
- PR-1: implement external adapter and provenance validation.
- PR-2: implement official metric reproduction and scorer parity.
- PR-3: implement frozen routing matrix, field ablations, candidate-pool stress
  tests, strict generalization checks, bootstrap confidence intervals, and
  overlap reporting.
- PR-4: implement live-agent runtime abstraction, fake runner, workspace
  isolation, verifier contract, and `live-agent.v1` trace schema without
  invoking a real agent.
- PR-5: implement the Codex CLI runner, isolated execution preflight, skill
  mounting, JSONL trace parsing, and redaction.
- PR-6: implement SkillsBench task adaptation, task freezing, global E2E skill
  registry, pilot/frozen matrices, and live-agent summaries.
- PR-7: assemble the unified evidence validator, Benchmark Validity Gate,
  optional Router Promotion Gate, decision reports, and evidence-map updates.

Each PR must preserve previous behavior and run the validation commands required
by its scope.

See `docs/v0.3/codex-implementation-guide.md` for the detailed Codex execution
guide for PR-1 through PR-7.
