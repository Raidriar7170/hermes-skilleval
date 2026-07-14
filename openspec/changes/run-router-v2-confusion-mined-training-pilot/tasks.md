## 1. Deterministic mining and review contracts

- [x] 1.1 Add focused RED tests for train-only source access, exact MiniLM revision, full 16-score output, eight-decimal ordering, rank/margin eligibility, hashes, and forbidden split rejection.
- [x] 1.2 Implement the minimal miner and validator; generate the first CPU-only mining artifact for all 64 train positives and verify its model/source hashes.
- [x] 1.3 Add focused RED tests and minimal canonical schemas for variable-size new-candidate pass 1, pass 2, adjudication, bounded rationale, and exact truth fields.
- [x] 1.4 Filter the 35 PR #37 supported negatives through the frozen rank/margin rule; permanently exclude the 29 disputed rows and report the retained count.

## 2. New train and held-out candidate adjudication

- [x] 2.1 Generate the first unseen top-confuser train candidate for each prompt not already represented by an eligible supported row.
- [x] 2.2 Generate deterministic taxonomy/lexical non-blind-test candidate labels without loading baseline scores and mark them `HELD_OUT_EVAL_ONLY`.
- [x] 2.3 Execute isolated `MODEL_PASS_1` and `MODEL_PASS_2` over the combined new-candidate set, then execute one bound model adjudication.
- [x] 2.4 Select baseline-hard supported train negatives deterministically; if fewer than 48 survive, add only the next unseen baseline confusers and repeat the same two-pass/adjudication contract for those new rows.
- [x] 2.5 Freeze 48-64 admitted train hard negatives and supported held-out-only labels with hashes and per-skill distribution, or stop fail-closed if the training threshold is not met.

## 3. Internal package and minimal training implementation

- [x] 3.1 Add focused RED tests and minimal package builder/validator for exactly 64 positives, 48-64 admitted hard negatives, exact exclusions, lineage, and model-only truth.
- [x] 3.2 Add `skill_id` to validated examples, sealed examples, example fingerprints, sealed handoff, and handoff fingerprint without weakening the existing human-only loader.
- [x] 3.3 Add focused RED tests and implement deterministic `skill-unique-v1` sampling with full positive coverage, no same-skill MNRL batch collision, and canonical plan hash.
- [x] 3.4 Bind config, run summary, and model manifest to data/mining/accepted/Git/base-model/seed/sampler/dependency lineage.
- [x] 3.5 Add focused RED tests and implement `--preflight-only` without Torch/sentence-transformers import, CUDA access, or output side effects.
- [x] 3.6 Build and validate the internal-only package and preregistered A/B/C run configs for seeds 7170, 7171, and 7172.

## 4. Frozen training and one-time evaluation

- [x] 4.1 Run the raw side-effect audit and canonical `--preflight-only`; save the exact result before any training.
- [x] 4.2 Attempt the authorized A100 path, record the SSH timeout without remote writes, then use the sufficient local CPU fallback with the exact model revision and dependencies.
- [x] 4.3 Run only Arm A, Arm B, and Arm C for seeds 7170-7172 with frozen hyperparameters and complete run/model manifests.
- [x] 4.4 Add focused metric/gate tests and consume the single non-blind-test attempt. The attempt failed before inference on the immutable-model copy guard, so all requested evaluation metrics are explicitly `UNAVAILABLE` and no retry is permitted.
- [x] 4.5 Apply the serialized fail-closed rule without post-hoc changes and emit `KEEP_BASELINE`.

## 5. Verification and bounded closeout

- [x] 5.1 Update README and resume recommendations with the fail-closed result and explicit model-only, zero-human, non-SOTA, non-production, no-blind-v2 limitations.
- [x] 5.2 Run focused/relevant tests, Ruff, mypy, strict OpenSpec validation, artifact hash validation, preflight side-effect audit, and `git diff --check`.
- [x] 5.3 Obtain a final read-only Reviewer pass, resolve all Must Fix findings, and record final branch HEAD and artifact hashes.
- [x] 5.4 Push the bounded branch to GitHub without archive, release, deploy, router promotion, or blind-v2 execution.
