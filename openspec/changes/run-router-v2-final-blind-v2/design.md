## Context

Router V2 pilot-002 is frozen and merged through PR #38. Its canonical evidence binds 64 training positives, 52 model-adjudicated hard negatives, Arm A and Arm C checkpoints for seeds `7170`, `7171`, and `7172`, and one 16-positive/9-negative-label held-out attempt. The result was internally positive but remains `MODEL_ONLY_PILOT`, `KEEP_BASELINE`, non-production, and not blind-v2 evidence.

The final research question is intentionally narrower than another model-development phase: evaluate the unchanged Arm C checkpoints once on a larger, externally authored and independently human-reviewed 64/48 pack. The old pilot runner cannot be edited into this role because its contracts deliberately bind 16/9, A/B/C, pilot-002 paths, and `blind_v2_run=false`.

The repository is OpenSpec-managed. This is the only new change. The user explicitly forbids a new Phase number, Human Brief, dashboard, generic qualification framework, additional model review, retraining, post-hoc tuning, blind-v3, and edits to historical pilot artifacts.

## Goals / Non-Goals

**Goals:**

- Freeze protocol, evaluator code, model/data authority, metrics, statistics, gate, and non-actions before reading blind-v2 data.
- Accept only an external human-authored pack with independent human review and exact 64/48/16-skill/64-family constraints.
- Separate static data validation from model scoring and preserve prompt privacy when publication permission is absent.
- Run one terminal Arm A versus Arm C attempt, retain failure evidence, and apply the preregistered gate mechanically.
- Produce raw-count-first, per-seed, aggregate, paired, statistical, failure-slice, and lineage artifacts that remain honest on pass, fail, infrastructure failure, or missing data.

**Non-Goals:**

- Training, mining, adjudication, relabeling, threshold changes, seed selection, model/checkpoint changes, Arm B decision use, release, default-router promotion, production claims, SOTA claims, merge, archive, tag, or deploy.
- Reusing old Phase 16 or pilot-002 tasks as blind-v2, creating pilot-003, attempt-2, blind-v2-002, or blind-v3.
- Repairing the pre-existing failing Validate workflow at `origin/main` `8f6a21e53c1363ee18ea6d6e3db1f4b3805ff552` unless a failure is introduced by this change.

## Decisions

### Dedicated blind-v2 contract and runner

Add `router_v2_blind_v2_evaluation.py` and `router_v2_blind_v2_evaluation_runner.py` plus one narrow script. Reuse only stable primitives such as canonical hashing, eight-decimal serialization, nearest-rank percentiles, sample standard deviation, frozen model metadata, and the prompt-only/skill-text builders. Do not modify pilot-001/002 code or artifacts.

Alternative rejected: adapting the pilot replay runner. It would require changing frozen 16/9 and `blind_v2_run=false` assumptions and risks making the old attempt look mutable.

### Commit A freezes executable protocol before data access

Commit A contains the OpenSpec artifacts, protocol document, focused tests, dedicated contract/runner/CLI, and preregistration JSON. The preregistration binds its parent/base commit and `origin/main`, exact source-file hashes, model manifests/files, training inputs, skill index, query/skill representation contracts, pilot-002 gate artifact, 64/48 counts, one-attempt policy, and all forbidden post-data actions. This avoids modifying evaluator semantics after observing blind-v2.

The JSON records `blind_v2_data_seen=false`; checking whether the environment variable exists is deferred until after Commit A and the synthetic smoke.

### External human pack is read once for static validation before scoring

`HERMES_BLIND_V2_ROOT` MUST resolve outside every Git worktree and contain the authored CSV, independent-review CSV, and reviewer metadata JSON. The validator first reads bytes, hashes them, validates UTF-8/schema/keys/identities/agreement/counts/distributions/leakage/exact overlap/normalized near-duplicate/family disjointness, and emits no model score.

Ambiguous-primary-skill and semantic-family judgments remain human assertions bound to reviewer evidence; code validates agreement and declared uniqueness but MUST NOT adjudicate human disagreement. Any rejected or invalid row reduces the accepted count and causes a stop until humans supply replacements.

If the pack is missing or incomplete, generate only blank templates and a human guide under `/tmp/hermes-blind-v2-authoring-pack/`, report the full 64/48 deficit, and stop at `BLIND_V2_WAITING_FOR_HUMAN_DATA`.

### Commit B is a byte-bound dataset freeze

After static validation passes, create exactly three files under `data/router-v2-blind-v2/`. When publication permission is true, the task JSONL contains prompts; otherwise it contains row hashes and non-sensitive distributions only. The manifest binds source bytes, review counts, overlap results, first-read timestamp, Commit A, and `model_scores_observed=false` / `evaluation_started=false`.

Commit B precedes all model scoring. After Commit B, dataset, reviewer decisions, gate, model, query builder, skill builder, and checkpoints are immutable.

The freeze and evaluate entry points accept only repository root plus the preregistration path. They derive the external pack from `HERMES_BLIND_V2_ROOT` and every repository input/output from frozen paths. If prompts are private, evaluation revalidates the external bytes and exactly regenerates all Commit B documents before any model load.

### Synthetic smoke is non-benchmark and A/C-only

Before checking the human pack, safely materialize the Arm A Hugging Face snapshot into a private temporary directory, verify all frozen model files, load Arm A plus Arm C seeds `7170/7171/7172` on CPU, encode the two preregistered synthetic strings, verify dimension consistency and finite values, and delete the temporary directory. It MUST NOT write an evaluation attempt or read blind data.

### One exclusive terminal attempt

From clean Commit B, create a fresh worktree and the namespace `artifacts/router-v2-blind-v2/router-v2-v4-final-blind-v2-001/attempt-1`. The started marker is created with exclusive/no-replace semantics before model inference. Once it exists, every exit writes or preserves a terminal artifact and consumes the attempt. Output-root identity and exact Commit A/B ancestry/changed-file guards prevent caller substitution or writes into training roots and old artifact namespaces. Each task receives one untimed warm-up immediately before its timed pass, and scores use pilot-002's eight-decimal `ROUND_HALF_EVEN` quantization before skill-ID tie breaking.

Only Arm A and Arm C seeds participate. Arm B may execute only if an unavoidable shared encoder contract requires it, and it is excluded from every gate and research conclusion.

### Statistics inform confidence but not the gate

Report raw counts, rates, ranks, latency, paired outcomes, per-task ranks, per-skill/negative/family slices, per-seed deltas, mean and sample standard deviation. Use exact paired McNemar tests for Recall@1 and Negative Hit@5. Use paired bootstrap with `10,000` resamples and seed `7170` for MRR, NDCG@5, and NHR@5 deltas. Repeated seed evaluations of the same tasks are explicitly not independent samples.

### Mechanical conclusions and frozen default

All preregistered gates passing yields `BLIND_V2_GENERALIZATION_SUPPORTED`; any gate failure yields `BLIND_V2_NOT_SUPPORTED` plus `KEEP_BASELINE`; infrastructure failure yields `BLIND_V2_INCONCLUSIVE_INFRASTRUCTURE_FAILURE`. Every path keeps `production_ready=false`, `release_eligible=false`, and `default_router_unchanged=true`.

## Risks / Trade-offs

- **Current main CI is already red** → Record the exact baseline `1155 passed, 25 failed` and Validate run `29433191147`; use focused blind-v2 tests and diff attribution, and do not claim a green full suite unless fresh evidence changes.
- **Human pack may not exist** → Commit A and smoke remain useful; generate blank materials and stop without inventing labels.
- **Semantic ambiguity cannot be proven mechanically** → Require independent human agreement and non-empty reasons; fail closed on disagreement rather than Codex adjudication.
- **Private prompts may be non-public** → Commit only hashes and aggregate distributions when permission is false.
- **One attempt can be consumed by infrastructure failure** → Preflight every hash, path, dependency, count, marker, and output namespace before the exclusive started marker.
- **Latency is environment-sensitive** → Use identical CPU device, model loading, order, warm-up, timer, and repeats for A/C; report absolute latency and ratios without changing the gate.
- **Large dedicated implementation** → Keep exactly two source modules, one script, and two test files; avoid reusable-framework abstractions.

## Migration Plan

1. Create Commit A from current `origin/main` with protocol, code/tests, and preregistration while blind data remains unseen.
2. Run the A/C synthetic smoke. On failure, stop before checking the human pack.
3. Check `HERMES_BLIND_V2_ROOT`; generate blank materials and stop if missing/incomplete.
4. Validate and freeze the human pack as Commit B without model scoring.
5. Run the single attempt from a fresh clean Commit B worktree, produce final artifacts, and update only result-facing public surfaces.
6. Validate, run a read-only Reviewer, push, and open one PR. Rollback is branch/PR abandonment only; old models, data, pilots, default router, and releases remain untouched.

## Open Questions

None before Commit A. Human publication permission and the existence/completeness of the external pack are runtime inputs that are intentionally not inspected before preregistration and smoke.
