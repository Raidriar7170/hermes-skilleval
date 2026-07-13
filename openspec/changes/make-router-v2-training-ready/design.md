## Context

Router V2 has a prompt-only query boundary and a fail-closed v3 training-input
gate, but its committed qualification pack remains diagnostic-only:
`REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`. The merged
baseline at `8e0dc41655555f44e4c5dde6047c8f2c18fa544c` contains no reviewed v4
source, family-disjoint split, accepted-pair package, skill-unique batch plan,
or side-effect-free training preflight.

This change closes those prerequisites in guarded stages. The first stage is an
immutable, pre-review source snapshot. It must stop after its exact commit when
no completed human decision file exists. Later stages may import explicit human
decisions, build a reviewed package, and run a standard-library-only preflight,
but even the final `TRAINING_READY_PRECHECK=PASS` state is not authorization to
train, use a GPU, create a checkpoint, rerun blind evaluation, or change
`KEEP_BASELINE`.

The canonical skill universe is the 16-row Skill Index at
`docs/demo/phase9-real-skill-library-migration/skills.json`. That index is an
input taxonomy and provenance anchor, not a training dataset. Phase 14-18,
blind trees, v3 qualification artifacts, public prompts, and release artifacts
are protected historical evidence and remain byte-for-byte unchanged.

## Goals / Non-Goals

**Goals:**

- Freeze exactly 192 deterministic `PENDING_REVIEW` v4 source records with
  balanced 16/16 skill coverage, explicit family-disjoint splits, and exact-byte
  provenance.
- Make human review an explicit file boundary with no inferred decision,
  reviewer, reason, identity, or acceptance.
- Build a reviewed v4 package only from a valid immutable snapshot and complete
  human decisions, with qualification minimums checked independently.
- Preserve and authenticate `skill_id` through the sealed training handoff,
  reject invalid Unicode as `TRAINING_INPUT_INVALID`, and plan deterministic
  skill-unique positive batches for Multiple Negatives Ranking Loss.
- Bind complete training lineage and expose a `--preflight-only` command that
  proves readiness without importing model frameworks or causing output/GPU
  side effects.

**Non-Goals:**

- No model/framework import during preflight, model load, GPU/A100 access,
  training, checkpoint, threshold selection, blind-v2 work, or performance
  claim.
- No mutation of v3 machine artifacts, Phase 14-18, blind data, canonical task
  manifests, public prompts, release decision, or default router.
- No generated or model-assisted human review, inferred acceptance, automatic
  continuation past the source snapshot, Human Brief, dashboard, release
  evidence, archive, tag, release, deploy, or phase numbering.
- No claim that `TRAINING_READY_PRECHECK=PASS` means trained, improved,
  promotable, or production-ready.

## OpenSpec Dependency

`harden-router-v2-pretraining-contracts` is complete in code but remains an
active, unsynced OpenSpec change. Its deltas introduce the base
`router-training-input-gate` and
`router-training-data-v2-qualification-pack` capabilities that this change
extends. Source commit A neither syncs nor archives either change. Before a
later sync/archive of this upper change, the lower change must be reviewed and
synced/archived first under separate authorization, followed by strict
revalidation of these v4 deltas against the new main specs.

## Decisions

### 1. Use one change with explicit irreversible stage gates

The change has five ordered stages:

1. **Source freeze:** author and validate the draft catalog, then write
   `source-candidates.jsonl`, `source-manifest.json`, and `review-queue.csv`
   under `data/router-v2-v4/`. All source rows are `PENDING_REVIEW`; the three
   human fields exist and are empty strings. `review-decisions.csv` is not
   generated.
2. **Human review import:** a person copies the queue to
   `review-decisions.csv` and supplies an allowed decision, reviewer, and reason
   for every row. Import validates every non-human byte against the frozen
   snapshot and never edits the snapshot.
3. **Reviewed package:** accepted/remapped rows, split manifest, qualification
   report, and training-input manifest are built atomically only after all
   review and minimum gates pass.
4. **Preflight implementation:** admission, batch planning, and the
   standard-library bootstrap are implemented and exercised with temporary
   synthetic packages and temporary Git repositories. These tests cannot mint
   the canonical PASS artifact.
5. **Reviewed integration freeze and real preflight:** after independent review,
   the workflow stops and requests exact authorization for reviewed-package
   commit B. Only that separately authorized commit may contain the completed
   decision/package/runtime slice. A fresh worktree at commit B must be clean
   before the real trainer entry point validates the complete package, lineage,
   skill-unique batches, and runtime configuration in `--preflight-only` mode,
   then exits. Full training remains outside this change's execution authority.

This staged design is preferred to a single end-to-end builder because it makes
the human boundary observable and prevents a successful source generation from
silently becoming acceptance. Pure manually maintained final artifacts were rejected
because they would not independently reproduce hashes, split checks, and queue
bytes.

### 2. Separate authoring rows from immutable source records

`source-draft.jsonl` is an explicitly authored pre-review catalog. In the first
slice it is authored by the implementing Codex agent from the approved source
constraints; authoring is not human review or row-level approval. It contains
exactly 128 prompt drafts:

- 64 train positive drafts, four per canonical skill, each with one explicitly
  selected same-category hard-negative skill;
- 16 calibration positives, one per canonical skill;
- 16 non-blind-test positives, one per canonical skill;
- 16 calibration no-skill drafts; and
- 16 non-blind-test no-skill drafts.

The builder expands each train positive draft into one positive source record
and one hard-negative candidate record. Other drafts expand one-to-one. The
result is exactly 192 rows: 64 train positives, 64 train hard-negative
candidates, 16 calibration positives, 16 non-blind-test positives, and 32
evaluation no-skill candidates. `positive_skill_id` owns the source prompt:
each canonical value owns exactly four train positives, one calibration
positive, one test positive, and the four hard-negative candidates expanded
from its train drafts. `skill_id` is the candidate identity shown to review and
later used for supervision: for a positive it equals `positive_skill_id`; for a
hard-negative candidate it is the distinct same-category target; for a no-skill
row both values are `null`. Across the 64 hard-negative rows, every canonical
`skill_id` target occurs exactly four times. No category or family is inferred
from prompt text.

The draft row has exactly these keys:

`schema_version`, `draft_id`, `prompt_family_id`, `split`, `draft_role`,
`positive_skill_id`, `hard_negative_skill_id`, and `prompt_text`.

`schema_version` is `router-v2-reviewed-source-draft-v1`; `draft_role` is
`SKILL_POSITIVE` or `NO_SKILL`; and the split is `train`, `calibration`, or
`non_blind_test`. `draft_id` and `prompt_family_id` match
`[a-z0-9][a-z0-9-]*` and are declared, unique stable identities rather than
array positions. `positive_skill_id` is non-null only for `SKILL_POSITIVE`.
`hard_negative_skill_id` is non-null only for train `SKILL_POSITIVE` drafts.

The generated source row has exactly these keys:

`schema_version`, `artifact_version`, `policy_id`, `source_record_id`,
`draft_id`, `task_id`, `prompt_family_id`, `split`, `source_role`,
`positive_skill_id`, `skill_id`, `query_text`, `query_text_policy`,
`prompt_text_sha256`, `skill_record_sha256`, `source_kind`,
`source_artifact_path`, `source_draft_line_sha256`, `status`, `decision`,
`reviewer`, and `reason`.

The three `source_role` values are `POSITIVE`, `HARD_NEGATIVE_CANDIDATE`, and
`NO_SKILL_CANDIDATE`. `task_id` equals `draft_id`. `source_record_id` is derived
exactly as `<draft_id>:positive:<skill_id>`,
`<draft_id>:hard-negative-candidate:<skill_id>`, or
`<draft_id>:no-skill`. The first two components and skill IDs already exclude
colon, so this derivation is unambiguous. `source_kind` is
`ROUTER_V2_V4_AUTHORED_DRAFT`; `source_artifact_path` is
`data/router-v2-v4/source-draft.jsonl`; `query_text_policy` is `prompt_only`;
and the source row schema/policy are
`router-v2-reviewed-source-record-v1` and
`router-v2-reviewed-source-policy-v1` with integer artifact version `1`.
For a non-null candidate `skill_id`, `skill_record_sha256` hashes the compact,
sorted-key, `ensure_ascii=false` JSON serialization of that exact parsed Skill
Index object; it is `null` for a no-skill row.

The draft is retained inside the snapshot directory and bound by the manifest.
The generated source rows, not the mutable review CSV, are the authoritative
pre-review records.

### 3. Make family and duplicate checks deterministic and fail closed

Every draft declares a stable non-empty `prompt_family_id` and exactly one of
`train`, `calibration`, or `non_blind_test`. A family ID may occur only in one
split. The two train records expanded from one draft intentionally share the
same family and prompt; no other prompt reuse is allowed.

Exact duplicate detection compares UTF-8 prompt bytes at the draft level.
Source-draft prompts must be one-line printable ASCII (`U+0020` through
`U+007E`) with no leading/trailing whitespace and no repeated whitespace; this
keeps the pre-review lexical guard identical on supported Python 3.11+ Unicode
databases while the later v4 admission gate still validates arbitrary strict
Unicode. Near-duplicate detection applies Unicode NFKC, casefolding, maps every
character outside ASCII `a-z` and `0-9` to one ASCII space, collapses each run
and strips both ends, then takes the set of every contiguous five-character
substring, including internal spaces. Jaccard is `|A intersection B| / |A union
B|`. Two different drafts whose similarity is at least `0.85` fail source
validation. Empty normalized text or fewer than five normalized characters also
fails. The manifest records algorithm ID
`ascii-nfkc-casefold-char5-jaccard-v1`, threshold `0.85`, Python version, and
`unicodedata.unidata_version`.

The builder never opens a protected prompt. A separate protection test parses
only the repository's known prompt-bearing fields/files, extracts each
protected prompt string in memory, hashes that string's exact UTF-8 bytes, and
compares it with each draft prompt hash solely to reject exact reuse. Hashing a
whole containing file is insufficient. The test reports only colliding path and
draft IDs and does not expose protected text or digests to the builder, source
manifest, review queue, mining, calibration, or selection. Semantic or
near-duplicate comparison against protected prompts is prohibited.

### 4. Bind canonical bytes instead of trusting copied hashes

JSON objects use UTF-8, `ensure_ascii=false`, sorted keys, compact separators,
and one `\n` after every JSONL row. CSV uses the Python standard-library
`excel` dialect with `lineterminator="\n"`, minimal quoting, a fixed column
order, UTF-8 without BOM, and `\n` line endings.
Rows are sorted by split order, prompt family, source role, and source record
ID. Stable IDs are derived from declared authoring IDs, never from array
position alone.

The queue column order is exactly:

`source_record_id`, `source_record_exact_bytes_sha256`, `draft_id`, `task_id`,
`prompt_family_id`, `split`, `source_role`, `positive_skill_id`,
`positive_skill_name`, `skill_id`, `skill_name`, `skill_category`,
`skill_description`, `query_text`, `prompt_text_sha256`, `status`, `decision`,
`reviewer`, `reason`.

Null source-row skill identities become empty CSV cells; canonical display
values come only from the bound Skill Index. Every other queue cell is an exact
copy or deterministic display projection of the source record.

`source-manifest.json` binds the exact bytes and byte sizes of the canonical
Skill Index, source draft, source candidates, and initial review queue. It also
binds each draft line and source-candidate line by stable ID and SHA-256, the
prompt hash, family, split, role, and skill identity. Validators recompute every
hash and count from bytes; a producer-supplied digest is never accepted without
recomputation.

The manifest has exactly these top-level keys:

`schema_version`, `artifact_version`, `policy_id`, `snapshot_id`, `ordering`,
`duplicate_policy`, `runtime`, `inputs`, `outputs`, `counts`,
`skill_distribution`, `records`, and `non_actions`.

`inputs.skill_index` and `inputs.source_draft` each have exactly `path`,
`sha256`, `byte_size`, and `row_count`. `outputs.source_candidates` and
`outputs.review_queue` have the same four keys. Each `records` entry has exactly
`source_record_id`, `draft_id`, `draft_line_sha256`,
`source_record_exact_bytes_sha256`, `prompt_text_sha256`, `prompt_family_id`,
`split`, `source_role`, `positive_skill_id`, and `skill_id`. `ordering` names
the split order `train`, `calibration`, `non_blind_test`, role order `POSITIVE`,
`HARD_NEGATIVE_CANDIDATE`, `NO_SKILL_CANDIDATE`, and sort keys `split`,
`prompt_family_id`, `source_role`, `source_record_id`. `duplicate_policy` has
exactly `algorithm_id` and `threshold`. `counts` has exactly `total`,
`train_positive`, `train_hard_negative_candidate`, `calibration_positive`,
`non_blind_test_positive`, `calibration_no_skill_candidate`, and
`non_blind_test_no_skill_candidate`. `skill_distribution` has exactly
`train_positive_by_skill`, `calibration_positive_by_skill`,
`non_blind_test_positive_by_skill`, `hard_negative_owner_by_skill`, and
`hard_negative_target_by_skill`. `non_actions` is the sorted list
`accepted_pairs`, `archive`, `blind_v2`, `checkpoint`, `dashboard`, `deploy`,
`gpu_access`, `human_brief`, `model_training`, `preflight`, `release`,
`review_decisions`, `router_promotion`, `tag`, `threshold_tuning`, and
`training_input`. Unknown or missing keys at any declared exact-shape level
fail.

`runtime` has exactly `python_version` and `unicode_data_version`, populated
from `platform.python_version()` and `unicodedata.unidata_version`. These are
recorded diagnostics; printable-ASCII prompt constraints keep normalization
results independent of their values. Candidate and queue bytes are therefore
runtime-independent. Manifest byte identity is conditioned on these two
runtime identifiers; a regeneration under different supported versions may
differ only in the exact `runtime` object. Both `draft_line_sha256` and
`source_record_exact_bytes_sha256` hash the canonical JSON object bytes plus
that row's terminating LF byte.

`snapshot_id` is `router-v2-v4-source-` plus the first 16 lowercase hex
characters of SHA-256 over exact Skill Index bytes, one NUL byte, exact draft
bytes, one NUL byte, and UTF-8 policy ID bytes in that order.
The manifest schema, artifact version, and policy are exactly
`router-v2-source-snapshot-manifest-v1`, integer `1`, and
`router-v2-reviewed-source-policy-v1`. Its input/output paths are exactly the
canonical repository-relative Skill Index and the three files under
`data/router-v2-v4/`; alternate paths are allowed only in isolated
regeneration tests and must serialize the same canonical logical paths.

The source snapshot is immutable after commit A. Later commands accept an exact
source-snapshot commit/hash identity and refuse a dirty or mutated snapshot.

### 5. Treat the review queue as a controlled copy boundary

`review-queue.csv` contains all stable source identity, exact-byte hash,
display fields, and the final columns `decision`, `reviewer`, and `reason`.
Those three columns are present and exactly empty in the frozen queue. The
builder does not write `review-decisions.csv`.

The human decision importer requires a completed decision row for every frozen
source row, exact header and row count, unique source IDs, byte-equivalent
non-human fields, an allowed decision compatible with the source role, and
non-empty reviewer and reason values supplied in the decision file. It rejects
blank, missing, copied-default, unknown, extra, duplicated, normalized, or
partially completed rows as `REVIEW_REQUIRED`. It records when one reviewer
performed the pilot and discloses that as a limitation; it does not invent a
second reviewer.

Allowed decisions remain exactly `ACCEPT_POSITIVE`, `TRUE_HARD_NEGATIVE`,
`SECONDARY_POSITIVE`, `AMBIGUOUS_MULTI_SKILL`, `EASY_NEGATIVE`,
`NO_SKILL_CONFIRMED`, `SOURCE_LABEL_DEFECT`, and `REJECT_DRAFT`. Only
`TRUE_HARD_NEGATIVE` becomes a hard negative. `SECONDARY_POSITIVE` becomes a
positive for the reviewed candidate skill. Evaluation rows never enter
embedding training.

The exhaustive role compatibility table is:

| Source role | Compatible decisions |
|---|---|
| `POSITIVE` | `ACCEPT_POSITIVE`, `AMBIGUOUS_MULTI_SKILL`, `SOURCE_LABEL_DEFECT`, `REJECT_DRAFT` |
| `HARD_NEGATIVE_CANDIDATE` | `TRUE_HARD_NEGATIVE`, `SECONDARY_POSITIVE`, `AMBIGUOUS_MULTI_SKILL`, `EASY_NEGATIVE`, `SOURCE_LABEL_DEFECT`, `REJECT_DRAFT` |
| `NO_SKILL_CANDIDATE` | `NO_SKILL_CONFIRMED`, `AMBIGUOUS_MULTI_SKILL`, `SOURCE_LABEL_DEFECT`, `REJECT_DRAFT` |

No other pairing is valid. `SECONDARY_POSITIVE` uses the row's candidate
`skill_id`, counts toward the minimum 64 accepted train positives and 16/16
positive coverage, and does not count as a true hard negative.

### 6. Qualify the reviewed package independently

The reviewed v4 builder does not overwrite source files and does not repair
review decisions. It requires at least 64 accepted train positives, at least 48
true hard negatives, 100-160 accepted train pairs, 16 accepted calibration
positives, 16 accepted non-blind-test positives, at least 16 confirmed no-skill
rows in each evaluation split, 16/16 train-positive skill coverage, at most one
accepted positive per source task/query, family disjointness, and zero blockers.
This prevents an accepted owner positive and same-draft secondary positive from
turning the identical query into two mutually negative MNRL candidates. Counts
and hashes are recomputed independently in the package, qualification report,
and training-input manifest.

The 100-160 policy range is preserved from the approved handoff even though
this snapshot can yield at most 128 accepted train pairs (64 positive-role rows
plus 64 hard-negative-candidate rows). The effective upper bound for this pilot
is therefore 128; the declared 160 ceiling neither creates rows nor authorizes
another source.

The v4 acceptance package binds the source snapshot ID and commit, source
manifest hash, source-candidate hash, decisions hash, split-manifest hash,
accepted-pairs hash, qualification-report hash, and exact record lineage. The
canonical router decision remains `KEEP_BASELINE`; reviewed-data readiness is
not a promotion decision.

The four derived artifacts are fixed as `accepted-pairs.jsonl`,
`split-manifest.json`, `qualification-report.json`, and
`training-input-manifest.json`, using exact v4 schemas and policies declared in
the qualification delta spec. They share one `package_id` derived from the
source snapshot ID, trusted commit A, and exact source/decision hashes. Their
dependency order is acyclic: accepted rows, complete 192-member split map,
independently recomputed PASS report, then final admission manifest. All four
stage and publish together only after zero blockers. Published qualification
keeps `can_start_training=false` even when `can_start_preflight=true`.

### 7. Extend the sealed handoff with authenticated skill identity

The v4 training-input gate preserves the existing closure-held seal and
secret-keyed fingerprint model but adds exact `skill_id` to each sealed example
and to the handoff fingerprint. Invalid Unicode is rejected before hashing or
handoff construction, using stable code `TRAINING_INPUT_INVALID`; lone UTF-16
surrogates are never normalized, replaced, or silently encoded.

Accepted rows remain exact-shape, default-deny inputs. The loader authenticates
source, review, split, qualification, and accepted-pair lineage before returning
one immutable handoff. The trainer verifies the seal and fingerprint as its
first operation and never reopens source or review artifacts afterward.

Commit A is a production trust root captured in the separate v4 API closure,
not a producer, CLI, config, environment, or caller field: the loader reads the
Skill Index, draft, candidates, queue, and source manifest directly from that
Git object before trusting current files. A pure validator may accept an
explicit commit only for temporary-repository tests and has no sealing or
construction authority. The v4 example exposes only accepted
record ID, source record ID, authenticated skill ID, query text, skill text,
and supervision. The handoff adds the package/snapshot/commit identities and
all seven required lineage hashes. Per-example HMAC payloads bind all six
fields; the handoff HMAC binds the ten lineage/identity strings, example count,
and ordered array of recomputed example fingerprints with an exact
domain-separated length frame. Closure-only constructor authority and weak
issued-instance registries make copied-field or `object.__new__` clones fail
even when hidden fields are copied. V3 and v4 closures, types, secrets,
registries, trust roots, and verifiers remain distinct.

### 8. Precompute deterministic skill-unique positive batches

For the MNRL positive stream, the preflight uses the delta spec's
domain-separated, length-framed SHA-256 keys with an unsigned 64-bit seed.
Examples group by authenticated `skill_id`; K is the maximum of the largest
skill group and `ceil(N/batch_size)`. Seeded skill offsets assign each group to
minimum-size eligible batches, with exact cyclic and index tie breaks. Final
positive batches must contain 2 through the requested size, at most one record
per skill, exact-byte-unique queries across the positive stream, and every
positive exactly once. Impossible, duplicate-query, or singleton plans fail
rather than dropping or duplicating examples. Hard negatives use a separately
hashed, deterministically chunked ContrastiveLoss stream whose final batch may
contain one pair.

This sampler is preferred to changing the loss because it preserves the
preregistered MNRL-plus-contrastive objective while removing same-skill false
negatives from MNRL batches.

### 9. Make `--preflight-only` a standard-library bootstrap

Argument parsing and v4 preflight live before any import of Torch,
SentenceTransformers, model modules, or device helpers. Preflight validates the
package, Unicode, hashes, sealed handoff, batch plan, clean Git worktree, and
lineage inputs. It computes and prints a deterministic plan but does not create
the output directory, load a model, inspect or initialize CUDA, write a log,
config, checkpoint, summary, manifest, or model card, or import model
frameworks. Fresh-subprocess sentinel tests prove those absences.

`TRAINING_READY_PRECHECK=PASS` is emitted only when every v4 gate passes. Any
error emits a stable non-PASS status and exits nonzero. A passing preflight does
not fall through to training and does not change `KEEP_BASELINE`.

Unit and subprocess tests before integration use temporary Git repositories and
synthetic packages and cannot stand in for the canonical PASS. After tasks 6-9
are complete and independently reviewed, the workflow must stop for exact
authorization to create reviewed-package commit B. The real PASS check runs
only from a fresh clean worktree at that commit; an uncommitted or untracked
decision/package/code path necessarily fails the clean-tree gate.

The CLI is exactly `--config`, `--preflight-only`, and
`--expected-git-commit`; preflight rejects output-root overrides. The exact v4
config binds immutable lowercase-40-hex model revision, seed, epochs, batch
size, objective, output-path strings, expected Python/platform/distribution
metadata, device policy `cuda_required` or `cpu_only`, and `KEEP_BASELINE`.
Runtime versions come from `importlib.metadata` without importing frameworks.
Git root, commit, tree, empty NUL-delimited status, tracked artifact bytes, and
config bytes are checked both before loading and immediately before PASS.

Success is one canonical JSON stdout line containing the complete lineage,
config/plan hashes, in-memory batch plan, runtime/model/Git identities,
`TRAINING_READY_PRECHECK=PASS`, `KEEP_BASELINE`, and
`can_start_training=false`. Failure is one sanitized canonical stderr JSON line
using only the six declared error codes and never emits PASS or writes a file.

### 10. Bind complete future execution lineage

Before any separately authorized real training, the planned config, run
summary, model manifest, and checkpoint metadata must bind
`training_input_manifest_sha256`, `source_manifest_sha256`,
`source_candidates_sha256`, `review_decisions_sha256`,
`accepted_pairs_sha256`, `qualification_report_sha256`,
`split_manifest_sha256`, `batch_plan_sha256`, `train_config_sha256`, exact Git
commit/tree, `git_worktree_state=CLEAN`, base model ID and immutable revision,
seed, dependency versions, Python version, platform, and device selection. The
preflight verifies that the current tree is clean, but it creates no execution
artifacts and provides no dirty-tree fallback.

## Risks / Trade-offs

- **[Pilot prompts are newly authored by the implementing agent rather than
  externally sourced or human-approved]** -> The snapshot records exact draft
  and generated bytes, never presents agent authorship as human review or the
  draft as benchmark truth, and requires explicit human decisions before use.
- **[A lexical near-duplicate detector can miss semantic paraphrases]** -> The
  deterministic detector is a minimum fail-closed guard; human review remains
  mandatory and the limitation is recorded. No embedding model is used to
  avoid hidden model/dependency and leakage effects.
- **[One reviewer may introduce correlated judgment error]** -> A single
  reviewer is allowed only for this pilot and is disclosed in qualification;
  the importer never implies independent agreement.
- **[Snapshot and decision files can drift independently]** -> Exact headers,
  row identity, line hashes, and non-human byte checks bind every decision back
  to commit A; any mismatch blocks the entire package.
- **[The same-skill sampler may reduce effective batch size]** -> Preflight
  reports the actual plan and fails unsupported batch parameters instead of
  weakening uniqueness.
- **[A green preflight may be mistaken for model success]** -> Every machine and
  human surface keeps `KEEP_BASELINE`, no-training, and no-improvement language;
  the only allowed conclusion is input/runtime readiness.
- **[A single compact change is larger than the first executable slice]** ->
  Tasks contain explicit stage-stop checkpoints, and commit A contains only the
  source-snapshot implementation plus authoritative planning artifacts.
