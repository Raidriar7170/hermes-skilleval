## ADDED Requirements

### Requirement: Preflight validates before framework or output side effects
The real embedding trainer entry point SHALL expose `--preflight-only` through a standard-library-only bootstrap. Before importing Torch, SentenceTransformers, model modules, CUDA/device helpers, or any module that imports them, it MUST validate arguments, the complete v4 training-input package, exact Unicode, the sealed handoff, deterministic batch plan, clean Git state, and complete lineage. Preflight MUST NOT inspect or initialize a GPU, load a model, create an output directory, or write a config, log, checkpoint, summary, manifest, model card, cache, or temporary artifact under the requested output root.

#### Scenario: Valid preflight runs in a framework-free subprocess
- **WHEN** a valid reviewed v4 package is passed with `--preflight-only` while shadow `torch` and `sentence_transformers` imports would create sentinels
- **THEN** the command exits zero with `TRAINING_READY_PRECHECK=PASS`
- **AND** import sentinels and the requested output root remain absent

#### Scenario: Invalid package is supplied
- **WHEN** any package, source, review, split, qualification, lineage, Unicode, handoff, or batch-plan check fails
- **THEN** the command exits nonzero without importing model frameworks or creating output
- **AND** it does not emit `TRAINING_READY_PRECHECK=PASS`

#### Scenario: Passing preflight reaches its terminal boundary
- **WHEN** every preflight gate passes
- **THEN** the command exits without falling through to training
- **AND** it does not load a model, access CUDA, write a checkpoint, or change `KEEP_BASELINE`

### Requirement: MNRL positive batches are deterministic and skill-unique
Preflight SHALL construct the positive Multiple Negatives Ranking Loss batch plan from authenticated `skill_id` and stable accepted-record identity. It SHALL order examples and skills with the exact domain-separated SHA-256 keys defined below and SHALL allocate them with the exact descending-group-size, minimum-size-eligible-batch, cyclic-offset algorithm defined below. Every positive SHALL appear exactly once per epoch, each positive batch MUST contain at most one example for any `skill_id`, and positive `query_text` values MUST be exact-byte unique across the complete positive stream. The same accepted bytes, seed, and batch size MUST produce the same ordered plan. Hard negatives SHALL remain a separate contrastive stream and MUST NOT be inserted as MNRL positives.

#### Scenario: Several prompts share one skill
- **WHEN** reviewed training input contains two or more positive prompts for a skill
- **THEN** no MNRL batch contains two examples with that skill ID
- **AND** all examples still appear exactly once in the deterministic epoch plan

#### Scenario: Plan is regenerated
- **WHEN** identical accepted bytes, seed, and batch size are preflighted twice
- **THEN** the ordered batch plan and `batch_plan_sha256` are identical

#### Scenario: Requested batch parameters cannot preserve the contract
- **WHEN** a batch parameter is invalid or cannot produce the declared skill-unique plan
- **THEN** preflight fails closed
- **AND** it does not fall back to random batching, duplicate a positive, drop an example, or change the objective

### Requirement: Preflight CLI and v4 train config are exact
The v4 command SHALL be invoked exactly as
`python scripts/train_embedding_router.py --config <repo-relative-config> --preflight-only --expected-git-commit <40-lowercase-hex>`.
`--preflight-only` and any future `--execute-training` flag are mutually
exclusive. A v4 config without `--preflight-only`, an unknown CLI argument, or
an `--output-root` override MUST fail; CLI values may not escape the bound
config hash. Existing v3 invocation without v4 schema remains unchanged.

The v4 config SHALL contain exactly `schema_version`, `artifact_version`,
`policy_id`, `artifact_type`, `training_input_manifest`, `base_model_id`,
`base_model_revision`, `epochs`, `batch_size`, `learning_rate`,
`hard_negative_margin`, `loss`, `seed`, `device_policy`, `output_root`,
`output_dir`, `runtime_requirements`, and `router_decision`. Constants are
`schema_version="router-v2-train-config-v4"`, integer
`artifact_version=4`, `policy_id="router-v2-training-preflight-v1"`,
`artifact_type="router-v2-train-config"`,
`training_input_manifest="data/router-v2-v4/training-input-manifest.json"`,
`loss="MultipleNegativesRankingLoss+ContrastiveLoss"`, and
`router_decision="KEEP_BASELINE"`.

`seed` is a non-bool integer from 0 through `2**64-1`; `epochs` is a non-bool
integer from 1 through 1000; `batch_size` is a non-bool integer from 2 through
the authenticated distinct-positive-skill count and never above 16.
Learning rate and margin are finite non-bool numbers greater than zero.
`base_model_id` is exactly one nonempty `owner/repository` pair with no URL,
`@`, whitespace, empty, dot, or dot-dot segment. `base_model_revision` matches
exactly `[0-9a-f]{40}`; branch, tag, short, uppercase, or network-resolved
identities fail. `device_policy` is exactly `cuda_required` or `cpu_only`;
`auto` is forbidden because preflight may not inspect devices.

`output_root` and `output_dir` are NUL-free normalized absolute POSIX strings,
and output dir is a strict lexical descendant of output root. Preflight MUST
NOT call `mkdir`, `resolve`, `exists`, `stat`, or another filesystem operation
on either output path. `train_config_sha256` hashes exact config file bytes,
which must be canonical compact sorted-key JSON plus one LF.

`runtime_requirements` SHALL contain exactly `python_implementation`,
`python_version`, `platform_system`, `platform_machine`, and `dependencies`.
Dependencies contains exactly `torch` and `sentence-transformers` with exact
nonblank installed-version strings. The four platform strings are exact
expected values rather than ranges.

#### Scenario: Mutable model revision is configured
- **WHEN** base revision is a branch, tag, short hash, URL fragment, or any
  value outside lowercase 40-hex
- **THEN** preflight fails `PREFLIGHT_CONFIG_INVALID`
- **AND** it performs no network or model-cache lookup to resolve the value

### Requirement: Batch ordering uses one domain-separated binary framing
The planner SHALL use `MAGIC=b"hermes-router-v2-batch-plan-v1\x00"` and define
`frame(domain, parts...)` as MAGIC, unsigned big-endian uint16 domain-byte
length, domain bytes, then for each part its unsigned big-endian uint32 byte
length and bytes. Oversized components fail. Seed bytes are exactly unsigned
8-byte big-endian; strings are strict UTF-8 with no normalization.

Ordering digests are exactly:

- `SHA256(frame(b"positive-skill-order", seed_bytes, skill_id_bytes))`;
- `SHA256(frame(b"positive-record-order", seed_bytes, skill_id_bytes,
  accepted_record_id_bytes))`;
- `SHA256(frame(b"hard-negative-record-order", seed_bytes, skill_id_bytes,
  accepted_record_id_bytes))`.

Digest ties use exact UTF-8 skill ID and then accepted record ID. Prompt,
reviewer, family, path, hash, or other provenance MUST NOT enter an ordering
key.

#### Scenario: Delimiter-shaped identities are ordered
- **WHEN** stable identities contain punctuation that would be ambiguous under
  string concatenation
- **THEN** length framing produces one unambiguous key
- **AND** no delimiter escaping or locale ordering is substituted

### Requirement: Positive allocation is complete, balanced, and non-singleton
The verified sealed v4 handoff MUST be the planner's only example source and
its verifier is the first planner operation. The planner rejects duplicate
accepted IDs, invalid skill IDs, unknown supervision, no positives, fewer than
two positive skills, or any value not already authenticated by the handoff.

Group positives by exact `skill_id` and sort each group by its positive-record
digest then accepted ID. Sort skill groups by descending group size, then
positive-skill digest, then skill ID. With positive count `N`, distinct skill
count `D`, requested size `B`, and largest group `M`, set
`K=max(M, ceil(N/B))`. Require `2 <= B <= D` and `K <= floor(N/2)`.
Create exactly K empty batches. For each ordered skill group, compute
`offset=int.from_bytes(skill_digest[:8], "big") % K`; for each ordered record,
choose among batches below capacity B and not already containing that skill.
Choose minimum current size, then minimum cyclic distance from offset, then
batch index. No other tie break is allowed.

Within each final batch, sort records by positive-skill digest,
positive-record digest, skill ID, and accepted ID. Every batch must have size
2 through B, contain unique skills, and together contain every positive
exactly once. Any unavailable eligible batch, singleton, duplicate, omission,
or impossible parameter fails `BATCH_PLAN_INVALID`; examples are never dropped,
duplicated, or randomly reshuffled. The same epoch template repeats unchanged
for all configured epochs.

Hard negatives remain a separate ContrastiveLoss stream, sorted by the exact
hard-negative digest then skill ID and accepted ID, chunked by B, with a final
one-record partial batch allowed. Each hard negative occurs exactly once per
epoch template. The v4 execution path must consume these templates and MUST
NOT call `random.shuffle`.

#### Scenario: Secondary positives make skill counts uneven
- **WHEN** some skills have more accepted positives than others
- **THEN** the exact K-batch balanced allocation is attempted and fully
  validated
- **AND** the planner either emits only skill-unique non-singleton batches or
  fails without a lossy fallback

### Requirement: Batch-plan object and hash are exact
The in-memory plan SHALL contain exactly `schema_version`, `artifact_version`,
`policy_id`, `algorithm_id`, `hash_framing_id`, `seed_encoding`,
`training_input_package_id`, `training_input_manifest_sha256`, `seed`,
`epoch_count`, `epoch_strategy`, `requested_batch_size`,
`positive_example_count`, `hard_negative_example_count`,
`distinct_positive_skill_count`, `positive_batches`, and
`hard_negative_batches`. Constants are
`schema_version="router-v2-training-batch-plan-v1"`, integer version 1,
`policy_id="router-v2-training-preflight-v1"`,
`algorithm_id="seeded-skill-unique-balanced-v1"`,
`hash_framing_id="u16-domain-u32-parts-sha256-v1"`,
`seed_encoding="uint64-big-endian"`, and
`epoch_strategy="repeat-identical-template"`.

Every batch object contains exactly integer `batch_index` starting at zero and
contiguous plus `records`. Every record contains exactly
`accepted_record_id` and `skill_id`. Positive and hard-negative arrays follow
their exact planner order. Plan bytes are compact sorted-key strict-UTF-8 JSON
with `ensure_ascii=false`, `allow_nan=false`, and one LF.
`batch_plan_sha256` is SHA-256 of those complete bytes and is not a self-field.
The plan is returned inside the preflight result and MUST NOT be written.

#### Scenario: Plan is hashed after reserialization
- **WHEN** a caller changes object key order, whitespace, escaping, record
  order, batch index, or terminal LF
- **THEN** its bytes no longer match the canonical plan or plan hash
- **AND** parsed-value similarity is not sufficient

### Requirement: Preflight binds complete prospective execution lineage
The preflight result SHALL bind `training_input_manifest_sha256`, `source_manifest_sha256`, `source_candidates_sha256`, `review_decisions_sha256`, `accepted_pairs_sha256`, `qualification_report_sha256`, `split_manifest_sha256`, `batch_plan_sha256`, `train_config_sha256`, `git_commit`, `git_tree_oid`, `git_worktree_state="CLEAN"`, `base_model_id`, immutable `base_model_revision`, `seed`, dependency versions, Python version, platform identity, and the explicitly requested device policy. Every value MUST be derived from exact input bytes or the current repository/runtime rather than copied from an unverified report.

The preflight SHALL run the exact twice-executed Git command set declared below, including `git status --porcelain=v1 -z --untracked-files=all --ignore-submodules=none`, before framework, model, GPU, or output work and SHALL fail when any tracked or untracked path is reported. It MUST NOT accept a patch, dirty-diff hash, ignore flag, or best-effort fallback as a clean-tree substitute.

Temporary unit/subprocess fixtures MAY exercise the gate in temporary Git repositories, but fixture success MUST NOT be reported as the canonical readiness result. After human review, reviewed-package construction, admission, and preflight implementation are complete, the workflow SHALL stop and request exact user authorization for reviewed-package commit B. Only when that commit is separately authorized may the reviewed decisions, package, and runtime code be committed. The canonical `TRAINING_READY_PRECHECK=PASS` MUST run from a fresh worktree at that exact commit with an empty status including untracked files.

#### Scenario: Exact clean lineage is available
- **WHEN** every bound file hash, configuration identity, immutable model revision, dependency version, Git identity, and clean-tree check agrees
- **THEN** the deterministic preflight result contains every required lineage field
- **AND** downstream execution can reproduce which inputs and plan were approved without claiming that execution occurred

#### Scenario: Worktree contains the review file as an untracked path
- **WHEN** any untracked or modified path is present at the execution boundary
- **THEN** preflight fails the clean-tree gate
- **AND** it does not ignore the path because its contents were hashed elsewhere

#### Scenario: Reviewed implementation is not committed
- **WHEN** tasks 6-9 exist only as a working diff or commit B lacks separate authorization
- **THEN** no canonical readiness PASS may be emitted
- **AND** temporary fixture success does not substitute for a clean committed run

### Requirement: Runtime identity is collected without framework imports
Preflight SHALL obtain distribution versions only through
`importlib.metadata.version("torch")` and
`importlib.metadata.version("sentence-transformers")`, without importing either
package. Missing metadata or any exact mismatch with config requirements fails
`PREFLIGHT_RUNTIME_INVALID`; local suffixes such as `+cu...` are preserved.

`platform_identity` SHALL contain exactly `python_implementation` from
`platform.python_implementation()`, `python_version` from
`platform.python_version()`, `system` from `platform.system()`, `release` from
`platform.release()`, and `machine` from `platform.machine()`. The first,
second, third, and fifth values MUST equal config requirements; release is
recorded but not user-selected. Hostname, executable path, IP, environment,
CUDA state, device count, and secrets MUST NOT be collected. Model revision
validation remains lexical and lineage-only; no network, cache, tokenizer, or
model lookup is allowed.

#### Scenario: Distribution metadata exists but a framework import would fail
- **WHEN** exact installed metadata matches and shadow framework imports create
  sentinels
- **THEN** runtime validation succeeds without touching the sentinels
- **AND** no import-based version fallback is attempted

### Requirement: Git identity is checked twice with exact bytes
Preflight SHALL run the following argument-array commands once before package
loading and again immediately before PASS, with `GIT_OPTIONAL_LOCKS=0`:
`git rev-parse --show-toplevel`, `git rev-parse HEAD`,
`git rev-parse HEAD^{tree}`, and
`git status --porcelain=v1 -z --untracked-files=all --ignore-submodules=none`.
The root must equal the expected worktree, HEAD must equal the independently
supplied `--expected-git-commit`, the two commit/tree pairs must match, and both
status byte strings must be empty. Config, training manifest, and every bound
lineage artifact must be tracked; `git show HEAD:<canonical-path>` bytes must
equal working-file bytes. A dirty-diff digest, ignore flag, submodule omission,
untracked allowance, or best-effort fallback is forbidden.

#### Scenario: State changes during preflight
- **WHEN** status, commit, tree, config, or a bound artifact differs between the
  two checks
- **THEN** preflight fails `PREFLIGHT_GIT_INVALID`
- **AND** no PASS is emitted even if all earlier computation succeeded

### Requirement: Preflight success and failure records are exact stdout contracts
Success SHALL emit exactly one compact sorted-key strict-UTF-8 JSON line to
stdout and no file. It SHALL contain exactly `schema_version`,
`artifact_version`, `policy_id`, `status`, `router_decision`,
`can_start_training`, `training_input_manifest_sha256`,
`source_manifest_sha256`, `source_candidates_sha256`,
`review_decisions_sha256`, `accepted_pairs_sha256`,
`qualification_report_sha256`, `split_manifest_sha256`,
`batch_plan_sha256`, `train_config_sha256`, `git_commit`, `git_tree_oid`,
`git_worktree_state`, `base_model_id`, `base_model_revision`, `seed`,
`dependency_versions`, `python_version`, `platform_identity`, `device_policy`,
`batch_plan`, and `non_actions`.

Constants are
`schema_version="router-v2-training-preflight-result-v1"`, integer version 1,
`policy_id="router-v2-training-preflight-v1"`,
`status="TRAINING_READY_PRECHECK=PASS"`,
`router_decision="KEEP_BASELINE"`, `can_start_training=false`, and
`git_worktree_state="CLEAN"`. `dependency_versions` contains exactly `torch`
and `sentence-transformers`; `platform_identity` has the exact runtime shape;
`python_version` exactly equals its nested counterpart. `non_actions` equals
the sorted list `blind_v2`, `checkpoint`, `deploy`, `gpu_access`,
`model_import`, `model_load`, `model_training`, `release`, `router_promotion`,
and `threshold_tuning`.

Failure SHALL emit no PASS and exactly one compact JSON line to stderr with
exact fields `schema_version="router-v2-training-preflight-error-v1"`, integer
`artifact_version=1`, `policy_id="router-v2-training-preflight-v1"`,
`status="TRAINING_READY_PRECHECK=FAIL"`,
`router_decision="KEEP_BASELINE"`, `can_start_training=false`, `error_code`,
and a sanitized single-line `error_detail` containing no prompt, reviewer,
path secret, environment, or connection value. Error code is exactly one of
`PREFLIGHT_ARGUMENT_INVALID`, `PREFLIGHT_CONFIG_INVALID`,
`TRAINING_INPUT_INVALID`, `BATCH_PLAN_INVALID`, `PREFLIGHT_GIT_INVALID`, or
`PREFLIGHT_RUNTIME_INVALID`.

#### Scenario: Invalid input reaches an error path
- **WHEN** any argument, config, package, batch, Git, or runtime gate fails
- **THEN** the command exits nonzero with the exact error schema on stderr and
  no stdout PASS
- **AND** error detail does not leak protected or private values

### Requirement: The preflight import graph and filesystem remain side-effect free
Before any project import, the script SHALL set `sys.dont_write_bytecode=True`
and initially import only the standard library. The v4 loader and planner may
then be imported only if their complete transitive graph is standard-library
only. On the preflight branch, imports of `torch`, `sentence_transformers`,
`hermes_skilleval.model_manifest`, `hermes_skilleval.embedding_training`,
`hermes_skilleval.remote_paths`, and
`hermes_skilleval.routers.embedding` are forbidden. Existing v3 execution
imports move behind the non-preflight boundary without changing v3 behavior.

Valid and invalid preflight MUST leave the requested output root absent when
it was absent, create no config, summary, manifest, model card, checkpoint,
log, cache, bytecode, or temporary output, and perform no CUDA query,
`nvidia-smi`, model-cache access, or model load. Fresh-process import and
filesystem sentinels prove these properties. Temporary fixtures may validate
pure objects, but only the separately authorized clean commit-B invocation is
canonical PASS.

#### Scenario: Invalid config fails before package loading
- **WHEN** preflight rejects config or CLI input
- **THEN** all framework/project import sentinels and output sentinels remain
  absent
- **AND** early failure is held to the same no-side-effect contract as success

### Requirement: Preflight status is distinct from training and promotion
The only success marker for this change SHALL be `TRAINING_READY_PRECHECK=PASS`. It means that reviewed input and the side-effect-free runtime bootstrap passed their declared gates. It MUST NOT be described as training started, training completed, checkpoint created, model improved, benchmark improved, candidate promoted, release approved, or production-ready. `router_decision` SHALL remain `KEEP_BASELINE` on every preflight surface.

#### Scenario: Preflight passes
- **WHEN** the command reports `TRAINING_READY_PRECHECK=PASS`
- **THEN** human- and machine-readable outputs state that no training, GPU job, checkpoint, blind-v2 run, threshold tuning, or promotion occurred
- **AND** the default router remains unchanged

### Requirement: Full training remains a separately authorized action
The trainer MUST require an explicit non-preflight invocation and all valid v4 gates before it could enter framework/model execution. This change's application and tests MUST NOT invoke that path. A successful preflight MUST NOT create authority for GPU/A100 work, training, release, deploy, or checkpoint publication.

#### Scenario: Change apply reaches final allowed state
- **WHEN** all source, review, package, and preflight tasks in this change are complete
- **THEN** the workflow stops at `TRAINING_READY_PRECHECK=PASS`
- **AND** no full training process, GPU/A100 job, checkpoint, blind-v2 run, threshold selection, release, or deploy is started
