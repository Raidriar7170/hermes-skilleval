## Context

The prompt-only implementation and fail-closed trainer gate are pushed at commit `51b59851255ef7cb85011912a413aa57c7dac0fb` on branch `agent/harden-router-v2-pretraining-contracts`. The active OpenSpec is not archived, and there is no PR or merge. This closeout repairs that lifecycle truth and records the remaining design prerequisites before any real training; it does not reopen the implemented runtime contract.

This change is a fail-closed contract repair. It preserves the canonical decision `REVIEW_REQUIRED`, `KEEP_BASELINE`, and `can_start_training=false`; it does not supply reviewed data or make the package training-ready. Phase 14–18 and blind evidence are protected historical inputs and must remain byte-for-byte unchanged.

## Goals / Non-Goals

**Goals:**

- Make `router_query_text(prompt)` the single prompt-only boundary for every real core router, reranker, verification, training-export, and Stage 2 query path.
- Remove metadata strings and category-derived score adjustments from core routing decisions while retaining metadata only as record identity and provenance.
- Advance qualification policy, candidate rows, report, and manifest to v3 with independently derived prompt, family, and per-skill statistics.
- Define v3 controlled-package and accepted-row contracts whose hashes and formal review evidence are verified atomically before any framework or output side effect.
- Correct stale README and current v3 Human Brief lifecycle wording to the pushed implementation baseline commit `51b59851255ef7cb85011912a413aa57c7dac0fb`, with the change active/unarchived and no PR or merge.
- Specify, but do not implement, source-snapshot authenticity, complete training-output lineage, same-skill false-negative mitigation, and the bounded closure/HMAC threat model required before real training.

**Non-Goals:**

- No model training, GPU/A100 work, dependency installation, checkpoint generation, performance claim, blind-v2 dataset, blind mining, blind rerun, or blind evidence replacement.
- No reviewed positives, reviewed hard negatives, trainer-ready package, calibration set, reject examples, inferred family labels, or target-coverage repair is produced.
- No Phase 14–18 or blind-tree modification, further push, PR, merge, archive, tag, release, deploy, or remote-CI claim is included.
- The base commit has 2 repository-wide Ruff findings and 98 mypy errors; this bounded change must keep Ruff at 2 and introduce no new mypy error signature, while relevant v3 migrations may remove inherited mypy errors.

## Decisions

### 1. Use one metadata-incapable query boundary

`router_query_text(prompt)` accepts only the loader-normalized prompt string and returns exactly that string. Callers must extract the normalized prompt before crossing the boundary; the helper must not accept a row, metadata mapping, task object, or optional context. Embedding-pair export, `EmbeddingRouter`, `KeywordRouter`, `HybridRouter`, verification-gated scoring, cross-encoder scoring, and Stage 2 core routed prediction export all use this same boundary.

Core query construction must stop concatenating task ID, category, difficulty, robustness tags, split, family, or other metadata. Category bonuses, affinity terms, weights, gates, and tie-breakers that derive from the category field must also be removed from real core score and ranking decisions. Category words that occur naturally inside the prompt remain part of the prompt. Metadata may remain beside results for identity, auditing, and structured provenance, but cannot influence model input, score, or rank.

The invariant is tested by holding the prompt fixed while mutating every metadata field: query text, router scores, and ordering must remain identical. This explicit API boundary is preferred to sanitizing arbitrary record objects because an object-accepting API can silently regain leakage later.

### 2. Make qualification v3 a breaking, independently recomputed contract

The qualification policy, candidate-row schema, qualification report, and manifest advance together from v2 to v3; mixed-version packs are invalid. V3 binds the pack to the prompt-only query contract and reports statistics computed from canonical rows rather than copied between artifacts:

- `unique_prompt_count=12` for the complete candidate set;
- train-policy unique prompt count `8`;
- a unique train-positive count for each of all 16 skills, including the five skills whose count is explicitly zero;
- missing family data as JSON `null` and human-readable `UNAVAILABLE`, never inferred from category, task ID, skill, or neighboring rows.

Validators independently recompute these values and require the policy, rows, report, and manifest to agree. The existing blocked decision markers remain unchanged; schema advancement is not human acceptance.

### 3. Put an exact, default-deny v3 gate ahead of the training framework

The controlled package manifest has exactly six required and allowed top-level fields: `schema_version`, `artifact_version`, `policy_id`, `package_id`, `accepted_pairs`, and `qualification_report`. `package_id` must be non-blank; blankness uses `value.strip()` only as a predicate, while the exact original package-ID bytes are preserved and bound by the handoff HMAC fingerprint. `accepted_pairs` has exactly `path`, `sha256`, and `row_count`; `qualification_report` has exactly `path` and `sha256`. Unknown or missing fields fail validation. Both paths are interpreted relative to the manifest parent directory as the package root and must be non-empty canonical POSIX-relative paths. Absolute paths, empty/`.`/`..` segments, backslashes, symlink components or targets, non-regular files, package-root escapes, and two references resolving to the same file are rejected before either bound file is consumed.

Every accepted row has exactly these required and allowed fields, with no optional extension surface:

`schema_version`, `artifact_version`, `policy_id`, `accepted_record_id`, `pair_id`, `source_record_id`, `source_schema_version`, `source_kind`, `source_dataset_id`, `source_artifact_path`, `source_split`, `candidate_type`, `task_id`, `skill_id`, `query_text`, `query_text_policy`, `prompt_text_sha256`, `skill_text`, `accepted_for_training`, `training_split`, `supervision_label`, `review_status`, `reviewer`, `review_reason`, `source_hash`, and `acceptance_hash`.

Unknown or missing row fields fail validation. In particular, `label`, category/difficulty/family metadata, and any legacy, alternate, composite, or second task-query field are forbidden. `accepted_record_id`, `pair_id`, and `source_record_id` are non-blank and independently unique within the package. `task_id`, `skill_id`, `query_text`, `skill_text`, `reviewer`, and `review_reason` are also non-blank. Validation uses `value.strip()` only as a blankness predicate and preserves every original string byte for prompt, source, and acceptance hashing; it never stores or hashes a trimmed replacement. The tuple `(source_kind, source_dataset_id, source_artifact_path, source_record_id)` is also independently unique.

Source provenance is a positive allowlist, not a forbidden-substring heuristic. Every admitted row must use `source_kind=ROUTER_TRAINING_DATA_V2_CANDIDATE`, `source_dataset_id=router-training-data-v2-qualification-pack`, `source_artifact_path=docs/demo/router-training-data-v2-qualification-pack/candidate-pairs.jsonl`, and `source_split=dev`. The only allowed role mappings are `candidate_type=positive` with `supervision_label=POSITIVE` and `review_status=ACCEPTED_POSITIVE`, or `candidate_type=same_category_negative_candidate` with `supervision_label=HARD_NEGATIVE` and `review_status=ACCEPTED_HARD_NEGATIVE`. This exact allowlist rejects blind, Phase 16, source-test, easy-negative, provisional, legacy, and unknown sources by default; the validator must not infer admissibility from path substrings or free-text provenance.

Each row carries two independently recomputed canonical hashes. `source_hash` binds exactly `source_record_id`, `pair_id`, `source_schema_version`, `source_kind`, `source_dataset_id`, `source_artifact_path`, `source_split`, `candidate_type`, `task_id`, `skill_id`, `query_text`, `query_text_policy`, `prompt_text_sha256`, and `skill_text`. `acceptance_hash` binds exactly `source_hash`, `policy_id`, `accepted_record_id`, `pair_id`, `supervision_label`, `accepted_for_training`, `training_split`, `review_status`, `reviewer`, and `review_reason`. Payloads use UTF-8 JSON with sorted object keys, compact `(',', ':')` separators, preserved array order, `ensure_ascii=false`, and no trailing newline. Hashes establish content and decision integrity only; they do not prove source authenticity, establish identity, or replace explicit provenance and reviewer evidence. Binding accepted rows to an independently authenticated source snapshot is a deferred prerequisite for a separately authorized reviewed-data phase; this change does not add a task-ID or path-substring blind heuristic, open protected data, or widen the exact positive provenance allowlist.

The future reviewed-data package therefore requires an independent authenticated source-snapshot manifest. At minimum it binds `candidate_artifact_sha256`; each `source_record_id` to its candidate artifact original row through `source_record_exact_bytes_sha256`; `task_snapshot_sha256`; `skill_snapshot_sha256`; the exact bytes shown to the reviewer through `reviewed_source_exact_bytes_sha256`; and both `source_snapshot_id` and `package_id`. The authentication root must be created independently of the acceptance package and must bind snapshot/package identity. A fixed dataset/path or a self-computed hash is insufficient: a producer able to rewrite both a row and its locally recomputed digest has not proved canonical source authenticity. This change designs that prerequisite only and does not add it to the current v3 schema or produce such a manifest.

The manifest accepted count must equal both the parsed accepted-row count and the bound qualification report's accepted count. The bound report must use the v3 qualification contract, set `can_start_training=true`, and have `blocker_codes=[]`; therefore the current canonical blocked report cannot pass. Only a temporary synthetic true report may exercise the success branch in tests, and it is not a production artifact or reviewed-data claim.

Validation runs in a standard-library-only bootstrap before importing Torch or model code, constructing or loading a model, creating an output directory, or writing a checkpoint. It validates the entire package before making one immutable, ordered handoff. Frozen dataclasses alone are insufficient because an ordinary caller could construct or forge them directly, and `object.__setattr__` can mutate a genuine frozen instance after construction. The gate therefore creates the example and handoff types around one unexported validation seal and one independent fingerprint secret held only in a closure, never in a module-global token, key, registry, or builder. Both constructors require the closure token and store it in frozen slots. The loader also stores a secret-keyed canonical content fingerprint in each example and in the handoff; the handoff fingerprint binds package ID plus every example field in file order. The secret is never stored in an instance. The module exposes only an internal verifier, and the downstream training function invokes that verifier as its first operation. It checks the exact handoff/example types, seals, tuple immutability, and recomputed secret fingerprints before any grouping, framework import, model access, or output side effect. Constructor forgery, `object.__new__` forgery, genuine-example field mutation, package-ID mutation, and genuine-handoff example replacement therefore fail closed, while an unchanged genuine handoff from `load_training_input` crosses the boundary exactly once.

The closure-held seal and HMAC fingerprint are an internal fail-closed integrity/misuse guard against accidental calls, ordinary construction, low-level object forgery, and unauthorized code paths covered by the verifier. They are not a cryptographic security boundary against arbitrary malicious same-process Python, introspection, monkey-patching, runtime memory inspection, or replacement of trusted code. This bounded threat model does not weaken the existing gate: all current validation, seal, fingerprint, whole-package rejection, and pre-side-effect ordering requirements remain mandatory.

After seal verification, the downstream trainer may group rows only by `supervision_label`, must derive each task-side model input only as `router_query_text(query_text)`, and may use `skill_text` only as the separate skill-side input. It must not read or reconstruct a raw `label`, category, or source metadata for training. Invalid input produces no handoff; valid input crosses the boundary exactly once, with no filtering, repair, inference, upgrade, or partial consumption. Fresh subprocess tests put shadow `torch` and `sentence_transformers` modules on `PYTHONPATH` whose import would create a sentinel, then run the real trainer script with an invalid manifest and an invalid accepted row. Each process must exit nonzero with the stable gate error while leaving both the import sentinel and output root absent.

The current positive path uses MultipleNegativesRankingLoss with random batching. Once future reviewed data contains multiple prompts for one skill, another positive for that same skill in the batch becomes a same-skill false negative. Before real training, the data/trainer contract must choose and test either a deterministic skill_id-unique batch sampler with at most one example per skill_id per batch, or an explicit multi-positive objective such as supervised contrastive/listwise training. The current sealed handoff does not expose skill_id, so that future contract must add a verified, fingerprint-bound skill identity or build the sampler before the metadata-reducing handoff without reopening source artifacts. This change records the design point only; it does not change batching, objectives, or the sealed handoff.

New trainer-controlled artifacts use only Router Training Data V2 v3 lineage. Generated train configs use `schema_version="router-training-data-v2-train-config-v3"`, integer `artifact_version=3`, `policy_id="router-training-data-v2-training-admission-v3"`, and `artifact_type="router-training-data-v2-train-config"`, with no `phase`. Generated train-run summaries use `schema_version="router-training-data-v2-train-run-summary-v3"`, integer `artifact_version=3`, the same admission policy, and `artifact_type="router-training-data-v2-train-run-summary"`, with no Phase 14 identity. Model manifests written by this trainer use `schema_version="router-training-data-v2-model-manifest-v3"`, integer `artifact_version=3`, the same admission policy, and `artifact_type="router-training-data-v2-model-manifest"`, with no Phase 15 identity. The shared historical `model_manifest` defaults and every committed Phase 14–18 artifact remain unchanged: the trainer builds the file inventory downstream, replaces historical identity only in memory, and writes the new v3 manifest itself. Generated model-card title, prose, and example command likewise use Router Training Data V2 v3 wording and a neutral v3 config path rather than Phase 14.

Before a real checkpoint may be written, the future train config, run summary, model manifest, and checkpoint metadata must all bind the exact execution lineage: `training_input_manifest_sha256`, `accepted_pairs_sha256`, `qualification_report_sha256`, `train_config_sha256`, `git_commit`, `git_tree_oid`, `git_worktree_state="CLEAN"`, `base_model_id`, immutable `base_model_revision`, `seed`, `dependency_versions`, and `split_manifest_sha256`. Real training must run `git status --porcelain --untracked-files=all` before framework/model/output side effects and fails closed when its output is non-empty, including for untracked files; there is no dirty-diff or patch-capture fallback. Reusing only `training_input_package_id` is insufficient because it cannot uniquely reproduce the bytes, committed tree, code, base model revision, environment, seed, or family-disjoint split that produced a checkpoint. This change records the required fields and clean-tree prerequisite but does not implement the runtime check or generate a config, run, model, checkpoint, schema, or artifact version.

### 4. Keep the legacy exporter diagnostic-only

The legacy exporter may remain available for inspection and compatibility diagnostics, but its output is not an accepted-row v3 package and must not be accepted by the trainer. It must not mint formal review metadata, upgrade legacy rows by inference, or present its output as trainer-ready. A separate, explicitly reviewed data phase must create any future controlled package.

### 5. Protect historical evidence and repair only stale lifecycle truth

Phase 14–18 and blind evidence trees are immutable for this change and are covered by identity checks. The current qualification-pack README and current v3 Human Brief must identify `REVIEWED_IMPLEMENTATION_COMMIT_PUSHED` at commit `51b59851255ef7cb85011912a413aa57c7dac0fb`, `BRANCH_PUSHED`, `ACTIVE_UNARCHIVED`, `NO_PR`, `NO_MERGE`, and `REMOTE_PR_CI_PENDING / NO_PR`. A feature-branch push does not trigger the existing PR-only/push-main workflow, so local validation is not remote CI. The wording must not imply review acceptance, training readiness, new evidence, PR integration, or archive completion.

### 6. Use non-regression validation rather than widening cleanup scope

Focused contract tests must cover metadata invariance, v3 statistics and null-family behavior, hash/package rejection, whole-input rejection, pre-framework/no-output side effects, legacy-format rejection, Stage 2 behavior, and protected-evidence identity. Changed-file `ruff check` must report zero findings, while `ruff format --check` must continue to report, without bulk formatting, exactly eight inherited whole-file reformat candidates in `src/hermes_skilleval/cli.py`, `src/hermes_skilleval/routers/cross_encoder.py`, `src/hermes_skilleval/routers/embedding.py`, `src/hermes_skilleval/routers/hybrid.py`, `src/hermes_skilleval/routers/keyword.py`, `tests/test_cli_smoke.py`, `tests/test_cross_encoder_router.py`, and `tests/test_gated_router.py`; the full repository must retain exactly 2 Ruff findings.

Repository-wide mypy non-regression uses exactly `MYPY_CACHE_DIR="$(mktemp -d)" mypy src tests`. A temporary `git archive` snapshot of base `f996690700a79ab4c065ed8523340d2fd387f6b9` establishes `98 errors in 21 files (checked 126 source files)`. The current tree must produce no more than 98 errors and no new error signature; relevant v3 migrations may legitimately remove inherited errors, so the current count is reported as observed rather than forced to remain exactly 98. Existing modified-file findings are evaluated base-versus-current by signature, not treated as an exact changed-file count.

New-file cleanliness uses exactly `mypy --check-untyped-defs --follow-imports=silent src/hermes_skilleval/router_query.py src/hermes_skilleval/training_input.py tests/test_router_query_contract.py tests/test_training_input.py tests/training_input_test_support.py` and requires zero errors. Broader unrelated cleanup belongs to another change.

No PR-triggered remote CI exists because there is no PR. The branch push and local checks must be reported separately from the `REMOTE_PR_CI_PENDING / NO_PR` state; local validation must never be labeled as remote CI.

### 7. Defer reviewed-data prerequisites explicitly

Before a next reviewed-data phase may begin, reviewers must separately approve an independent calibration-data contract and an explicit blind/test access allowance (default deny), alongside the required human acceptance and hard-negative review policy. This change records those prerequisites only. It neither grants an allowance nor reads, derives, or creates calibration, blind, test, or blind-v2 data.

## Risks / Trade-offs

- [Breaking v3 migration can leave mixed artifacts] → Reject mixed versions and recompute cross-artifact statistics and hashes from canonical rows.
- [A hidden metadata-dependent branch could survive query cleanup] → Combine a metadata-incapable API with mutation-based score and ranking invariance tests across every listed core consumer.
- [Top-level framework imports could violate the pre-framework gate] → Keep package validation in a lightweight bootstrap and delay all trainer/framework imports until validation succeeds.
- [Open-ended records can silently admit new training channels] → Require exact manifest, nested-object, and accepted-row field sets; reject every unknown or missing field.
- [Hash checks can appear valid while binding ambiguous serialization] → Freeze the exact source/acceptance payload keys and UTF-8 sorted-key compact serialization, including preserved array order and no trailing newline.
- [Relative package references can escape or alias files] → Resolve canonical POSIX-relative paths from the manifest parent, reject symlinks/non-regular files/escapes, and require distinct bound files.
- [Validated metadata can leak back into training] → Hand off an immutable collection once, group only by `supervision_label`, and derive task-side input only through `router_query_text(query_text)`.
- [Frozen handoff classes can be instantiated, forged, or mutated through low-level assignment] → Require a closure-held seal plus secret-keyed canonical content fingerprints in frozen slots and make downstream seal/fingerprint verification the first operation before imports, grouping, or outputs.
- [Closure/HMAC wording can overclaim hostile same-process security] → State the internal fail-closed misuse-guard threat model explicitly while retaining every existing rejection and pre-side-effect invariant.
- [Accepted rows can be self-consistent but detached from the canonical reviewed source] → Require a separately authenticated source-snapshot manifest that binds exact original/reviewed bytes and snapshot/package identity before real training.
- [Future MNRL batches can treat another prompt for the same skill as a negative] → Require a deterministic skill-unique sampler or an explicit multi-positive objective with a focused no-same-skill-false-negative test.
- [New trainer artifacts can silently inherit Phase 14/15 lineage] → Give config, run summary, model manifest, and model card exact Router Training Data V2 v3 identities while preserving the shared historical writer defaults.
- [A checkpoint can retain only a reusable package label rather than reproducible inputs] → Bind the exact input/report/config/split hashes, code commit, immutable base-model revision, seed, and dependency versions before any real run.
- [A recorded commit can hide tracked or untracked worktree changes used by training] → Require `git_tree_oid` plus `git_worktree_state="CLEAN"`, fail closed on any non-empty porcelain status, and provide no dirty-diff fallback.
- [Diagnostic output may be mistaken for approved training data] → Give legacy output no accepted v3 schema and make the trainer reject it categorically.
- [Truth wording can overstate lifecycle progress] → Identify the pushed baseline while keeping no-PR/no-merge/active-unarchived and PR-CI-pending states separate from local validation.
- [Inherited whole-file findings can be mistaken for regressions or trigger unrelated cleanup] → Record the exact eight format candidates, require new-file mypy cleanliness, and compare the current repository mypy signatures against the archived 98-error base snapshot while allowing relevant v3 migrations to reduce the count.

## Migration Plan

1. Introduce the pure query helper and route all listed real core consumers through it; add fixed-prompt metadata-mutation tests.
2. Remove metadata/category input and score paths, then advance qualification policy, rows, report, and manifest together to v3 with independent-statistic validation.
3. Add the exact-field v3 manifest and accepted-row schemas, default-deny source allowlist, canonical hash payloads, safe package-root path resolution, and standard-library pre-framework gate; connect the trainer through one immutable prompt-only handoff only after complete validation succeeds.
4. Mark and test the legacy exporter as diagnostic-only, then add protected-evidence identity checks and stale README/Human Brief truth repairs.
5. Run focused tests, changed-file Ruff check/format-check, the pinned new-file and repository-wide mypy commands, OpenSpec validation, and diff checks. Report inherited whole-file output separately from new-file cleanliness and base-versus-current mypy signatures, do not bulk-format unrelated files, and record `REMOTE_PR_CI_PENDING / NO_PR` separately from local validation.
6. Review integration as a stack: first `main <- f996690700a79ab4c065ed8523340d2fd387f6b9` for the qualification/prompt-only data contract, then `f996690700a79ab4c065ed8523340d2fd387f6b9 <- 51b59851255ef7cb85011912a413aa57c7dac0fb` for shared runtime query, v3 artifacts, admission gate, and trainer bootstrap. This is a review plan only; this closeout creates no PR.

Rollback is a code-and-artifact revert to the pre-change local state. It must not rewrite the protected Phase 14–18 or blind evidence trees. Because v2 and v3 inputs cannot be mixed, rollback must restore the code and qualification artifacts as one unit; no v3 package may be silently downgraded to a legacy training input.

## Open Questions

There are no unresolved decisions required to implement this bounded contract repair. The calibration-data contract and blind/test access allowance remain explicit, default-deny prerequisites for a separately proposed and reviewed data phase; they are not questions to answer or implement here.
