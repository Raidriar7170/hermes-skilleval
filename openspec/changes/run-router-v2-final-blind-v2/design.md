## Context

Router V2 pilot-002 is frozen and merged through PR #38. Its canonical evidence binds 64 training positives, 52 model-adjudicated hard negatives, Arm A and Arm C checkpoints for seeds `7170`, `7171`, and `7172`, and one 16-positive/9-negative-label held-out attempt. The result remains `MODEL_ONLY_PILOT`, `KEEP_BASELINE`, non-production, and not final blind-v2 evidence.

Historical commit `09ba4104a147a2f740ef69283c850f40e78a0b15` implemented and preregistered an external human-authored, independently human-reviewed 64/48 protocol. No human pack was supplied and no formal attempt began. On 2026-07-17 the user explicitly replaced that data-source contract with a fully agent-generated and dual-agent-reviewed 128/96 design. The old commit remains immutable history, but a new `Commit A-agent` must supersede it before any candidate generation. All smoke receipts bound to the old SHA are obsolete for the new protocol.

The research question is correspondingly narrower: do the unchanged Arm C checkpoints meet the unchanged pilot-002 gate once on a larger, preregistered agent-constructed set accepted only by unanimous, role-isolated Agent review? This experiment cannot establish human-authored real-world generalization or statistical independence among reviewers from the same provider.

The repository is OpenSpec-managed. This remains the only change. The user forbids a new Phase number, Human Brief, dashboard, generic qualification framework, adjudicator/third review, retraining, post-hoc tuning, blind-v3, and edits to historical pilot artifacts.

## Goals / Non-Goals

**Goals:**

- Freeze generation/review prompts, schemas, exact Agent configurations, isolation rules, retry rules, contamination checks, selection rules, evaluator code, model/data authority, statistics, gate, and non-actions before candidate generation.
- Construct a 128-task, 96-negative-label, 16-skill, 128-family set through one generator plus two role-isolated reviewers under exact three-way label agreement.
- Keep raw Agent traces outside Git while preserving canonical hashes, requested and returned model identities, reasoning efforts, run/thread IDs, timestamps, decisions, and lineage.
- Separate dataset construction and static validation from Arm A/C scoring, then run one terminal attempt and apply the preregistered gate mechanically.
- Produce raw-count-first artifacts and claims that remain honest on pass, gate failure, infrastructure failure, protocol invalidation, or dataset insufficiency.

**Non-Goals:**

- Human authoring, human review, adjudication, majority vote, reviewer feedback, relabeling, confidence-based selection, or retry after a substantive Agent response.
- Training, mining, threshold changes, seed selection, model/checkpoint changes, Arm B decision use, release, default-router promotion, production/SOTA claims, merge, archive, tag, or deploy.
- Reusing old Phase 16 or pilot-002 tasks, creating pilot-003, a replacement Run 002 attempt, blind-v2-003, or blind-v3.
- Repairing the pre-existing failing Validate workflow at `origin/main` unless this change introduces the failure.

## Decisions

### A superseding Commit A-agent is the only active preregistration

Do not rewrite or amend historical commit `09ba4104…`. Add a later, explicit superseding commit whose preregistration contains `supersedes_commit`, the unchanged `origin/main` authority, the exact changed-file boundary, and a new schema/version. Every generation request, Agent response, smoke receipt, dataset manifest, Commit B check, and evaluation artifact must bind the superseding SHA. No candidate may be generated before it exists.

Alternative rejected: silently editing the existing human protocol or treating uncommitted documentation as authority. Either would erase the chronology or allow data construction before the executable contract is frozen.

### Three fixed Agent roles use sealed, asymmetric inputs

The generator is `gpt-5.6-sol` with reasoning effort `max`; Reviewer A is `gpt-5.6-sol` with `ultra`; Reviewer B is `gpt-5.6-luna` with `max`. Generator invocations have a frozen `1,800`-second timeout and Reviewer invocations have a frozen `900`-second timeout. Commit A-agent embeds the complete canonical system/user prompt text and structured-output schemas in both the protocol and preregistration, binds their SHA-256 hashes, and freezes the transport-retry rule, requested aliases, and required returned-model checks. Unsupported deterministic controls are recorded as `UNAVAILABLE`, never fabricated.

The generator receives only the canonical 16-skill definitions, naturalness/single-primary-skill rules, forbidden leakage terms, and frozen generation quotas. It never receives train, pilot-002, Phase 16, Arm A/C prompts, scores, ranks, review results, or model comparisons.

Each reviewer invocation is a fresh, non-forked, one-candidate session with a unique thread/session ID, empty conversation history, and no imported memory payload. The request-schema whitelist permits only an opaque task ID, prompt, canonical skill definitions, and frozen rubric. It does not permit the generator's labels/rationale, the other review, acceptance quotas/deficits, contamination output, Arm A/C information, or any earlier candidate. Reviewer A's schedule is ascending `sha256("review-a:7170:" + candidate_id)`; Reviewer B's is ascending `sha256("review-b:7171:" + candidate_id)`. Both schedules and every session identity are recorded.

Both reviewers must independently emit `ACCEPT` and independently choose the same gold and negative-skill/none as each other and the generator. Each must also affirm naturalness, one clear primary skill, absence of label leakage, and, when present, a plausible but insufficient negative skill. Any disagreement or substantive schema failure permanently rejects the candidate. There is no adjudicator, majority vote, feedback, or second opinion.

These controls justify the phrase “role-isolated dual-Agent unanimous review,” not “independent expert review.” Same-provider correlation is a disclosed limitation.

### Candidate generation has two bounded rounds

Run 001 started exactly four Generator requests: all four responses were present and schema-valid, one used `candidate_index=0..15`, and three used model-authored indexes `1..16`, so the controller stopped before contamination scan, review, or dataset construction. Its public terminal remains immutable with SHA-256 `74b8e9fb01e008ee40c1f38c65c73a9fde371c615e4689f847ab88887cefa6ea`; no Run 001 response, model score, or private authority is reusable. Run 002 (`router-v2-v4-successor-blind-v2-002`) records replacement reason `HOST_ASSIGNED_CANDIDATE_IDENTITY`.

Round 1 issues 16 requests, one per gold skill, and every successful response contains exactly 16 candidates with 12 negative-labeled proposals and four positive-only proposals. A Generator candidate contains only prompt, declared semantic family, proposed gold, proposed negative/none, language, and concise rationale. The host assigns position `0..15` and an opaque ID derived from Run 002 ID, request SHA-256, position, and prompt; model-authored identity, order, round, and hash fields are prohibited.

After deterministic filtering and dual review, the controller computes deficits only by gold skill and negative/positive-only stratum. If any final stratum is short, one and only one round-2 request is issued for each deficient gold skill. Each response remains fixed at 16 candidates, with its negative/positive-only quota split deterministically in proportion to the two deficits. The generator receives only those numeric deficits; it never receives rejected prompts, rejection reasons, reviewer labels, contamination scores, or Arm A/C output. Every round-2 candidate traverses the same complete contamination scan, fresh Reviewer A session, fresh Reviewer B session, dual `ACCEPT`, and exact three-way agreement path as round 1. If the accepted pool still cannot satisfy every stratum after round 2, the workflow stops at `AGENT_BLIND_V2_DATASET_INSUFFICIENT` before Commit B and before model scoring.

Alternative rejected: open-ended replenishment. It would permit iterative adaptation to reviewer behavior and turn the blind set into a tuned artifact.

### Non-voting contamination checks precede review

Before reviewers see a candidate, deterministic tooling applies UTF-8/schema checks, NFKC plus casefold normalization, exact hashes, token 5-gram Jaccard `>= 0.80`, character 5-gram Jaccard `>= 0.85`, family-ID disjointness, and cosine similarity `>= 0.90` against train, pilot-002, Phase 16, and earlier/current blind-v2 candidates. Semantic embeddings use `sentence-transformers/all-mpnet-base-v2` at revision `e8c3b32edf5434bc2275fc9bab85f82640a19130`, normalized embeddings, prompt-only text, and no Router skill representation. This checker is not Arm A, Arm C, or another evaluated checkpoint; Commit A-agent also binds every materialized model-file hash before generation.

The scanner can only quarantine/reject; it cannot assign gold or negative labels. The selection seed is `7170`. Pairwise conflicts keep the lower generation round, then the lexicographically smaller `sha256("7170:" + candidate_id)`. All scanner inputs, thresholds, and outcomes are hashed. Rejection details are never fed back to the generator or reviewers.

Alternative rejected: an additional LLM contamination judge. That would create an unapproved third reviewer and another correlated decision surface.

### Accepted-set selection is mechanical

After exact three-way agreement, select eight tasks per gold skill—six negative-labeled and two positive-only—by ascending lexicographic `sha256("7170:" + candidate_id)` within each stratum. Confidence and rationale never affect selection. The 128 selected tasks must have unique task IDs, prompt bytes, normalized prompts, and semantic-family IDs. If deterministic selection cannot satisfy these constraints, the dataset is insufficient rather than manually repaired.

Raw generation, reviews, and contamination ledgers remain under an absolute private Run 002 root outside every Git worktree. Before the synthetic canary or any formal call, that root contains an immutable `run002-authority-manifest.json` binding Commit A, Run 002, prompt/schema/config hashes, retry rules, and selection authority. The complete private staging contract then contains that manifest plus `blind-v2-generation.jsonl`, `blind-v2-review-a.jsonl`, `blind-v2-review-b.jsonl`, `blind-v2-contamination.jsonl`, and `agent-run-metadata.json`. Pack validation replays exact schedules, request quotas, host identities, retry records, globally unique sessions, frozen contamination results, clean-only reviewer schedules, and deterministic selection from source responses; ledger decisions are not accepted as authority. Commit B publishes the final task prompts and labels plus canonical review/config/run hashes and summaries, but not hidden reasoning or unsanitized Agent traces.

### Retry is limited to transport failure or invalid JSON and remains fail-closed

An Agent call may be retried once only if no syntactically valid response was received because of a recorded transport failure or invalid JSON. The retry must use byte-identical input, model alias, reasoning effort, and prompt hash. A returned model mismatch, wrong candidate count, valid-JSON schema/semantic failure, label disagreement, refusal, or rubric failure is substantive and receives no retry. No fallback model or lower reasoning effort is allowed.

Before generation, dummy non-evaluation text must prove all three exact Agent configurations are callable. Failure stops without candidate generation and records `AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE` with `failure_stage=agent_config_smoke`. The A/C fixed-string model-load smoke is deliberately deferred until after Commit B so no Arm A/C model is loaded before the dataset freeze.

### Commit B is a byte-bound 128/96 dataset freeze

After all static checks pass, create exactly `blind-v2-tasks.jsonl`, `blind-v2-review-summary.json`, and `blind-v2-manifest.json` under `data/router-v2-blind-v2-successor-002/`. The manifest binds Run 002 Commit A, source-ledger hashes, prompt/schema/config hashes, requested and returned model IDs, reasoning efforts, run/thread IDs, retry records, contamination evidence, candidate/rejection/acceptance counts, selection seed/order, `task_count=128`, `negative_labeled_task_count=96`, `family_count=128`, `human_author_count=0`, `human_reviewer_count=0`, `model_scores_observed=false`, and `evaluation_started=false`.

Commit B precedes all Arm A/C scoring and is a direct child of Commit A-agent containing only the canonical three dataset files. After Commit B, tasks, labels, review decisions, gate, model, query builder, skill builder, and checkpoints are immutable.

### Synthetic smokes are non-benchmark and respect the data/model boundary

The Agent-configuration smoke runs after Commit A-agent but before generation, uses only dummy text, and records requested/returned model identities and reasoning efforts. The model-load smoke runs only after clean Commit B, safely verifies and loads Arm A plus Arm C seeds `7170/7171/7172` on CPU, encodes only the two preregistered synthetic strings, verifies dimensions and finite values, and deletes temporary files. Neither smoke may emit routing scores or write an evaluation attempt; the A/C smoke may read only Commit B authority and never the private raw Agent ledgers.

### One exclusive terminal evaluation attempt

From clean Run 002 Commit B, create a fresh worktree and the unique namespace `artifacts/router-v2-blind-v2/router-v2-v4-successor-blind-v2-002/`. Write the exclusive started marker before inference. Once it exists, every exit writes or preserves a terminal artifact and consumes the attempt; there is no automatic rerun, replacement namespace, or failed-seed retry.

Only Arm A and Arm C seeds participate. Each task receives one untimed warm-up immediately before its timed pass, and scores use pilot-002's eight-decimal `ROUND_HALF_EVEN` quantization before skill-ID tie breaking. Any infrastructure failure after the marker yields `AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE` and requires a separately preregistered future experiment rather than mutation of this run.

### Statistics inform confidence but do not change the gate

Report raw counts, rates, ranks, latency, paired outcomes, per-task ranks, per-skill/negative/family slices, per-seed deltas, mean, and sample standard deviation. Use exact paired McNemar tests for Recall@1 and Negative Hit@5. Use paired bootstrap with 10,000 resamples and seed `7170` for MRR, NDCG@5, and NHR@5 deltas. Repeated seed evaluations of the same 128/96 tasks are explicitly not independent samples.

### Terminal states and public claims are bounded

Before evaluation, the workflow may report `AGENT_BLIND_V2_READY_FOR_GENERATION` or `AGENT_BLIND_V2_READY_FOR_FORMAL_ATTEMPT`. Terminal states are `AGENT_BLIND_V2_DATASET_INSUFFICIENT`, `AGENT_BLIND_V2_PROTOCOL_INVALID`, `AGENT_BLIND_V2_INFRASTRUCTURE_INCONCLUSIVE`, `AGENT_BLIND_V2_GATES_PASSED`, and `AGENT_BLIND_V2_GATES_NOT_PASSED`.

Every terminal state, including dataset insufficiency, protocol invalidation, and infrastructure failure before or after the formal marker, sets `router_decision=KEEP_BASELINE`, `production_ready=false`, `release_authorized=false`, and `default_router_unchanged=true`. Passing may be described only as meeting the preregistered gate on an Agent-generated set accepted by two role-isolated OpenAI reviewers with unanimous labels. It is not human-reviewed evidence, statistical independence, production evidence, or proof of human-task generalization.

## Risks / Trade-offs

- **Same-provider correlation** → Disclose all three OpenAI configurations and use role/input isolation; do not call the reviewers statistically independent.
- **Generator distribution bias** → Freeze quotas/prompts before data and restrict conclusions to the Agent-constructed distribution.
- **Reviewer disagreement may shrink the set** → Start with 2× per-stratum candidates, allow one deficit-only round, then stop without lowering standards.
- **Semantic contamination detection is imperfect** → Combine exact, normalized, lexical, family, and frozen non-router embedding checks; preserve thresholds and hashes.
- **Raw Agent traces may contain hidden reasoning or sensitive runtime data** → Keep them outside Git; commit sanitized summaries and tamper-evident hashes only.
- **One attempt can be consumed by infrastructure failure** → Run the Agent-configuration smoke before generation, freeze Commit B before loading A/C, then run the A/C model smoke and revalidate every authority before the exclusive marker.
- **Current main CI is already red** → Preserve exact baseline evidence, use focused attribution, and never claim a green full suite without fresh proof.
- **Larger dedicated implementation** → Limit implementation to the existing two source modules, one CLI, two test files, protocol, preregistration, and this OpenSpec change; do not build a generic framework.

## Migration Plan

1. Update and approve these OpenSpec artifacts without touching implementation, protocol, preregistration, candidates, or evaluation state.
2. Under a separately approved implementation plan, add RED tests and replace the human 64/48 contract with the Agent-only 128/96 contract in the existing dedicated modules.
3. Update the protocol and preregistration, run validations and read-only review, then create the superseding Commit A-agent only after explicit commit authorization.
4. Run the exact Agent-configuration smoke. Stop before generation on failure.
5. Generate, quarantine, and dual-review candidates outside Git; send every round-2 candidate through the same full pipeline and stop if two rounds cannot satisfy the frozen strata.
6. Freeze the selected set as Commit B before loading Arm A/C.
7. On clean Commit B, run the A/C fixed-string model-load smoke, then run the single formal attempt, produce terminal artifacts, and update only result-facing public surfaces.
8. Validate, obtain read-only review, and stop before push/PR unless separately authorized. Rollback is branch abandonment; historical models, data, pilots, default router, and releases remain untouched.

## Open Questions

None. Agent aliases/reasoning efforts, timeouts, semantic model/revision/thresholds, lexical thresholds, selection seed/order, and reviewer schedule order are fixed above. The canonical prompt and schema bodies must be written verbatim into both the protocol and preregistration, reviewed, hashed, and committed in Commit A-agent before any candidate generation; implementation planning may transcribe this contract but cannot choose different values.
