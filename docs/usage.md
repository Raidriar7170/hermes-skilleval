# Hermes SkillEval CLI Usage

This page keeps the longer command walkthrough out of the README front door.
For the current release conclusion and reviewer evidence, start from
[`docs/release-handoff.md`](release-handoff.md).
For local reviewer navigation across release, diagnostic, CI, OpenSpec, and
Human Brief evidence, see [`docs/evidence-map.md`](evidence-map.md); it is a
navigation layer, not a second source of truth, and not release approval.
For concrete blocked-regression and diagnostic-risk examples, use
[`docs/failure-gallery.md`](failure-gallery.md) as a review aid.
For current patch release notes, use
[`docs/release-notes/v0.2.1.md`](release-notes/v0.2.1.md). For the historical
pre-publish v0.2.0 release decision package, use
[`docs/demo/v0.2.0-release-decision/release-decision.md`](demo/v0.2.0-release-decision/release-decision.md);
it records `NEEDS_REVIEW`, `KEEP_BASELINE`, and `Published: false` for human
release review, not the current publication record.
For the v0.2.0 release notes and v0.2.0 final approval checklist, use
[`docs/release-notes/v0.2.0.md`](release-notes/v0.2.0.md) and
[`docs/demo/v0.2.0-final-approval/final-approval.md`](demo/v0.2.0-final-approval/final-approval.md);
the release notes summarize implemented capabilities and the checklist records
the historical pre-publish human GO/NO-GO gate. Current post-release facts live
in [`docs/demo/v0.2.0-post-release/post-release.md`](demo/v0.2.0-post-release/post-release.md).

## Installation

```bash
git clone https://github.com/Raidriar7170/hermes-skilleval.git
cd hermes-skilleval

python -m venv .venv
source .venv/bin/activate

python -m pip install -e "."
```

Install optional neural routing backends:

```bash
python -m pip install -e ".[dev,embedding]"
```

## Fresh-clone local demo

Run this path from a fresh clone to exercise committed fixtures only. It uses
repo-relative paths and temporary outputs, with no credentials, SaaS, runtime
MCP service, browser cache, private directory, or network-only model download.

```bash
python -m pip install -e ".[dev]"

TMP_ROOT="${TMPDIR:-/tmp}/hermes-skilleval-fresh-clone"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT"

skilleval scan \
  examples/github-action/skills \
  --output "$TMP_ROOT/skills.json"

skilleval route \
  "audit workflow evidence before release" \
  --index "$TMP_ROOT/skills.json" \
  --top-k 2 \
  --output "$TMP_ROOT/route.json"

skilleval github-action-gate \
  --skill-path examples/github-action/skills \
  --benchmark-path examples/github-action/benchmark \
  --min-recall-at-k 1.0 \
  --max-negative-hit-rate 0.0 \
  --output-dir "$TMP_ROOT/gate"

printf 'README.md\n' > "$TMP_ROOT/changed-files.txt"

skilleval ci-summary \
  --check github-action-gate=success \
  --changed-files "$TMP_ROOT/changed-files.txt" \
  --overclaim-root README.md \
  --output "$TMP_ROOT/ci-summary.json" \
  --markdown-output "$TMP_ROOT/ci-summary.md"
```

Expected local result: the gate writes `ALLOW_MERGE` to
`$TMP_ROOT/gate/ci-summary.md`, and the CI summary writes local JSON/Markdown
without calling the GitHub API.

## GitHub Action trial

To try the released repository Action in another repository, copy
`examples/github-action/skills/`, `examples/github-action/benchmark/`, and the
workflow shape below. The Action writes GitHub Actions step summary content and
uploadable gate artifacts, and it does not require a GitHub API token.

```yaml
name: SkillEval Gate

on:
  pull_request:
  workflow_dispatch:

jobs:
  skilleval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - uses: Raidriar7170/hermes-skilleval@v0.2.1
        with:
          skill-path: skills
          benchmark-path: benchmark
          min-recall-at-k: "1.0"
          max-negative-hit-rate: "0.0"
          upload-artifacts: "true"
```

Expected summary behavior: a matching fixture produces `ALLOW_MERGE`; a
regression that misses a gold skill or selects a negative skill produces
`BLOCK_MERGE`. See [`docs/demo-repo-plan.md`](demo-repo-plan.md) for the future
external demo repository plan.

## Diagnostic Onboarding Path

Use these commands when you have a real skill or tool library but have not yet
written gold/negative benchmark labels. Diagnostic commands require explicit
`--output` paths so the JSON artifacts can be reviewed and compared later.

### Scan a Markdown skill folder

```bash
skilleval scan \
  benchmarks/skills \
  --output runs/diagnostic/scan.json
```

The scan artifact contains normalized skills, source paths, routing cues, and
parser warnings. The same command also accepts an MCP tool schema file such as
`mcp.json`:

```bash
skilleval scan \
  path/to/mcp.json \
  --output runs/diagnostic/mcp-scan.json
```

### Lint routing clarity

```bash
skilleval lint \
  --index runs/diagnostic/scan.json \
  --output runs/diagnostic/lint.json
```

`lint` reports routing clarity findings such as missing descriptions, weak
activation cues, missing negative boundaries, and overly generic cues. It is not
a general Markdown or prose-style linter.

### Inspect conflict risk clusters

```bash
skilleval inspect \
  --index runs/diagnostic/scan.json \
  --output runs/diagnostic/inspect.json
```

`inspect` writes explainable conflict risk clusters from visible signals such as
token overlap, trigger-term overlap, category proximity, missing boundaries, and
local route co-appearance. These clusters are review-worthy risk signals, not
definitive verdicts.

### Route an unlabeled query

```bash
skilleval route \
  "debug failing tests with a red-green loop" \
  --index runs/diagnostic/scan.json \
  --inspect runs/diagnostic/inspect.json \
  --top-k 5 \
  --output runs/diagnostic/route.json
```

The route artifact includes top-k candidates, scores, matched evidence terms,
source fields, and risk flags from weak boundaries or conflict clusters.

### Render the diagnostic dashboard

```bash
skilleval diagnostic-dashboard \
  --scan runs/diagnostic/scan.json \
  --lint runs/diagnostic/lint.json \
  --inspect runs/diagnostic/inspect.json \
  --route runs/diagnostic/route.json \
  --output runs/diagnostic/dashboard.html
```

The generated HTML is self-contained and focuses on source summaries,
routing-readiness findings, route examples, and conflict risk clusters. These
diagnostic artifacts can feed labeled regression work and artifact-based CI
validation, but this path is not a Marketplace Action, not a PR annotation
system, not SaaS, not a runtime MCP router, and not a SOTA claim.

### Run the diagnostic CI gate

`skilleval diagnostic-ci-gate` validates already generated diagnostic artifacts
against explicit thresholds. Use non-zero thresholds when a known demo or skill
library intentionally contains warnings, review-worthy conflict clusters, or
route risk flags:

```bash
skilleval diagnostic-ci-gate \
  --scan runs/diagnostic/scan.json \
  --lint runs/diagnostic/lint.json \
  --inspect runs/diagnostic/inspect.json \
  --route runs/diagnostic/route.json \
  --output runs/diagnostic/ci-gate-report.json \
  --markdown-output runs/diagnostic/ci-gate-report.md \
  --max-lint-findings 0 \
  --max-conflict-clusters 0 \
  --max-route-risk-flags 0 \
  --min-route-candidates 1
```

In GitHub Actions, the repository workflow reads the committed diagnostic demo
artifacts for the gate report and writes that report to `$RUNNER_TEMP`. The
same validate job also regenerates the diagnostic onboarding demo into
`$RUNNER_TEMP/diagnostic-onboarding` and runs the artifact drift check below,
with drift reports written outside the repository checkout.

### Check diagnostic artifact drift

`skilleval diagnostic-artifact-drift-check` compares expected and actual
diagnostic artifacts after normalizing approved volatile fields such as
`generated_at` and local artifact path displays. Use it after regenerating
artifacts into a temporary directory:

```bash
TMP_ROOT="${TMPDIR:-/tmp}/diagnostic-onboarding"

skilleval diagnostic-artifact-drift-check \
  --expected docs/demo/diagnostic-onboarding \
  --actual "$TMP_ROOT" \
  --output "$TMP_ROOT/diagnostic-artifact-drift.json" \
  --markdown-output "$TMP_ROOT/diagnostic-artifact-drift.md"
```

The drift check is local semantic artifact comparison. It does not call the
GitHub API, post PR comments, write annotations, publish a Marketplace Action,
run a SaaS service, act as a runtime MCP router, or approve a release.

In the GitHub Actions validate workflow, the drift JSON report is written to
`$RUNNER_TEMP/diagnostic-artifact-drift.json` and the Markdown report is
written to `$RUNNER_TEMP/diagnostic-artifact-drift.md`.

### Generate a local PR review packet

`skilleval diagnostic-pr-review-surface` turns an existing diagnostic CI gate
report into JSON and Markdown that a maintainer can review or paste into a pull
request discussion:

```bash
skilleval diagnostic-pr-review-surface \
  --gate-report runs/diagnostic/ci-gate-report.json \
  --output runs/diagnostic/pr-review-packet.json \
  --markdown-output runs/diagnostic/pr-review-packet.md
```

The packet uses the CI gate report as its verdict source and summarizes
review-worthy lint findings, conflict clusters, route risk flags, evidence
gaps, and source artifacts. It is a local review surface only: it does not call
the GitHub API, post PR comments, write annotations, publish a Marketplace
Action, run a SaaS service, or act as a runtime MCP router.

### Regenerate the committed diagnostic demo evidence pack

The committed demo under `docs/demo/diagnostic-onboarding/` uses a small local
Markdown skill source to make the diagnostic workflow inspectable without
preparing a separate library. Run these commands from the repository root:

```bash
ROOT=docs/demo/diagnostic-onboarding

TMP_ROOT="${TMPDIR:-/tmp}/diagnostic-onboarding"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT"

PYTHONPATH=src python -m hermes_skilleval.cli scan \
  "$ROOT/source/skills" \
  --output "$TMP_ROOT/scan.json"

PYTHONPATH=src python -m hermes_skilleval.cli lint \
  --index "$TMP_ROOT/scan.json" \
  --output "$TMP_ROOT/lint.json"

PYTHONPATH=src python -m hermes_skilleval.cli inspect \
  --index "$TMP_ROOT/scan.json" \
  --output "$TMP_ROOT/inspect.json"

PYTHONPATH=src python -m hermes_skilleval.cli route \
  "smoke test a local browser page and check console errors" \
  --index "$TMP_ROOT/scan.json" \
  --inspect "$TMP_ROOT/inspect.json" \
  --top-k 3 \
  --output "$TMP_ROOT/route-browser-smoke.json"

PYTHONPATH=src python -m hermes_skilleval.cli route \
  "debug failing tests with a red-green loop" \
  --index "$TMP_ROOT/scan.json" \
  --inspect "$TMP_ROOT/inspect.json" \
  --top-k 3 \
  --output "$TMP_ROOT/route-debug-red-green.json"

PYTHONPATH=src python -m hermes_skilleval.cli diagnostic-dashboard \
  --scan "$TMP_ROOT/scan.json" \
  --lint "$TMP_ROOT/lint.json" \
  --inspect "$TMP_ROOT/inspect.json" \
  --route "$TMP_ROOT/route-browser-smoke.json" \
  --route "$TMP_ROOT/route-debug-red-green.json" \
  --output "$TMP_ROOT/dashboard.html"

PYTHONPATH=src python -m hermes_skilleval.cli diagnostic-ci-gate \
  --scan "$TMP_ROOT/scan.json" \
  --lint "$TMP_ROOT/lint.json" \
  --inspect "$TMP_ROOT/inspect.json" \
  --route "$TMP_ROOT/route-browser-smoke.json" \
  --route "$TMP_ROOT/route-debug-red-green.json" \
  --output "$TMP_ROOT/ci-gate-report.json" \
  --markdown-output "$TMP_ROOT/ci-gate-report.md" \
  --max-lint-findings 5 \
  --max-conflict-clusters 4 \
  --max-route-risk-flags 15 \
  --min-route-candidates 3

PYTHONPATH=src python -m hermes_skilleval.cli diagnostic-pr-review-surface \
  --gate-report "$TMP_ROOT/ci-gate-report.json" \
  --output "$TMP_ROOT/pr-review-packet.json" \
  --markdown-output "$TMP_ROOT/pr-review-packet.md"

PYTHONPATH=src python -m hermes_skilleval.cli diagnostic-artifact-drift-check \
  --expected "$ROOT" \
  --actual "$TMP_ROOT" \
  --output "$TMP_ROOT/drift-report.json" \
  --markdown-output "$TMP_ROOT/drift-report.md"
```

The demo source intentionally includes nearby browser skills, nearby debugging
and red-green testing skills, and a thin helper skill. The generated artifacts
show parser warnings, routing-clarity findings, review-worthy conflict clusters,
route evidence, route risk flags, and an explicit CI gate policy whose limits
match the committed demo artifact counts.

## 1. Index a Hermes-style Skill Library

```bash
skilleval index \
  --skills-path benchmarks/skills \
  --output runs/skills.json
```

## 2. Run a Router Evaluation

```bash
skilleval eval \
  --index runs/skills.json \
  --tasks benchmarks/tasks \
  --router hybrid \
  --top-k 5 \
  --output-dir runs/hybrid
```

## 3. Compare Multiple Routers

```bash
skilleval compare \
  --index runs/skills.json \
  --tasks benchmarks/tasks \
  --routers keyword,hybrid,embedding-hashing=embedding:hashing \
  --top-k 5 \
  --output-dir runs/comparison
```

## 4. Analyze Failures

```bash
skilleval analyze-failures \
  --runs runs/comparison \
  --baseline hybrid \
  --candidate embedding-hashing \
  --output runs/comparison/failure-analysis.md
```

## 5. Run the Cross-Encoder Reranker

```bash
skilleval eval \
  --index runs/skills.json \
  --tasks benchmarks/tasks \
  --router cross-encoder \
  --embedding-backend sentence-transformers \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --embedding-cache runs/embeddings/all-MiniLM-L6-v2.json \
  --cross-encoder-model cross-encoder/ms-marco-MiniLM-L-6-v2 \
  --gated-pool-size 10 \
  --top-k 5 \
  --output-dir runs/cross-encoder
```

## 6. Calibrate Cross-Encoder Acceptance

```bash
skilleval calibrate-cross-encoder \
  --results docs/demo/phase7a-cross-encoder/cross-encoder-minilm-rank-only/results.jsonl \
  --output runs/cross-encoder-calibration.json \
  --calibrated-output runs/cross-encoder-calibrated-test/results.jsonl \
  --fit-split dev \
  --apply-split test \
  --max-negative-hit-rate 0.05 \
  --max-selection-rate-at-5 0.3
```

## 7. Run Agent-in-the-loop Migration Evaluation

```bash
skilleval run-agent-loop \
  --routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --condition routed-skill \
  --output-dir runs/phase10-agent-loop/hybrid
```

The command writes dashboard-compatible `results.jsonl`,
`agent-traces.jsonl`, `agent-loop-summary.json`, and `report.md` artifacts.
Use `--condition no-skill` and `--condition oracle-skill` for the control runs.

## 8. Judge Agent-loop Evidence

```bash
skilleval judge-agent-loop \
  --traces docs/demo/phase10-agent-in-the-loop/agent-loop-hybrid/agent-traces.jsonl \
  --output-dir runs/phase11-evidence-judge/hybrid \
  --run-label judge-agent-loop-hybrid
```

The committed Phase 11 judge uses an offline `deterministic-rubric`; it does
not require API keys, network access, or live LLM judging.

## 9. Rank Offline Skill Metadata Patch Candidates

```bash
skilleval rank-skill-patches \
  --judge-results docs/demo/phase11-evidence-judge-calibration/judge-agent-loop-hybrid/judge-results.jsonl \
  --routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --output-dir docs/demo/phase12-skill-patch-ranking
```

Phase 12 joins Phase 11 routed-skill judge failures, Phase 9 routes, migration
task metadata, and the migrated skills index to rank offline deterministic
metadata patch candidates. It does not modify source `SKILL.md` files or write
a patched skills index.

## 10. Simulate Ranked Skill Patches

```bash
skilleval simulate-skill-patches \
  --ranked-patches docs/demo/phase12-skill-patch-ranking/ranked-patches.jsonl \
  --baseline-routes docs/demo/phase9-real-skill-library-migration/hybrid/results.jsonl \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --router hybrid \
  --top-k 5 \
  --max-patches 5 \
  --output-dir docs/demo/phase13-patch-simulation
```

Phase 13 applies ranked metadata candidates to copied `Skill` records only,
writes a shadow skill index, and compares shadow routing against the Phase 9
baseline. It is an offline deterministic regression guard, not fine-tuning or
learned training, and it does not modify source `SKILL.md` files or overwrite
the original `skills.json`.

## 11. Export Fine-Tuned Embedding Router Training Data

```bash
skilleval export-embedding-training-data \
  --tasks benchmarks/migration-tasks \
  --skills-index docs/demo/phase9-real-skill-library-migration/skills.json \
  --output-dir docs/demo/phase14-finetuned-embedding-router
```

Phase 14 exports supervised task-skill pairs and a remote-ready training config
for a domain-specific embedding router. It does not commit model checkpoints,
embedding caches, or downloaded models. Fine-tuned evaluation artifacts are
added only after a real model path is evaluated:

```bash
skilleval judge-finetuned-embedding \
  --baseline-results docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl \
  --candidate-results docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl \
  --output-dir docs/demo/phase14-finetuned-embedding-router \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router
```

## 12. Build Held-Out Fine-Tuned Provenance Pack

```bash
skilleval judge-finetuned-embedding \
  --baseline-results docs/demo/phase14-finetuned-embedding-router/baseline-results.jsonl \
  --candidate-results docs/demo/phase14-finetuned-embedding-router/finetuned-results.jsonl \
  --output-dir docs/demo/phase15-held-out-generalization \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --apply-split test \
  --write-filtered-results

skilleval write-finetuned-provenance \
  --training-summary docs/demo/phase14-finetuned-embedding-router/training-summary.json \
  --train-config docs/demo/phase14-finetuned-embedding-router/train-config.json \
  --train-run-summary docs/demo/phase15-held-out-generalization/train-run-summary.json \
  --model-manifest docs/demo/phase15-held-out-generalization/model-manifest.json \
  --regression-summary docs/demo/phase15-held-out-generalization/regression-summary.json \
  --output-dir docs/demo/phase15-held-out-generalization
```

Phase 15 filters the Phase 14 result files to the strict held-out `test` split
and adds a sanitized provenance pack. It records file hashes and training
summaries while keeping model checkpoints out of the repository.

## 13. Run Blind Validation and Release Gate

```bash
skilleval write-blind-validation \
  --baseline-results docs/demo/phase16-blind-validation/baseline-minilm/results.jsonl \
  --candidate-results docs/demo/phase16-blind-validation/finetuned-embedding/results.jsonl \
  --output-dir docs/demo/phase16-blind-validation \
  --model-dir /mnt/data/minghongsun/hermes-skilleval-phase14/models/minilm-skill-router \
  --task-root benchmarks/blind-migration-tasks

skilleval verify-release \
  --public-root README.md \
  --public-root docs/phase9.md \
  --public-root docs/phase10.md \
  --public-root docs/phase11.md \
  --public-root docs/phase12.md \
  --public-root docs/phase13.md \
  --public-root docs/phase14.md \
  --public-root docs/phase15.md \
  --public-root docs/phase16.md \
  --public-root docs/release-handoff.md \
  --public-root docs/demo/phase16-blind-validation \
  --public-root benchmarks/blind-migration-tasks \
  --required-path docs/demo/phase16-blind-validation/regression-summary.json \
  --required-path docs/release-handoff.md \
  --summary-output docs/demo/phase16-blind-validation/release-check-summary.json
```

Phase 16 adds a blind `test` task pack and a release verification gate. The
committed blind result is `REVIEW_REQUIRED`: the fine-tuned router preserves
Recall@5 but increases negative-skill selection on the blind pack, so it should
not replace the baseline without calibration or rollback logic.

## 14. Select the Default Release Router

```bash
skilleval select-release-router \
  --regression-summary docs/demo/phase16-blind-validation/regression-summary.json \
  --route-diffs docs/demo/phase16-blind-validation/route-diffs.jsonl \
  --output-dir docs/demo/phase17-calibrated-release-selector
```

Phase 17 turns the Phase 16 blind-validation evidence into an explicit release
decision:
[`docs/demo/phase17-calibrated-release-selector/release-decision.json`](demo/phase17-calibrated-release-selector/release-decision.json).
The current selector result is `KEEP_BASELINE`: the default router remains
`baseline-minilm`, and `finetuned-embedding` is not approved as the default.
See [`docs/phase17.md`](phase17.md) and
[`docs/release-handoff.md`](release-handoff.md).

## 15. Reproduce the Release Pack in CI Shape

```bash
skilleval release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
```

Phase 18 reruns the release selector and public release guard, then records a
deterministic manifest at
[`docs/demo/phase18-ci-release-reproducibility/release-manifest.json`](demo/phase18-ci-release-reproducibility/release-manifest.json).
The current reproducible release reading remains `KEEP_BASELINE`.

## 16. Static Dashboard

```bash
skilleval dashboard \
  --runs docs/demo/phase7b-cross-encoder-calibration \
  --output docs/demo/phase8-static-dashboard/dashboard.html
```

The generated file is self-contained and can be opened directly in a browser
for interactive run filtering, failure inspection, score ranking, and raw JSON
audit:
[`Live dashboard`](https://raidriar7170.github.io/hermes-skilleval/docs/demo/phase8-static-dashboard/dashboard.html).
The committed source artifact is also available at
[`docs/demo/phase8-static-dashboard/dashboard.html`](demo/phase8-static-dashboard/dashboard.html).

## 17. Run Tests

```bash
pytest -q
```

Expected:

```text
419 passed
```

## 18. Regenerate the External Skill Library Validation Pack

The committed external pack under
`docs/demo/external-skill-library-validation/` exercises two external-style
source tracks: Markdown `SKILL.md` folders and an MCP-style tool schema JSON.
It is local diagnostic evidence only: not a Marketplace Action, not GitHub API PR
comments, not PR annotations, not SaaS, not a runtime MCP router, not a SOTA claim,
not benchmark status, not production readiness, and not release approval.

Run the full regeneration commands from
[`docs/demo/external-skill-library-validation/README.md`](demo/external-skill-library-validation/README.md),
or use the same pattern in CI: write outputs outside the checkout and compare
them with the committed pack. The snippet below is the drift-check closeout,
not the complete regeneration script.

```bash
ROOT=docs/demo/external-skill-library-validation
TMP_ROOT="${TMPDIR:-/tmp}/external-skill-library-validation"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT/markdown-skills" "$TMP_ROOT/mcp-tool-schema"

# Regenerate both tracks with the commands in "$ROOT/README.md".

skilleval diagnostic-artifact-drift-check \
  --expected "$ROOT" \
  --actual "$TMP_ROOT" \
  --output "$TMP_ROOT/drift-report.json" \
  --markdown-output "$TMP_ROOT/drift-report.md"
```

The validate workflow performs this regeneration under
`$RUNNER_TEMP/external-skill-library-validation`, runs each track's diagnostic
CI gate, runs the drift check, uploads the regenerated artifacts, and passes
the outcome to the PR-facing CI summary as `external-pack`.

## 19. Simulate the PR-facing CI Summary Locally

```bash
TMP_ROOT="${TMPDIR:-/tmp}/diagnostic-onboarding"
EXTERNAL_TMP_ROOT="${TMPDIR:-/tmp}/external-skill-library-validation"

# First run the diagnostic regeneration and drift-check flow above so
# "$TMP_ROOT/diagnostic-artifact-drift.json" exists.
# Also run the external validation pack flow so
# "$EXTERNAL_TMP_ROOT/drift-report.json" exists.
{
  git diff --name-only HEAD || true
  git ls-files --others --exclude-standard
} | sort -u > /tmp/hermes-changed-files.txt

skilleval ci-summary \
  --check pytest=success \
  --check openspec-validate=success \
  --check release-check=success \
  --check diagnostic-gate=success \
  --check diagnostic-drift=success \
  --check external-pack=success \
  --changed-files /tmp/hermes-changed-files.txt \
  --release-check docs/demo/phase18-ci-release-reproducibility/release-check-summary.json \
  --diagnostic-gate docs/demo/diagnostic-onboarding/ci-gate-report.json \
  --diagnostic-drift "$TMP_ROOT/diagnostic-artifact-drift.json" \
  --overclaim-root README.md \
  --overclaim-root docs/usage.md \
  --output /tmp/hermes-ci-summary.json \
  --markdown-output /tmp/hermes-ci-summary.md
```

`skilleval ci-summary` is a local/GitHub Actions summary surface for already
run checks. It does not call the GitHub API, does not require tokens, and is
not a GitHub API comment bot, not a PR annotation system, not a Marketplace
Action, not SaaS, not a runtime MCP router, and not release approval.

## 20. Simulate the GitHub Actions Node 24 Preflight Locally

The Validate workflow uses a GitHub Actions Node 24 preflight by setting
`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` at workflow level. Local machines cannot
execute hosted JavaScript actions with GitHub's runner runtime, so the local
checklist is to preserve the same repository gates before pushing and then
inspect the remote Validate run. The setting follows GitHub's
[Node 20 deprecation changelog](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/).

```bash
python -m pytest -q
OPENSPEC_TELEMETRY=0 openspec validate --all --strict
skilleval release-check \
  --phase17-output-dir docs/demo/phase17-calibrated-release-selector \
  --release-output-dir docs/demo/phase18-ci-release-reproducibility
# Regenerate diagnostic and external validation packs as shown above.
# Then run skilleval ci-summary with explicit success/failure check outcomes.
```

Boundary: this is not a Marketplace Action, not GitHub API PR comments, not PR
annotations, not SaaS, not a runtime MCP router, not a SOTA claim, not
benchmark status, not production readiness, not release approval, not automatic
merge approval, and not a permanent compatibility guarantee.

## 21. Run the Reusable GitHub Action Gate Locally

The root `action.yml` is a published reusable repository Action for external
skill-library maintainers. It runs `skilleval github-action-gate` against a
labeled benchmark and writes deterministic gate artifacts:

```bash
python -m pip install -e ".[dev]"
skilleval github-action-gate \
  --skill-path examples/github-action/skills \
  --benchmark-path examples/github-action/benchmark \
  --min-recall-at-k 1.0 \
  --max-negative-hit-rate 0.0 \
  --output-dir runtime/github-action-gate
```

The example workflow under
[`examples/github-action/.github/workflows/skilleval.yml`](../examples/github-action/.github/workflows/skilleval.yml)
uses `Raidriar7170/hermes-skilleval@v0.2.1`. Use a pinned commit SHA only when
you intentionally want to test an exact commit instead of the published tag.

The historical local external-consumer smoke pack under
[`docs/demo/external-repo-action-smoke-pack`](demo/external-repo-action-smoke-pack)
records the same gate shape from consumer-relative `skills/`, `benchmark/`, and
`skilleval-output` paths. Its committed output shows `ALLOW_MERGE` with
`recall_at_5=1.0` and `negative_hit_rate=0.0`; captured refs in that pack are
historical smoke evidence, not the current recommended released Action ref.

The historical hosted consumer smoke pack under
[`docs/demo/hosted-consumer-action-smoke`](demo/hosted-consumer-action-smoke)
records one GitHub-hosted consumer smoke run from
`Raidriar7170/hermes-skilleval-action-consumer-smoke`. The committed run
metadata links the hosted workflow run and the downloaded artifacts show
`ALLOW_MERGE`, `recall_at_5=1.0`, and `negative_hit_rate=0.0`; captured
historical action refs in that pack are not current onboarding recommendations.

Boundary: This is a reusable repository Action, not a Marketplace-published Action, not a GitHub API PR comment bot, not a SaaS dashboard, and not a runtime MCP router. It is not GitHub API PR comments, not PR annotations, not a public ranking table, not a SOTA claim, not benchmark status, not production readiness, not release approval, and not automatic merge approval.

## 22. Review the v0.2.0 Release Decision Package

The v0.2.0 release decision package summarizes Phase 16 blind validation,
Phase 17 default-router selection, Phase 18 reproducibility, the local
external-consumer action smoke, and the hosted consumer action smoke:

- [`release-decision.md`](demo/v0.2.0-release-decision/release-decision.md)
- [`release-decision.json`](demo/v0.2.0-release-decision/release-decision.json)
- [`input-manifest.json`](demo/v0.2.0-release-decision/input-manifest.json)

This is historical pre-publish review evidence. The package decision is
`NEEDS_REVIEW`; `Published: false`; the router decision is `KEEP_BASELINE`; the
default router remains `baseline-minilm`; and `finetuned-embedding` is not
approved as default. The current publication record is the post-release
evidence linked above.

Boundary: this historical decision package is not a Marketplace Action release,
not GitHub API PR comments, not PR annotations, not SaaS, not a runtime MCP
router, not a SOTA claim, not benchmark status, not production readiness, not
release approval, not automatic merge approval, and not automatic publication.
Any further patch tag, GitHub Release, Marketplace publication, or public
release action after v0.2.1 still requires explicit human confirmation.

## 23. Review the v0.2.0 Release Notes And Final Approval Checklist

The v0.2.0 release notes remain the release notes for that published version.
The current patch release notes are in
[`release-notes/v0.2.1.md`](release-notes/v0.2.1.md). The final approval
checklist is historical pre-publish review evidence:

- [`release-notes/v0.2.0.md`](release-notes/v0.2.0.md)
- [`final-approval.md`](demo/v0.2.0-final-approval/final-approval.md)
- [`final-approval.json`](demo/v0.2.0-final-approval/final-approval.json)
- [`input-manifest.json`](demo/v0.2.0-final-approval/input-manifest.json)

The release notes summarize the published GitHub Release package, implemented
capabilities, and committed evidence. The final approval package records the
pre-publish Overall decision: `NEEDS_REVIEW` and Published: `false`; it lists
GO Conditions, NO-GO Until, and Requires Human Confirmation so a reviewer can
audit the original publish gate.

Boundary: the checklist is pre-publish review evidence, not automatic
publication, not a Marketplace Action release, not GitHub API PR comments, not
PR annotations, not SaaS, not a runtime MCP router, not a SOTA claim, not
benchmark status, not production readiness, not release approval, not automatic
merge approval, and not Marketplace publication.
