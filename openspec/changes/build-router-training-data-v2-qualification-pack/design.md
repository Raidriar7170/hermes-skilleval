## Context

Phase 14 exported 28 rows from 12 non-blind migration tasks against the Phase 9 16-skill index: 16 positives and 12 negatives. Only the 19 `dev` rows are train-like; the 9 `test` rows were already consumed by held-out evaluation. The 11 train-like positives cover only 11 of 16 target skills, and every existing explicit negative crosses the target skill's ecosystem category.

Phase 16 is a permanent blind boundary. It preserved Recall@5 but increased Negative Hit Rate, so its committed decision remains `REVIEW_REQUIRED` / `KEEP_BASELINE`. Its tasks, prompt content, labels, and derived Phase 16/17/18 results cannot be used for candidate generation, negative mining, calibration, model selection, or training.

The non-blind migration corpus can still support an honest diagnostic expansion. The closed product of 12 tasks and 16 target skills contains 192 candidate pairs: 16 positives, 32 same-category negative candidates, and 144 cross-category easy negatives. Only 48 rows are positive or same-category candidates, only 32 of those belong to the train-like `dev` source split, and there are no reviewed reject/no-skill examples, explicit task-family metadata, independent calibration split, or human acceptance record. Quantity and qualification therefore remain distinct.

## Goals / Non-Goals

**Goals:**

- Build a deterministic, reviewable qualification pack for the current 16-skill migration-router universe.
- Classify every non-blind task-skill candidate without relabeling easy negatives as hard negatives.
- Preserve already-spent `test` tasks and pairs as reserved evidence rather than training candidates.
- Make source identity, candidate counts, blocker codes, and non-readiness machine-readable.
- Fail before task loading when a source path or task-directory identity crosses the blind boundary.
- Preserve all historical Phase 14/15/16 evidence byte-for-byte.

**Non-Goals:**

- Producing an accepted `training-pairs.jsonl`, training a model, creating a checkpoint, or running A100/GPU work.
- Reading or hashing blind prompt content, mining blind negatives, rerunning blind evaluation, tuning thresholds, or selecting/promoting a router.
- Combining the unrelated 45-skill benchmark universe with the current 16-skill migration router.
- Inventing reject prompts, semantic family IDs, teacher scores, cross-encoder labels, or human acceptance evidence.
- Merging, pushing, publishing, releasing, or archiving the change.

## Decisions

### 1. Freeze one target universe

The canonical pack uses `benchmarks/migration-tasks` and `docs/demo/phase9-real-skill-library-migration/skills.json`. The builder validates that every gold and explicit-negative reference exists in that index and that every task's gold skills belong to one ecosystem category.

The 80-task/45-skill corpus is excluded even though it could produce 100–200 rows. Its taxonomy is not the Phase 14/16 target universe, so mixing it in would make pair volume look better while weakening provenance and comparability.

### 2. Reject blind sources before loading prompt content

The CLI command `qualify-router-training-data-v2` runs a path/identity preflight before calling `load_tasks()`. It resolves the source root, every discovered task directory, and each `task.yaml` / `prompt.md` file; any real path containing `blind-migration-tasks` is rejected. It also rejects a task-directory basename beginning `blind-`, reads only `task.yaml` during preflight, and rejects a metadata `id` beginning `blind-` before the prompt loader can run. The loaded task identities are checked again as defense in depth.

The pack does not accept a blind-root argument and does not calculate blind prompt hashes. This is intentional: consulting blind prompts to filter or select training candidates would itself contaminate the data-selection process. Protected Phase 14/15/16/17/18 blob identities are verified separately at the Git boundary.

### 3. Emit candidates, not trainer-ready rows

A new `router_training_data_v2.py` module builds the sorted product of task ID and skill ID. Each JSONL record contains stable identity, the original source split, prompt hash, task/skill text, label, candidate type, source provenance, and disposition.

Candidate types are:

- `positive`: the skill is in `gold_skills`;
- `same_category_negative_candidate`: the non-gold skill shares the gold ecosystem category and still requires review before it can be called a hard negative;
- `cross_category_easy_negative`: the non-gold skill is outside that category and is never counted toward the qualified-pair target.

The row schema is fixed at `router-training-data-v2-candidate-v1`. Task and skill IDs containing `/` are rejected so `pair_id=<task-id>/<skill-id>` cannot collide; `prompt_text_sha256` hashes the UTF-8 loaded prompt text after the loader's surrounding-whitespace normalization, while manifest file hashes cover raw file bytes. Rows are ordered by `(task_id, skill_id)` and use exactly these dispositions:

- `TRAIN_CANDIDATE_POSITIVE` for a `dev` positive;
- `REVIEW_REQUIRED_NEGATIVE_CANDIDATE` for a `dev` same-category negative candidate;
- `EXCLUDED_EASY_NEGATIVE` for a `dev` cross-category easy negative;
- `RESERVED_SOURCE_TEST` for every row derived from a source `test` task.

All rows set `accepted_for_training=false`. This does not erase source evidence: the canonical report separately records 11 `dev` positives covering 11/16 skills, 21 `dev` same-category review candidates, 32 total train-policy candidates, 0 accepted train pairs, 64 reserved matrix rows, and 16 reserved positive-or-same-category candidates. No `training-pairs.jsonl` is written by version 1.

Alternatives rejected:

- **Keep the 28-row Phase 14 classification:** it preserves the misleading claim that all 12 explicit negatives are hard negatives.
- **Call every non-gold skill a hard negative:** 144 of 176 non-gold rows cross category and are easy negatives.
- **Copy test rows into training:** those rows already support held-out evidence and are not fresh training data.
- **Generate synthetic reject prompts:** no reviewed source currently proves those prompts have no suitable skill.

### 4. Separate candidate volume from qualification

`qualification-report.json` always records `qualification_status="REVIEW_REQUIRED"`, `router_decision="KEEP_BASELINE"`, and `can_start_training=false` in version 1. The command is a diagnostic snapshot, not a state machine that can become ready: it intentionally accepts no reviewed-negative, reject, task-family, calibration-split, or human-acceptance inputs. The report evaluates and exposes these future readiness requirements without claiming it can satisfy them:

1. accepted train-pair count is within 100–200;
2. train positives cover all 16 target skills;
3. same-category negative candidates have explicit review acceptance;
4. at least one reviewed true reject/no-skill example exists;
5. every task has explicit family metadata and families do not cross train, calibration, and test;
6. train, calibration, and test are all non-empty and prompt/task identities do not cross them;
7. a human acceptance record covers the exact input/output hashes.

The canonical report contains exactly these blocker codes, sorted lexically:

- `INDEPENDENT_CALIBRATION_SPLIT_MISSING`
- `MANUAL_ACCEPTANCE_MISSING`
- `PAIR_COUNT_BELOW_MINIMUM`
- `REJECT_EXAMPLES_MISSING`
- `SAME_CATEGORY_NEGATIVES_UNREVIEWED`
- `TARGET_POSITIVE_COVERAGE_INCOMPLETE`
- `TASK_FAMILY_METADATA_MISSING`
- `TASK_FAMILY_SPLIT_NOT_INDEPENDENT`

Its canonical counts are: 28 source pairs; 192 matrix candidates; 16 positives; 32 same-category negative candidates; 144 easy negatives; 32 train-policy candidates; 0 accepted train pairs; 64 reserved matrix rows; 11/16 train-positive skill coverage; and 0 reject examples.

Blind-source identity violations are harder failures: the command exits before writing a pack instead of recording a reviewable blocker.

### 5. Make provenance and regeneration self-contained

The committed directory is:

```text
docs/demo/router-training-data-v2-qualification-pack/
├── README.md
├── candidate-pairs.jsonl
├── manifest.json
└── qualification-report.json
```

The manifest records `policy_id="router-training-data-v2-qualification-v1"`, schema/artifact versions, logical input paths relative to the discovered repository root, SHA-256 hashes for every non-blind `task.yaml` and `prompt.md`, the canonical skill index hash, output hashes for the candidate matrix and report, deterministic ordering rules, counts, and explicit non-actions. It does not hash itself and does not record machine-specific absolute output paths. Inputs outside the discovered repository root are rejected because they cannot have portable logical identities in this version.

Before writing, the command resolves the requested absent target with `Path.resolve(strict=False)`, which resolves every existing symlink ancestor, and compares that real target in both directions with the resolved protected paths. It rejects a target that already exists, lies within, or contains any protected path:

- `docs/demo/phase14-finetuned-embedding-router`
- `docs/demo/phase15-held-out-generalization`
- `docs/demo/phase16-blind-validation`
- `docs/demo/phase17-calibrated-release-selector`
- `docs/demo/phase18-ci-release-reproducibility`

The pack is written into a fresh temporary sibling under the resolved safe parent and atomically renamed to the resolved absent target. Failure removes the temporary directory, so no partial pack or stale `training-pairs.jsonl` can survive. The requested pack is the only persistent output; the temporary sibling is an implementation detail and never remains after success or failure.

The README contains only a regeneration command targeting a newly created temporary destination, byte/hash comparison instructions against the committed pack, authority links, expected `REVIEW_REQUIRED` state, artifact roles, and non-claims. It never instructs the user to overwrite the existing committed target. The Chinese Human Brief is generated from these sources and does not become a second source of truth.

### 6. Keep the implementation isolated from Phase 14 behavior

The existing `export_embedding_training_pairs()` API and committed Phase 14 artifacts remain unchanged. The new builder and CLI command are independent, import no training frameworks, invoke no subprocess, and write only the requested qualification-pack directory.

## Risks / Trade-offs

- **[A 192-row matrix may be mistaken for 192 qualified examples]** → Use `candidate-pairs.jsonl`, report the positive/same-category/easy split, omit `training-pairs.jsonl`, and keep `can_start_training=false`.
- **[Same-category candidates may still be false negatives]** → Name them candidates, require explicit acceptance, and keep `SAME_CATEGORY_NEGATIVES_UNREVIEWED` blocking.
- **[Source `dev`/`test` labels may be mistaken for independent train/calibration/test]** → Preserve them as `source_split`, reserve all test rows, and fail the family/calibration gates.
- **[Blind contamination occurs during validation]** → Resolve root/directory/file symlinks, read only task metadata for `blind-*` ID preflight, and do not read or hash blind prompt content.
- **[Manifest paths become machine-specific]** → Record logical relative inputs and content hashes, not resolved absolute output paths.
- **[Historical evidence is accidentally regenerated]** → Reject protected or existing output targets, publish atomically, and compare the five protected directory inventories against apply base `aec4a09e7a60a5a1eb534b4198078acc24ff5cd5` after apply.

## Migration Plan

1. Add RED tests for symlink/metadata-aware path preflight, deterministic classification, exact schema/counts/blockers, output-path protection, atomic publication, hashing, and CLI output.
2. Implement the independent builder and CLI command, then generate the canonical blocked pack.
3. Add artifact-contract tests, the regeneration README, and the Chinese Human Brief.
4. Run focused/full tests, Ruff, strict OpenSpec validation, release checks, JSON/JSONL/hash/determinism checks, protected-evidence identity checks, and read-only review.
5. Stop at the local publication gate. A later OpenSpec change may curate new accepted pairs, reject examples, family metadata, and calibration splits; it must not silently loosen this gate.

Rollback is deletion of the local branch/worktree before publication. No external state changes are part of this apply.

## Open Questions

None. Supplying teacher labels, a reviewed reject corpus, semantic family metadata, or another skill universe changes the approved scope and requires a new proposal or explicit amendment.
