# Router Training Data V2 Qualification Pack

This is a deterministic diagnostic qualification snapshot, not accepted training
data. Its current decision is `REVIEW_REQUIRED` / `KEEP_BASELINE`, and
`can_start_training=false`.

## What is authoritative

- [Proposal](../../../openspec/changes/archive/2026-07-11-build-router-training-data-v2-qualification-pack/proposal.md)
- [Design](../../../openspec/changes/archive/2026-07-11-build-router-training-data-v2-qualification-pack/design.md)
- [Specification](../../../openspec/changes/archive/2026-07-11-build-router-training-data-v2-qualification-pack/specs/router-training-data-v2-qualification-pack/spec.md)
- [Tasks](../../../openspec/changes/archive/2026-07-11-build-router-training-data-v2-qualification-pack/tasks.md)
- [Candidate matrix](candidate-pairs.jsonl)
- [Qualification report](qualification-report.json)
- [Provenance manifest](manifest.json)
- [Artifact-contract tests](../../../tests/test_router_training_data_v2_artifacts.py)

The OpenSpec artifacts define the lifecycle and policy. The JSON/JSONL files and
tests are the machine-readable evidence. This README is only a navigation and
regeneration aid.

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
row has `accepted_for_training=false`; source-test rows remain reserved, and no
`training-pairs.jsonl` exists.

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

- `candidate-pairs.jsonl`: `fbfc626d0b5fa98f3eb505042a3bf002d697ec0ca9ea1328edec6fd637cb82c3`
- `qualification-report.json`: `7a5b61ec9245cb6ffbdb514899c637005652382cd6db4a19b7fafcff5c6d62d7`
- `manifest.json`: `b1f8fb98b9eac2f21bed137506eec63d678053d03205ce0248b843fc3e5a80ab`

## Lifecycle truth

The OpenSpec change `build-router-training-data-v2-qualification-pack` is
archived (`OPENSPEC_ARCHIVED`). The archive branch
`ops/archive-build-router-training-data-v2-qualification-pack` has been pushed
(`BRANCH_PUSHED`). No PR has been opened for this branch (`NO_PR`), and this
branch has not been merged to `main` (`NO_MAIN_MERGE`).

## Boundaries and non-claims

This phase did not train or fine-tune a router (`NO_TRAINING`), read or hash
blind prompt content, run an A100/GPU job (`NO_A100_GPU_JOB`), create a
checkpoint (`NO_CHECKPOINT`), calibrate a threshold, select or promote a model,
or rerun blind evaluation (`NO_BLIND_RERUN`). It did not establish a
benchmark improvement or change `KEEP_BASELINE`. This archive/truth-surface
change created no new tag, release, or deploy (`NO_TAG`, `NO_RELEASE`,
`NO_DEPLOY`). Candidate volume is not qualified-pair volume, and this pack does
not authorize training or a public performance claim.
