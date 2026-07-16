# Router V2 Final Blind-v2 Protocol

## Research question

Can the already frozen Router V2 Arm C checkpoints preserve gold-skill ranking
and reduce negative-skill risk on a larger blind-v2 that was never used during
development and was authored and independently reviewed by humans?

This is the final Router V2 evaluation, not another model-development phase.
A supported result, an unsupported result, an infrastructure failure, or a
formal stop while waiting for human data all freeze the project. None permits
retraining, post-hoc tuning, relabeling, best-seed selection, or another blind
set.

## Frozen authority before blind-v2 access

- Base branch: `origin/main`
- Preregistration parent: `8f6a21e53c1363ee18ea6d6e3db1f4b3805ff552`
- PR #38: merged by `4b47e4af67f998de0d5be0e52bab04e100bd94cd`
- Training package: 64 positives and 52 model-adjudicated hard negatives
- Seeds: `7170`, `7171`, `7172`
- Pilot-002: 16 positives, 9 negative-labeled tasks, one completed attempt
- Pilot result: `ROUTER_V2_PILOT_IMPROVED`
- Current router decision: `KEEP_BASELINE`
- Blind-v2 before Commit A: not run and not read

The exact model, model-manifest, training-input, skill-index, query-builder,
skill-representation, evaluator, metric, latency, gate, and source hashes are
machine-bound in
`artifacts/router-v2-blind-v2/preregistration.json`. Any mismatch stops the
workflow before blind-v2 access. No mismatch may be repaired by replacing a
checkpoint, rebuilding training artifacts, changing a seed, or rerunning
training.

The current `origin/main` baseline is not fully green: local full pytest is
`1155 passed, 25 failed`, and GitHub Validate run `29433191147` failed at
`8f6a21e…`. Those failures follow the bilingual README rewrite and historical
release-check side effects. This blind-v2 change records but does not hide or
repair that pre-existing baseline.

## Commit order and information barrier

### Commit A: preregistration

Commit A contains this protocol, the dedicated blind-v2 contract/runner/CLI,
focused tests, the single OpenSpec change, and the preregistration. It is
created before checking `HERMES_BLIND_V2_ROOT` and before opening any blind-v2
prompt or label.

`preregistration.json` records its parent commit to avoid a self-referential
Git hash. The resulting Commit A SHA is recorded after commit creation and is
later bound by Commit B and the final lineage manifest.

The preliminary pre-data Commit A revisions
`f75c8686a611fa5f0e3c5fa4c3ff20e0a59e6a17` and
`9253771a424c890e161265081d188231c79a92c5`, followed by
`1fbe1fd721d420b7652241269350cd9032ec91a4` and
`43d3115ecf21c3740fd9ed72fc929c794c3575ae`, were superseded before any
blind-v2 data access after read-only reviews found incomplete evaluator,
single-attempt, freeze, warm-up/quantization, and lineage authority checks. The
environment root was unset, no blind-v2 prompt or label was read, and this
amended Commit A is the sole preregistration authority for any later human-pack
freeze or attempt.

### A/C-only synthetic real-load smoke

After Commit A, verify hashes and sizes, safely materialize the Arm A Hugging
Face snapshot into a private temporary directory, and load:

- Arm A frozen MiniLM once;
- Arm C seed 7170;
- Arm C seed 7171;
- Arm C seed 7172.

All models use CPU and encode only:

```text
synthetic blind-v2 model load query
synthetic blind-v2 skill description
```

The smoke checks finite, equal-dimension normalized embeddings and deletes the
temporary directory. It reads no blind-v2 data, produces no benchmark metric,
and creates no attempt marker. Any failure stops the workflow before the human
pack is checked.

A canonical tamper-evident receipt under
`/tmp/hermes-router-v2-blind-v2-smoke-receipts/<commit-a>.json` binds the clean
Commit A, preregistration semantic hash, fixed strings, exact A/C grid, device,
dimension, and the two false data/metric flags. Formal evaluation requires this
exact receipt before re-reading the external human pack; it is not an attempt
artifact and contains no prompt, label, rank, or benchmark result.

### Human-data gate

Only after Commit A and smoke may the workflow check the absolute external
path in `HERMES_BLIND_V2_ROOT`. The directory must be outside all repository
worktrees and contain:

- `blind-v2-authored.csv`
- `blind-v2-independent-review.csv`
- `reviewer-metadata.json`

Both `pack-status` and `freeze` first validate the clean canonical Commit A,
preregistration authority, and that Commit A's tamper-evident smoke receipt.
Neither command reads the environment root before those checks pass. The only
template destination is `/tmp/hermes-blind-v2-authoring-pack/`; no CLI option
can redirect it.

Codex and model agents must not author, complete, rewrite, polish, adjudicate,
or relabel any prompt, gold skill, negative skill, reviewer identity, decision,
reason, or replacement task.

If the root or a required file is absent, create only blank materials under
`/tmp/hermes-blind-v2-authoring-pack/` and stop at
`BLIND_V2_WAITING_FOR_HUMAN_DATA`. The deficit is 64 authored tasks, 64
independently reviewed tasks, coverage for all 16 canonical skills, and 48
negative-labeled tasks unless humans have supplied a partial pack.

## Static human-pack validation

Static validation occurs before any evaluation model load or routing score. It
requires:

- valid UTF-8 CSV/JSON schemas and no duplicate keys;
- unique task IDs, prompt bytes, NFKC-casefold prompts, and 64 families;
- exactly 64 accepted tasks, 16 skills x 4 tasks;
- exactly 48 negative-labeled tasks, three per gold skill;
- one positive-only task per gold skill;
- one tempting negative per negative-labeled task;
- at least 12 negative targets and no target over six uses;
- canonical gold/negative IDs with gold different from negative;
- `source_type=HUMAN_AUTHORED`;
- a reviewer different from the author for every accepted task;
- exact author/reviewer gold and negative agreement;
- non-empty reviewer confidence and reason;
- reviewer isolation from model rankings and pilot-002 task-level results;
- no skill ID/name or answer-bearing metadata leakage;
- no protected old-data marker, old Phase 16 path, or exact/NFKC-casefold
  overlap with any of the 16 hash-bound Phase 16 prompts;
- no exact or NFKC-casefold overlap with train or pilot-002 prompts;
- no family overlap with train or pilot-002.

Human semantic judgments remain human judgments. Code does not overturn a
reviewer decision or edit a disputed record. Rejected rows reduce the accepted
count; humans must supply replacements until all frozen counts pass.

## Commit B: dataset freeze

After static validation, create exactly:

```text
data/router-v2-blind-v2/blind-v2-tasks.jsonl
data/router-v2-blind-v2/blind-v2-review-summary.json
data/router-v2-blind-v2/blind-v2-manifest.json
```

When publication permission is false, task data contains per-row prompt hashes
and distributions but no prompt plaintext. The manifest binds Commit A, source
bytes, counts, distributions, human role counts, review agreement, exclusions,
overlap checks, first-read time, and these truths:

```text
model_scores_observed=false
evaluation_started=false
retraining_after_data_access=false
gate_changed_after_data_access=false
```

The freeze command takes the human pack only from `HERMES_BLIND_V2_ROOT`,
derives skills and overlap references only from preregistered repository paths,
and writes only the canonical data directory. For private prompts, the formal
evaluator revalidates the same external human bytes and exactly regenerates all
three committed freeze documents in memory before any model load; it never
requires prompt plaintext to be committed.

Commit B is `data(router): freeze human-reviewed Router V2 blind-v2`. After it,
tasks, reviews, models, query/skill builders, checkpoints, gates, thresholds,
seeds, and row selection are immutable.

## Single terminal attempt

Create a fresh clean worktree at Commit B. Revalidate Commit A/B, every A/C
model hash, skill/query/gate/dataset hashes, 64/48 counts, smoke status,
namespace absence, marker absence, and worktree cleanliness.

The only namespace is:

```text
artifacts/router-v2-blind-v2/router-v2-v4-final-blind-v2-001/
```

The exclusive `attempt-1.started.json` marker is written before inference.
After that marker, every failure consumes the attempt. There is no attempt-2,
replacement namespace, blind-v2-002, failed-seed retry, best-seed subset, or
blind-v3. A failure retains started, terminal, and failure evidence and yields
`BLIND_V2_INCONCLUSIVE_INFRASTRUCTURE_FAILURE`.

Only Arm A and Arm C seeds enter the comparison. Arm B is absent from the gate.
All rows use ascending task ID, the same CPU device, model-loading pattern,
prompt-only query, frozen skill text, one per-query warm-up immediately before
one timed pass, nearest-rank latency percentiles, eight-decimal
`ROUND_HALF_EVEN` score quantization, and deterministic skill-ID tie breaking.

## Metrics and statistics

Per Arm/seed report raw counts and rates for Recall@1 and Recall@5 over 64,
MRR, NDCG@5, raw Negative Hit@1 and @5 over 48, first-negative rank, p50/p95
latency, per-task gold/negative rank, paired wins/losses/ties, and failure slices
by gold skill, negative target, and semantic family.

Aggregate output reports each seed delta, three-seed mean, sample standard
deviation, and pooled repeated counts with an explicit warning that the same
64/48 tasks across seeds are not independent samples.

- Recall@1: exact two-sided paired McNemar test
- Negative Hit@5: exact two-sided paired McNemar test
- MRR delta: paired task bootstrap 95% interval
- NDCG@5 delta: paired task bootstrap 95% interval
- NHR@5 delta: paired task bootstrap 95% interval
- Bootstrap resamples: 10,000
- Bootstrap seed: 7170

Statistics describe uncertainty but never add, remove, or alter a gate.

## Mechanical gate and conclusions

The unchanged pilot-002 gate is:

| Metric | Mean | Every seed |
|---|---:|---:|
| Recall@5 delta | `>= 0` | `>= 0` |
| MRR delta | `>= -0.01` | `>= -0.01` |
| NDCG@5 delta | `>= -0.01` | `>= -0.01` |
| Negative Hit Rate@5 delta | `<= -0.05` | `<= 0` |
| p95 latency ratio | `<= 1.20` | `<= 1.20` |

Every gate passing yields `BLIND_V2_GENERALIZATION_SUPPORTED`. Any gate
failing yields `BLIND_V2_NOT_SUPPORTED` and `KEEP_BASELINE`. Infrastructure
failure yields `BLIND_V2_INCONCLUSIVE_INFRASTRUCTURE_FAILURE`.

Every terminal state keeps:

```text
production_ready=false
release_eligible=false
default_router_unchanged=true
router_promotion_requires_separate_human_decision=true
```

## Required artifacts

The final namespace contains preregistration, blind-v2 manifest, review
summary, started/terminal markers, per-seed, aggregate, paired, statistics,
failure slices, evaluation summary, result report, and a lineage manifest that
hash-binds Commit A/B, evaluator, models, data/review files, skill index, query
contract, gate, attempt token, the exact started marker, the planned/actual
success terminal, and every non-self output artifact. The lineage document has
its own canonical self-hash.

## Explicit non-actions

No training or optimizer step; no mining; no model, loss, sampler, threshold,
gate, seed, label, checkpoint, query, or skill-representation change; no
best-seed selection; no task deletion; no old blind/Phase 16 reuse; no
pilot-003; no retry; no blind-v3; no default-router modification; no SOTA,
production, or release claim; no merge, tag, release, deploy, or archive.
