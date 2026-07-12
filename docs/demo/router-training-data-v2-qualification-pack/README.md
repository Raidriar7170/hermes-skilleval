# Router Training Data V2 Qualification Pack

This is the current deterministic prompt-only v3 diagnostic qualification snapshot,
not accepted training data. Its decision remains `REVIEW_REQUIRED` / `KEEP_BASELINE`,
and `can_start_training=false`.

## What is authoritative

- [Current proposal](../../../openspec/changes/harden-router-v2-pretraining-contracts/proposal.md)
- [Current design](../../../openspec/changes/harden-router-v2-pretraining-contracts/design.md)
- [Router query contract](../../../openspec/changes/harden-router-v2-pretraining-contracts/specs/router-query-contract/spec.md)
- [Qualification-pack contract](../../../openspec/changes/harden-router-v2-pretraining-contracts/specs/router-training-data-v2-qualification-pack/spec.md)
- [Training-input gate contract](../../../openspec/changes/harden-router-v2-pretraining-contracts/specs/router-training-input-gate/spec.md)
- [Current tasks](../../../openspec/changes/harden-router-v2-pretraining-contracts/tasks.md)
- [Candidate matrix](candidate-pairs.jsonl)
- [Qualification report](qualification-report.json)
- [Provenance manifest](manifest.json)
- [Shared query source](../../../src/hermes_skilleval/router_query.py)
- [Qualification builder source](../../../src/hermes_skilleval/router_training_data_v2.py)
- [Training-input gate source](../../../src/hermes_skilleval/training_input.py)
- [Trainer bootstrap](../../../scripts/train_embedding_router.py)
- [Query-contract tests](../../../tests/test_router_query_contract.py)
- [Qualification builder tests](../../../tests/test_router_training_data_v2.py)
- [Artifact and documentation tests](../../../tests/test_router_training_data_v2_artifacts.py)
- [Training-input gate tests](../../../tests/test_training_input.py)
- [Current v3 Human Brief](../../../docs/human-briefs/2026-07-12-harden-router-v2-pretraining-contracts.html)
- [Historical v2 apply brief](../../../docs/human-briefs/2026-07-11-make-router-training-data-v2-primary-prompt-only-apply.html)

OpenSpec defines the lifecycle and contracts. Source, tests, and the JSON/JSONL
artifacts are the authoritative implementation and evidence. This README is a
review/navigation aid, not a second source of truth.

## Prompt-only v3 contract

The only task-side formatter is `router_query_text(prompt: str)`, and the only
primary query is the loaded prompt:

`query_text == loader-normalized task.prompt`

Every candidate row sets `query_text_policy="prompt_only"`, and
`sha256(query_text.encode("utf-8")) == prompt_text_sha256`. Task ID, category,
difficulty, robustness tags, split, and family remain structured validation,
classification, split, or provenance fields only. They are not serialized into
the task query or used as a scoring, ranking, gating, tie-break, or acceptance
feature. There is no legacy, alternate, composite, or second task query.

Current identifiers are:

- candidate: `router-training-data-v2-candidate-v3`, `artifact_version=3`
- policy: `router-training-data-v2-qualification-v3`
- report: `router-training-data-v2-qualification-report-v3`, `artifact_version=3`
- manifest: `router-training-data-v2-manifest-v3`, `artifact_version=3`

## Current qualification truth

- Source pairs: 28
- Matrix candidates: 192
- Positives: 16
- Same-category negative candidates requiring review: 32
- Cross-category easy negatives: 144
- Reserved source-test rows: 64
- Train-policy candidates: 32
- Accepted training pairs: 0
- Train-positive target-skill coverage: 11/16
- Reviewed reject/no-skill examples: 0

`candidate-pairs.jsonl` is a closed 12-task by 16-skill diagnostic matrix.
Candidate rows are diagnostic candidates, not qualified training data. Every row
has `accepted_for_training=false`; reserved source-test rows do not flow back into
training, and cross-category easy negatives do not count toward accepted volume.

The eight blocking codes are:

1. `INDEPENDENT_CALIBRATION_SPLIT_MISSING`
2. `MANUAL_ACCEPTANCE_MISSING`
3. `PAIR_COUNT_BELOW_MINIMUM`
4. `REJECT_EXAMPLES_MISSING`
5. `SAME_CATEGORY_NEGATIVES_UNREVIEWED`
6. `TARGET_POSITIVE_COVERAGE_INCOMPLETE`
7. `TASK_FAMILY_METADATA_MISSING`
8. `TASK_FAMILY_SPLIT_NOT_INDEPENDENT`

## Diversity diagnostics

- Unique prompts: 12
- Train-policy unique prompts: 8
- Unique task family count: `null`
- Family-independent count: `null`
- Family metadata status: `UNAVAILABLE`

Missing task-family metadata is not inferred. Unique train-positive prompt counts
are recorded for all 16 canonical skills:

- `accessibility-tree-inspection`: `0`
- `apply-patch-discipline`: `1`
- `browser-smoke-testing`: `1`
- `evidence-backed-final`: `1`
- `form-interaction-flow`: `1`
- `mcp-tool-routing`: `0`
- `plan-mode`: `1`
- `slash-command-workflow`: `1`
- `subagent-worker-protocol`: `1`
- `systematic-debugging`: `1`
- `task-tool-delegation`: `0`
- `test-driven-development`: `1`
- `using-git-worktrees`: `0`
- `verification-before-completion`: `1`
- `visual-regression-review`: `1`
- `workspace-git-hygiene`: `0`

## Trainer admission gate

The trainer accepts only an exact
`router-training-data-v2-training-input-manifest-v3` package under policy
`router-training-data-v2-training-admission-v3`. Only formally reviewed positives
and human-reviewed hard negatives can pass: respectively `ACCEPTED_POSITIVE` and
`ACCEPTED_HARD_NEGATIVE`, with exact evidence, hashes, provenance, and a bound
training-ready v3 qualification report. The current canonical pack is rejected by
the v3 trainer gate because it has eight blockers, zero accepted pairs, and
`can_start_training=false`. No compatibility inference or partial consumption is
allowed.

`source_hash` and `acceptance_hash` protect content and acceptance-decision
integrity; they do not establish source authenticity. Independent source-snapshot
binding, human review, and independent calibration remain prerequisites.

## Reproduce without overwriting the committed pack

Run from the repository root. The CLI requires an absent output target. This writes
to a fresh temporary child, then compares all three generated artifacts against the
canonical snapshot; it never passes the canonical pack as `--output-dir`.

```bash
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/hermes-router-v3.XXXXXX")"
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

Expected canonical SHA-256 values:

- `candidate-pairs.jsonl`: `fff59d8ddc199a4579dcf831fa806fa0b2ef761465a7bde7acd77dc967f41b45`
- `qualification-report.json`: `edb1b1111e24c8866bda6edca776129d4952ef38d23c017c753586dd6ef77e3b`
- `manifest.json`: `da97accd98e3af5113a962423ff79a8235f4388b4e2fd2d0ff7aeb3931f6c449`

Neither `training-pairs.jsonl`, `training-pairs-v2.jsonl`, an accepted-pair v3
artifact, nor a real training-input manifest is generated.

## Lifecycle truth and non-claims

The active OpenSpec change is `openspec/changes/harden-router-v2-pretraining-contracts`.
Current state is `LOCAL_WORKING_DIFF` on branch
`agent/harden-router-v2-pretraining-contracts`, with base HEAD
`f996690700a79ab4c065ed8523340d2fd387f6b9`. The current v3 diff is uncommitted,
unpushed, has no PR, is unmerged, and the change is active and unarchived. Because
the branch is unpushed, remote CI is unavailable; local checks are not remote CI.

This change did not train or fine-tune a router, read or hash blind prompt content,
run an A100/GPU job, create or load a model, create a checkpoint, run blind-v2, or
establish a benchmark improvement. It did not merge, archive, tag, release, or
deploy this v3 working diff. Phase 14–18 and blind evidence remain unchanged.
Candidate volume is not qualified-pair volume, and this pack does not authorize
training or a public performance claim.
