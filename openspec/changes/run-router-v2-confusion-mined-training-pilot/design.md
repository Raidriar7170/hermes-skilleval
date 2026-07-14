## Context

PR #37 landed the frozen Router V2 v4 `MODEL_ONLY_PILOT` audit without changing
admission: its evidence remains `admission_effect=NONE`,
`can_start_training=false`, and `router_decision=KEEP_BASELINE`. This sibling
change is an internal experiment that may admit a separate training package
without mutating the human-only path, the frozen 192-row source snapshot, or the
PR #37 audit artifacts.

The experiment must answer one question within one preregistered run: does
MiniLM training with baseline-confusion hard negatives outperform the exact
baseline without unacceptable positive-ranking or latency regression? Mining,
review, training, and final non-blind evaluation are separate stages with
content-addressed handoffs.

## Goals / Non-Goals

**Goals:**

- Mine reproducible confusers for exactly 64 frozen train positives against the
  frozen 16-skill index and the exact baseline revision.
- Produce 48-64 model-supported, baseline-hard training negatives through two
  isolated model passes and one adjudication.
- Freeze a separate model-supported `HELD_OUT_EVAL_ONLY` hard-negative label
  artifact without using baseline scores to choose those labels.
- Make the training handoff, skill-unique sampler, preflight, three arms, three
  seeds, metrics, and final decision reproducible and fail closed.
- Preserve exact model-only, non-production, non-release, non-blind truth.

**Non-Goals:**

- Human review, human acceptance, independent human review, or production data.
- Dashboard, qualification layer, Human Brief, third model-review pass, new
  model architecture, blind-v2, old Phase 16, release, or router promotion.
- Changing the frozen source snapshot, the existing human-only change, or the
  PR #37 audit decision.

## Decisions

### One isolated internal namespace

All generated evidence lives below
`artifacts/router-v2-v4/internal-training-pilot/<pilot-id>/`. The internal
package uses its own schema and never writes `review-decisions.csv` or reuses
human qualification vocabulary. Every manifest carries
`review_mode=MODEL_ONLY_PILOT`, `human_reviewer_count=0`,
`model_review_pass_count=2`, `model_adjudication_enabled=true`,
`independent_human_review=false`, `model_correlation_risk=true`,
`release_eligible=false`, and `router_decision=KEEP_BASELINE`.

The admitted internal data manifest additionally carries
`can_start_internal_training=true`,
`can_start_production_training=false`, and `blind_v2_eligible=false`. Those
values do not alter the PR #37 audit, whose admission and training fields remain
false.

### Frozen deterministic mining protocol

Mining reads only train positive rows from snapshot
`router-v2-v4-source-38afe7d5b2500d4a` and the 16-skill index. It rejects any
attempt to read calibration, non-blind-test, Phase 16, or blind-v2 inputs. The
baseline is `sentence-transformers/all-MiniLM-L6-v2` at immutable revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.

CPU inference is single-threaded. Skill text uses the existing frozen
`id + name + category + description + trigger_terms + body` builder. Scores are
quantized to eight decimal places before sorting and thresholding; ties use
ascending `skill_id`. Each row records all 16 scores, gold rank, top-three
non-gold candidates, selected candidate rank, `gold_score-candidate_score`,
model file manifest/hash, source-row hash, prompt hash, and skill-index hash.

A candidate is baseline-hard exactly when `candidate_rank <= 5` or the
quantized score margin is `<= 0.05`. The 35 PR #37 supported hard negatives are
eligible only when they pass this rule; all 29 disputed rows are permanently
excluded. The first new round selects the top non-gold confuser per train
prompt. If the admitted total is below 48, later rounds may add only the next
previously unseen baseline confuser; they never relabel a rejected row or add
an easy negative.

### Two isolated model passes and one adjudication

Only newly mined train candidates and held-out label candidates enter the new
review. Pass 1 and pass 2 have distinct run identities and state that the other
pass output was unavailable. Both use role-compatible opinion vocabularies,
bounded rationales, canonical JSONL, exact source/candidate hashes, and the
truth block. A single adjudication binds the two pass-row hashes. There is no
third pass and no claim of human or statistical independence.

Training admission requires both baseline hardness and an adjudicated
`HARD_NEGATIVE_ROLE_SUPPORTED` opinion. Selection is deterministic, keeps
48-64 rows, and maximizes skill coverage before taking additional rows in
canonical order. If 48 valid rows cannot be obtained, package construction and
training fail closed and report the shortfall.

### Held-out labels are separate and score-blind

Before training, each of the 16 frozen non-blind-test positives receives a
candidate chosen by a deterministic taxonomy/lexical skill-snapshot rule that
does not load or consume baseline scores. Candidates share the same two model
passes and adjudication but use `usage=HELD_OUT_EVAL_ONLY`. Only supported
labels are sealed. They never enter mining, sampler input, embedding training,
or hyperparameter decisions.

Calibration is limited to schema and runtime-integrity preflight. Final
non-blind-test labels and outcomes are read only once after all arms complete.
Blind-v2 is neither read nor run.

### Internal package and deterministic sampler

The training package contains exactly 64 train positives and 48-64 admitted
hard negatives. Calibration, test, no-skill, disputed, ambiguous, unsupported,
and easy-negative rows are excluded. `skill_id` is carried by every validated
example and is included in the example fingerprint, sealed handoff, and handoff
fingerprint.

Sampler version `skill-unique-v1` groups positives by `skill_id`, derives stable
per-skill and per-round RNG streams from seed and epoch, and emits every
positive exactly once per epoch while allowing at most one row for a skill in
an MNRL batch. The canonical batch plan and its SHA-256 are recorded.

Config, run summary, and model manifest bind the data manifest, accepted-pairs
file, mining manifest/artifact, Git commit, exact base-model revision, model
file manifest/hash, seed, sampler version/plan hash, and dependency versions.
`--preflight-only` uses only standard-library/project contract code, does not
import Torch or sentence-transformers, does not query CUDA, and creates no
file, directory, cache, or output side effect.

### Frozen arms, evaluation, and decision gate

Only these arms run with seeds `7170`, `7171`, and `7172`:

- A: exact Base MiniLM, evaluation only.
- B: positive-only V2.
- C: positive plus admitted baseline-confusion hard negatives.

Training uses 3 epochs, batch size 16, learning rate `2e-5`, and contrastive
hard-negative margin `1.5`. Arm B is explanatory only; Arm C versus paired Arm
A is the sole promotion candidate.

Every seed reports Recall@1, Recall@5, MRR, NDCG@5, Negative Hit Rate@1 and @5,
first-negative rank, p50/p95 latency, paired wins/losses, and failure slices.
Aggregates report arithmetic mean and sample standard deviation. The decision
is `ROUTER_V2_PILOT_IMPROVED` only when all of the following hold for both the
three-seed mean and each paired seed where stated:

- Recall@5 delta is at least `0.00` for the mean and every seed.
- MRR and NDCG@5 deltas are each at least `-0.01` for the mean and every seed.
- Negative Hit Rate@5 mean delta is at most `-0.05`, and every seed delta is at
  most `0.00`.
- The mean and every-seed p95 latency ratios are at most `1.20`.

Any failure yields `KEEP_BASELINE`. Gates are serialized before held-out
evaluation and cannot be changed after results are read.

## Risks / Trade-offs

- Two passes can share correlated model errors: every artifact states
  `model_correlation_risk=true` and remains ineligible for release.
- Sixteen held-out rows make percentage changes coarse: raw per-row ranks and
  paired outcomes are retained, and thresholds are not relaxed.
- CPU/GPU floating point can drift: mining is CPU-only with pinned versions and
  eight-decimal quantization; training/evaluation records exact dependencies
  and hardware.
- Fewer than 48 candidates may survive: the pipeline supplements only new
  baseline confusers and otherwise stops without training.
- Latency is noisy: all paired arms use the same device, warmup, query order,
  and measurement procedure, with raw timings retained.

## Execution Plan

1. Implement and validate deterministic mining/review/package contracts.
2. Generate the first mining round and run two isolated model passes plus one
   adjudication; supplement only if fewer than 48 rows survive.
3. Seal the internal package and held-out labels, then run side-effect-free
   preflight.
4. Inspect live A100 occupancy, choose one idle GPU explicitly, and run the
   frozen A/B/C by three-seed matrix under `/mnt/data/minghongsun`.
5. Read non-blind-test once, evaluate, apply the serialized gate, and publish
   only the allowed conclusion and conservative README/resume wording.

Rollback removes only this sibling change and internal pilot namespace. It
does not alter frozen sources, PR #37 evidence, human-review state, releases,
or blind evidence.

## Open Questions

None. The user explicitly approved the separate `HELD_OUT_EVAL_ONLY` artifact.
