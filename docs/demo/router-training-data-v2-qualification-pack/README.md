# Router Training Data V2 Qualification Pack

This is the current deterministic prompt-only v2 diagnostic qualification
snapshot, not accepted training data. Its decision remains `REVIEW_REQUIRED` / `KEEP_BASELINE`,
and `can_start_training=false`.

## What is authoritative

- [Active proposal](../../../openspec/changes/make-router-training-data-v2-primary-prompt-only/proposal.md)
- [Active design](../../../openspec/changes/make-router-training-data-v2-primary-prompt-only/design.md)
- [Active delta specification](../../../openspec/changes/make-router-training-data-v2-primary-prompt-only/specs/router-training-data-v2-qualification-pack/spec.md)
- [Active tasks](../../../openspec/changes/make-router-training-data-v2-primary-prompt-only/tasks.md)
- [Candidate matrix](candidate-pairs.jsonl)
- [Qualification report](qualification-report.json)
- [Provenance manifest](manifest.json)
- [Artifact-contract tests](../../../tests/test_router_training_data_v2_artifacts.py)
- [Current v2 apply brief](../../../docs/human-briefs/2026-07-11-make-router-training-data-v2-primary-prompt-only-apply.html)
- [Historical v1 brief](../../../docs/human-briefs/2026-07-11-build-router-training-data-v2-qualification-pack.html)

The OpenSpec artifacts define the lifecycle and policy. The JSON/JSONL files and
tests are the machine-readable evidence. This README is only a navigation and
regeneration aid.

## Prompt-only v2 contract

The only primary query is the loaded prompt:

`query_text == loader-normalized task.prompt`

Every candidate row sets `query_text_policy="prompt_only"`, and
`sha256(query_text.encode("utf-8")) == prompt_text_sha256`. Task ID, category,
difficulty, and robustness tags remain structured validation, classification,
split, or provenance inputs; they are not serialized into the primary query.
There is no legacy, alternate, composite, or second query representation.

Current identifiers are:

- candidate: `router-training-data-v2-candidate-v2`
- policy: `router-training-data-v2-qualification-v2`
- report: `router-training-data-v2-qualification-report-v2`
- manifest: `router-training-data-v2-manifest-v2`, `artifact_version=2`

## Current result

- Source pairs: 28
- Matrix candidates: 192
- Positives: 16
- Same-category negative candidates requiring review: 32
- Cross-category easy negatives: 144
- Train-policy candidates: 32
- Accepted training pairs: 0
- Reserved source-test rows: 64
- Train-positive target-skill coverage: 11/16
- Reviewed reject/no-skill examples: 0

The eight blocking codes are:

1. `INDEPENDENT_CALIBRATION_SPLIT_MISSING`
2. `MANUAL_ACCEPTANCE_MISSING`
3. `PAIR_COUNT_BELOW_MINIMUM`
4. `REJECT_EXAMPLES_MISSING`
5. `SAME_CATEGORY_NEGATIVES_UNREVIEWED`
6. `TARGET_POSITIVE_COVERAGE_INCOMPLETE`
7. `TASK_FAMILY_METADATA_MISSING`
8. `TASK_FAMILY_SPLIT_NOT_INDEPENDENT`

`candidate-pairs.jsonl` is a closed 12-task by 16-skill diagnostic matrix. Every
row has `accepted_for_training=false`; source-test rows remain reserved, and
neither `training-pairs.jsonl` nor `training-pairs-v2.jsonl` exists.

## Reproduce without overwriting the committed pack

Run from the repository root. The CLI requires an absent target, so this command
creates a temporary directory and writes into its fresh, absent `pack` child.
It then compares all generated machine-readable artifacts byte-for-byte and by
SHA-256 with the committed snapshot.

```bash
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/hermes-router-v2.XXXXXX")"
OUT="$TMP_ROOT/pack"
trap 'rm -rf "$TMP_ROOT"' EXIT

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m hermes_skilleval.cli \
  qualify-router-training-data-v2 \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --output-dir "$OUT"

for name in candidate-pairs.jsonl qualification-report.json manifest.json; do
  cmp "docs/demo/router-training-data-v2-qualification-pack/$name" "$OUT/$name"
  shasum -a 256 \
    "docs/demo/router-training-data-v2-qualification-pack/$name" \
    "$OUT/$name"
done
```

Expected committed SHA-256 values:

- `candidate-pairs.jsonl`: `e70006f3124f496a7e0005a081db06527391167bd380574b08c7991bcf2c6475`
- `qualification-report.json`: `d36afe875f2ada4e38ac3b707ced5bbb27c89262aad403793b7ee68058dd2395`
- `manifest.json`: `883e7d8a35622b89a243a373304bd5e9e570275649bd22d01e9a8799c674daaf`

## Lifecycle truth

The active OpenSpec change is
`make-router-training-data-v2-primary-prompt-only`. Its local apply surface is
complete for user review (`APPLY_COMPLETE_LOCAL` / `USER_REVIEW_REQUIRED`) and
the change remains active and unarchived. HEAD
`e822d9c489ca39180b556000dc3e361552d6c75e` is the proposal commit. The current
apply diff is uncommitted and has not been pushed, opened as a PR, merged, or
archived.

## Release reproducibility replay truth

Task 7.4 performed a validation-only reproducibility replay. It replayed the
frozen release selector using committed/frozen Phase 16 aggregate artifacts and
wrote fresh temporary Phase 17/18 outputs. It did not read blind prompts or rerun
blind evaluation. It did not use new data or tuning to make a new router choice.
It did not promote or adopt a candidate router and did not change the router
decision; the reproduced result remained `KEEP_BASELINE`.

## Boundaries and non-claims

This apply did not train or fine-tune a router (`NO_TRAINING`), read or hash
blind prompt content, run an A100/GPU job (`NO_A100_GPU_JOB`), create a
checkpoint (`NO_CHECKPOINT`), or rerun blind evaluation (`NO_BLIND_RERUN`). The
validation replay above used no new training data, calibration, or threshold
tuning and established no benchmark improvement or model improvement
(`NO_PERFORMANCE_CLAIM`). `NO_COMMIT` applies to the current apply diff; that
diff also has no push, PR, merge, archive, tag, release, or deploy (`NO_PUSH`,
`NO_PR`, `NO_MERGE`, `NO_ARCHIVE`, `NO_TAG`, `NO_RELEASE`, `NO_DEPLOY`).
Candidate volume is not qualified-pair volume, and this pack does not authorize
training or a public performance claim.
