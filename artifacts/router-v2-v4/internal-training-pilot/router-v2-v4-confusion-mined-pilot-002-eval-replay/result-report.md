# Router V2 pilot-002 evaluation replay

Pilot `router-v2-v4-confusion-mined-pilot-002-eval-replay` reused the exact
frozen pilot-001 training artifacts and completed its one authorized evaluation
attempt. All preregistered Arm C versus Arm A gates passed, so the pilot
evaluation conclusion is `ROUTER_V2_PILOT_IMPROVED`.

The router promotion decision remains `KEEP_BASELINE`: this is a
`MODEL_ONLY_PILOT` with `human_reviewer_count=0`; it is non-SOTA,
non-production, not release eligible, and blind-v2 was not run.

## Raw-count headline

- Arm A -> C Recall@1: `12/16 -> 16/16` for every seed.
- Arm A -> C Recall@5: `16/16 -> 16/16` for every seed.
- Arm A -> C Negative Hit Rate@1: `1/9 -> 0/9` for every seed.
- Arm A -> C Negative Hit Rate@5 by seed: `8/9 -> 6/9`,
  `8/9 -> 7/9`, and `8/9 -> 5/9`; across the three paired runs this is
  `24/27 -> 18/27`.

## Per-arm and per-seed metrics

| Arm | Seed | Recall@1 | Recall@5 | MRR | NDCG@5 | NHR@1 | NHR@5 | First-negative rank | p50 ms | p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 7170 | 12/16 | 16/16 | 0.859375 | 0.895217 | 1/9 | 8/9 | 2.888889 | 5.457458 | 6.193209 |
| A | 7171 | 12/16 | 16/16 | 0.859375 | 0.895217 | 1/9 | 8/9 | 2.888889 | 5.572833 | 6.079083 |
| A | 7172 | 12/16 | 16/16 | 0.859375 | 0.895217 | 1/9 | 8/9 | 2.888889 | 4.463750 | 6.116042 |
| B | 7170 | 16/16 | 16/16 | 1.000000 | 1.000000 | 0/9 | 8/9 | 4.000000 | 4.639750 | 5.605250 |
| B | 7171 | 16/16 | 16/16 | 1.000000 | 1.000000 | 0/9 | 7/9 | 3.666667 | 4.531916 | 5.622500 |
| B | 7172 | 16/16 | 16/16 | 1.000000 | 1.000000 | 0/9 | 8/9 | 3.777778 | 4.605583 | 5.848208 |
| C | 7170 | 16/16 | 16/16 | 1.000000 | 1.000000 | 0/9 | 6/9 | 5.111111 | 4.484792 | 5.794833 |
| C | 7171 | 16/16 | 16/16 | 1.000000 | 1.000000 | 0/9 | 7/9 | 4.444444 | 4.486209 | 5.063375 |
| C | 7172 | 16/16 | 16/16 | 1.000000 | 1.000000 | 0/9 | 5/9 | 4.666667 | 4.425000 | 6.628875 |

## Mean and sample standard deviation

| Arm | Recall@1 | Recall@5 | MRR | NDCG@5 | NHR@1 | NHR@5 | First-negative rank | p50 ms | p95 ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0.750000 +/- 0 | 1.000000 +/- 0 | 0.859375 +/- 0 | 0.895217 +/- 0 | 0.111111 +/- 0 | 0.888889 +/- 0 | 2.888889 +/- 0 | 5.164680 +/- 0.609758 | 6.129445 +/- 0.058232 |
| B | 1.000000 +/- 0 | 1.000000 +/- 0 | 1.000000 +/- 0 | 1.000000 +/- 0 | 0.000000 +/- 0 | 0.851852 +/- 0.064150 | 3.814815 +/- 0.169725 | 4.592416 +/- 0.055110 | 5.691986 +/- 0.135567 |
| C | 1.000000 +/- 0 | 1.000000 +/- 0 | 1.000000 +/- 0 | 1.000000 +/- 0 | 0.000000 +/- 0 | 0.666667 +/- 0.111111 | 4.740741 +/- 0.339450 | 4.465334 +/- 0.034937 | 5.829028 +/- 0.783310 |

## Unchanged gate

| Gate value, Arm C minus/over Arm A | Seed 7170 | Seed 7171 | Seed 7172 | Mean | Threshold | Result |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Recall@5 delta | 0.000000 | 0.000000 | 0.000000 | 0.000000 | each/mean >= 0.00 | PASS |
| MRR delta | 0.140625 | 0.140625 | 0.140625 | 0.140625 | each/mean >= -0.01 | PASS |
| NDCG@5 delta | 0.104783 | 0.104783 | 0.104783 | 0.104783 | each/mean >= -0.01 | PASS |
| NHR@5 delta | -0.222222 | -0.111111 | -0.333333 | -0.222222 | each <= 0; mean <= -0.05 | PASS |
| p95 latency ratio | 0.935675 | 0.832918 | 1.083850 | 0.950814 | each/mean <= 1.20 | PASS |

No threshold changed, no best seed was selected, and no rerun occurred.

## Paired wins/losses

Each cell is `wins/losses/ties` for Arm C versus paired Arm A.

| Seed | Recall@1 | Recall@5 | MRR | NDCG@5 | NHR@1 | NHR@5 | First-negative rank | Latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7170 | 4/0/12 | 0/0/16 | 4/0/12 | 4/0/12 | 1/0/8 | 2/0/7 | 6/0/3 | 12/4/0 |
| 7171 | 4/0/12 | 0/0/16 | 4/0/12 | 4/0/12 | 1/0/8 | 2/1/6 | 6/1/2 | 14/2/0 |
| 7172 | 4/0/12 | 0/0/16 | 4/0/12 | 4/0/12 | 1/0/8 | 4/1/4 | 6/1/2 | 10/6/0 |

## Failure slices

Arm C had seven flagged tasks in each seed. There were no `TOP1_MISS`,
`GOLD_MISS_AT_5`, `NEGATIVE_HIT_AT_1`, or `GOLD_RANK_REGRESSION` flags.
`NEGATIVE_HIT_AT_5` covered 6, 7, and 5 tasks; `NEGATIVE_MOVED_EARLIER`
covered 0, 1, and 1; task-level latency ratio above 1.20 covered 1, 0, and 2.
The canonical category, skill, flag, and task-ID slices are retained in
`evaluation/attempt-1/artifacts/failure-slices.json`.

## Lineage and evidence

- Evaluation code commit: `756a6c5b165b4ab6251266d46befc934ef1544f4`
- Attempt token SHA-256:
  `8ad3bd8011b64ab15dea4025550754119d0f41853535ef7f98ee2b2cba93a489`
- Canonical pilot manifest file SHA-256:
  `5888842a9a60a7c94dff56ba505e070b4af418535dd828ab62809e4bbb04b2d7`
- Evaluation summary semantic SHA-256:
  `433d0a92b6548eef8634b43c0856129db3513777444249fd7e03cf901cfdcd13`
- Evaluation plan semantic SHA-256:
  `ed8aaa5f3bf29ec30efe863059f077c00ff100cdd9169bdb0b8b7ff980fa2523`
- Pilot-001 metrics observed: `false`
- Replacement reason: `INFRASTRUCTURE_FAILURE_BEFORE_INFERENCE`

The committed JSON files are canonical copies from the isolated local `0700`
evaluation namespace. Prompt-level `route-results.jsonl` remains local and is
not part of this small public evidence pack.
