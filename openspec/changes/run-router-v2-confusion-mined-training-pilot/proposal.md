## Why

The completed Router V2 model-only audit identified a bounded pool of supported hard negatives but intentionally had no admission effect. A separate internal-only pilot is needed to test whether baseline-confusion mining improves the router under preregistered, leakage-resistant evaluation without weakening the human-only path or making production, release, blind-v2, or promotion claims.

## What Changes

- Add a deterministic CPU-only baseline-confusion mining contract over exactly 64 frozen train positives and the frozen 16-skill snapshot, pinned to `sentence-transformers/all-MiniLM-L6-v2` revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
- Filter only the 35 previously adjudicated supported train hard negatives through a preregistered rank-or-margin condition, permanently exclude the 29 disputed rows, and permit supplementation only from newly mined baseline-confusion candidates.
- Add one combined two-pass `MODEL_ONLY_PILOT` review and model adjudication flow for new train candidates and a separately partitioned `HELD_OUT_EVAL_ONLY` non-blind-test label artifact; no third review round is allowed.
- Add a fail-closed internal training package containing exactly 64 train positives and 48-64 supported hard negatives, deterministic skill-unique sampling, sealed handoff/fingerprint binding, full lineage, and a framework/GPU/output-free `--preflight-only` path.
- Preregister only Arm A base, Arm B positive-only, and Arm C positive-plus-confusion across seeds `7170`, `7171`, and `7172`, with frozen hyperparameters and Arm C versus Arm A as the only decision gate.
- Add a one-time post-training non-blind-test evaluation contract with complete per-seed, paired, aggregate, and failure-slice reporting. Calibration is integrity-only; blind-v2 remains unrun.
- Keep the previous model-only audit at `admission_effect=NONE` and `can_start_training=false`, leave `make-router-v2-training-ready` unchanged, and prohibit production release, router promotion, release claims, blind-v2 conclusions, human-label advertising, or résumé human-review claims.
- Do not implement code, generate artifacts, access models, run training, or perform evaluation in this proposal phase.

## Capabilities

### New Capabilities

- `router-v2-confusion-mined-training-pilot`: Defines the frozen mining, model review, held-out label, internal package, preflight, three-arm training, one-time evaluation, decision, lineage, and claim-boundary contract.

### Modified Capabilities

None. Existing human-only and model-only audit capabilities remain unchanged.

## Impact

- Future implementation may add deterministic mining/review/package/preflight/training/evaluation code and internal pilot artifacts under a new isolated namespace.
- The pilot reuses the established prompt-only query formatter, `MultipleNegativesRankingLoss+ContrastiveLoss` objective family, and immutable model lineage conventions without modifying protected Phase 14-18 or blind-v2 evidence.
- No dashboard, qualification package, Human Brief, parallel Superpowers plan, production artifact, release state, or router promotion is added.
