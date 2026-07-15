## Context

Pilot-001 trained Arm B and C for seeds `7170`, `7171`, and `7172`, then
consumed its only evaluation attempt on an Arm A snapshot-copy guard before any
model inference. No held-out metric was observed. Commit `6fb9bb9` added safe
Hugging Face snapshot materialization, and a separate non-heldout real-load
smoke subsequently verified the exact Arm A snapshot plus all six frozen B/C
snapshots using only fixed synthetic text.

Pilot-002 is therefore an evaluation replay, not a training or data phase. Its
authority must point at pilot-001's immutable training execution root while its
attempt ledger and evaluation outputs use a new namespace.

## Goals / Non-Goals

**Goals:**

- Bind one new pilot ID to the exact pilot-001 data, mining, run-pack,
  checkpoint, model-manifest, base-model, seed, query-order, metric, and gate
  evidence.
- Fail before attempt consumption if any frozen checkpoint, manifest, file
  hash, or reuse field differs.
- Run exactly one evaluation attempt and retain complete raw, per-seed,
  aggregate, paired, failure-slice, latency, and decision evidence.
- Publish resume-safe raw counts and limitations without changing the
  preregistered gate.

**Non-Goals:**

- Training, retraining, run-pack rebuild, data changes, mining, another model or
  human review, hyperparameter changes, best-seed selection, or reruns.
- Blind-v2, pilot-003, production readiness, release, router promotion, deploy,
  merge, or archive.

## Decisions

### A manifest created before the attempt binds the replacement

The runner creates one canonical pilot-002 manifest in the new `0700` output
root before it starts the attempt. The manifest records
`replacement_reason=INFRASTRUCTURE_FAILURE_BEFORE_INFERENCE`,
`reuses_frozen_training_artifacts_from_pilot_001=true`,
`pilot_001_metrics_observed=false`, all required model-only truth fields, the
exact frozen hashes and paths, the clean evaluation code commit, the new output
namespace, the deterministic query-order contract, the full metric list, and
the unchanged gate thresholds. A pre-existing mismatched manifest fails closed;
the completed manifest is later copied byte-for-byte into repository evidence.

Alternative considered: commit a manifest containing the evaluation commit.
That creates a self-referential Git hash. Binding the clean commit atomically at
runtime avoids that cycle while still freezing it before the attempt marker.

### Training inputs and evaluation outputs use separate roots

The authority has an immutable pilot-001 training execution root and a distinct
pilot-002 evaluation execution ID. Run-pack configs and all B/C run summaries,
model manifests, and model files are read only from the former; the evaluation
ledger and artifacts are written only to the latter. Arm A resolves to the same
MiniLM revision and frozen file manifest used by pilot-001.

Alternative considered: copy or rebuild the run pack under pilot-002. This is
rejected because rebuilding would change Git lineage and copying would add an
unnecessary second authority surface.

### All artifact checks precede attempt consumption

The clean Git commit, pilot manifest, run-pack file/internal hashes, training
configs, run summaries, model manifests, checkpoint topology, model-file sizes,
and SHA-256 values are verified before `attempt-1.started.json` is written. A
missing or drifting checkpoint stops without training and without consuming
pilot-002. After the marker is written, any failure is terminal and no retry is
allowed.

### The existing evaluation order, metrics, and gates remain authoritative

The runner preserves arm order A/B/C, seed order 7170/7171/7172, ascending
frozen task order, one warm-up plus measured query encoding, current metric
definitions, arithmetic mean/sample standard deviation, and Arm C versus paired
Arm A comparison. Thresholds remain exactly: Recall@5 delta `>=0.00`; MRR and
NDCG@5 delta `>=-0.01`; NHR@5 mean delta `<=-0.05` and each seed `<=0.00`; p95
latency ratio `<=1.20`, each where preregistered. Any failed gate yields
`KEEP_BASELINE`; only all-pass yields `ROUTER_V2_PILOT_IMPROVED`.

## Risks / Trade-offs

- [The 16-positive and 9-negative sample is small] → Report raw counts beside
  rates and retain `non-SOTA / non-production / blind-v2 not run` wording.
- [CPU latency is noisy] → Preserve the existing identical-device, identical
  order, warm-up, and raw timing contract; do not rerun.
- [A failure after the marker consumes pilot-002] → Put every possible frozen
  artifact and model-load preflight before the marker and accept that runtime
  inference failures are terminal.
- [Model-only labels are correlated] → Keep `MODEL_ONLY_PILOT`,
  `human_reviewer_count=0`, and `router_decision=KEEP_BASELINE` until all gates
  finish.

## Migration Plan

1. Add replay authority/tests and validate the exact reuse manifest without
   creating an attempt.
2. Commit the clean evaluation code and create the new `0700` output root.
3. Run the one authorized attempt; never invoke the training or run-pack build
   scripts.
4. Copy small canonical evidence into the repository, update docs and Human
   Brief, verify, and open a PR.

Rollback before step 3 removes only the new change and unused output namespace.
After step 3 the attempt is immutable; rollback keeps `KEEP_BASELINE` and does
not create a replacement.

## Open Questions

None. The user fixed every permitted field and terminal action.
