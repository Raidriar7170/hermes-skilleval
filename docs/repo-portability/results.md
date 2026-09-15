# Two-repository confirmation results

**Study: COMPLETED_EXPLORATORY. Utility: INCONCLUSIVE.** The small frozen sample does not establish incremental repair utility from S. One attempt per arm and repair family; no equivalence, causal, production, or upstream-adoption claim.

All 18 planned attempts started using wheel/source `31ebf2456381df2cff80725f9b9bc187d41021d2`; all starts and patches are retained in the [execution ledger](../../artifacts/repo-portability/execution-ledger.json). Three csvkit #1345 development attempts are separate. Six confirmation families qualified before any confirmation result; none were excluded after observing outcomes. Preparation failures were repaired before qualification, not discarded Agent attempts.

## Primary outcome by repository

Pass requires both the specified target and related regression slice. Unknown remains in the scheduled denominator.

| Repository | Arm | Started | Pass | Fail | Unknown | Policy rejected | Timeout |
|---|---|---:|---:|---:|---:|---:|---:|
| simonw/sqlite-utils | F | 3 | 2 | 1 | 0 | 0 | 0 |
| simonw/sqlite-utils | N | 3 | 2 | 1 | 0 | 0 | 0 |
| simonw/sqlite-utils | S | 3 | 2 | 1 | 0 | 0 | 0 |
| wireservice/csvkit | F | 3 | 2 | 0 | 1 | 1 | 0 |
| wireservice/csvkit | N | 3 | 2 | 0 | 1 | 1 | 0 |
| wireservice/csvkit | S | 3 | 3 | 0 | 0 | 0 | 0 |

## Repair-family results

| Family | N | F | S |
|---|---|---|---|
| csvkit-1219 | [PASS](../../artifacts/repo-portability/records/confirm-csvkit-1219-N-001/record.json) | [PASS](../../artifacts/repo-portability/records/confirm-csvkit-1219-F-001/record.json) | [PASS](../../artifacts/repo-portability/records/confirm-csvkit-1219-S-001/record.json) |
| csvkit-1247 | [UNKNOWN (policy)](../../artifacts/repo-portability/records/confirm-csvkit-1247-N-001/record.json) | [UNKNOWN (policy)](../../artifacts/repo-portability/records/confirm-csvkit-1247-F-001/record.json) | [PASS](../../artifacts/repo-portability/records/confirm-csvkit-1247-S-001/record.json) |
| csvkit-1270 | [PASS](../../artifacts/repo-portability/records/confirm-csvkit-1270-N-001/record.json) | [PASS](../../artifacts/repo-portability/records/confirm-csvkit-1270-F-001/record.json) | [PASS](../../artifacts/repo-portability/records/confirm-csvkit-1270-S-001/record.json) |
| sqlite-utils-131 | [PASS](../../artifacts/repo-portability/records/confirm-sqlite-utils-131-N-001/record.json) | [PASS](../../artifacts/repo-portability/records/confirm-sqlite-utils-131-F-001/record.json) | [PASS](../../artifacts/repo-portability/records/confirm-sqlite-utils-131-S-001/record.json) |
| sqlite-utils-781-783 | [FAIL](../../artifacts/repo-portability/records/confirm-sqlite-utils-781-783-N-001/record.json) | [FAIL](../../artifacts/repo-portability/records/confirm-sqlite-utils-781-783-F-001/record.json) | [FAIL](../../artifacts/repo-portability/records/confirm-sqlite-utils-781-783-S-001/record.json) |
| sqlite-utils-828 | [PASS](../../artifacts/repo-portability/records/confirm-sqlite-utils-828-N-001/record.json) | [PASS](../../artifacts/repo-portability/records/confirm-sqlite-utils-828-F-001/record.json) | [PASS](../../artifacts/repo-portability/records/confirm-sqlite-utils-828-S-001/record.json) |

csvkit #1247 N/F added ordinary `examples/` fixtures, which the frozen profile rejected before functional verification. The write-root restriction was not disclosed to the Agent. Original mechanical rejections remain unchanged; functional outcomes are **unknown**, not demonstrated model failures. The uniform, separately committed [post-hoc fixture audit](../../artifacts/repo-portability/fixture-audit/index.json) rebuilt the entire unchanged N/F patches and both passed 5 target + 2 regression cases. These post-hoc passes do not replace primary rows or validate the original policy.

rowid #781/#783 is one family. N and F each fail three rowid-alias replace cases and the ignored-insert hash-ID case; S fails the hash-ID case. The valid trusted failures concern returned row identity, not a failed environment. See each saved patch and JUnit. The [scope table](evidence-boundary.md) states narrower acceptance for #1219, #131 and hinted #828.

## Paired descriptive comparison

Win/loss is by complete functional outcome of a family, not number of individual tests. Pairs with an unknown arm are kept in an unknown column.

| Repository | First vs second | Wins | Losses | Ties | Unknown pairs |
|---|---|---:|---:|---:|---:|
| simonw/sqlite-utils | S vs F | 0 | 0 | 3 | 0 |
| simonw/sqlite-utils | S vs N | 0 | 0 | 3 | 0 |
| simonw/sqlite-utils | F vs N | 0 | 0 | 3 | 0 |
| wireservice/csvkit | S vs F | 0 | 0 | 2 | 1 |
| wireservice/csvkit | S vs N | 0 | 0 | 2 | 1 |
| wireservice/csvkit | F vs N | 0 | 0 | 2 | 1 |

With only three families per repository and one trial per cell, descriptive ties cannot establish noninferiority/equivalence. Bootstrap intervals from an all-tied tiny sample would be degenerate and are not evidence of certainty. The fixture-policy confound prevents treating S’s higher mechanical acceptance on #1247 as a repair-quality gain. No extra runs or harder-task search followed these outcomes.

## Real usage and timing

Totals below are sums over three confirmation attempts per repository/arm. Input includes cached input; output includes reasoning output. Uncached is input minus cached. Dollar cost is null. Summed worker time is not batch user waiting time.

| Repository | Arm | Input | Cached subset | Uncached | Output | Reasoning subset | Execution seconds | Pipeline seconds | S recommendation seconds |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| simonw/sqlite-utils | F | 4,144,254 (3/3) | 3,937,792 (3/3) | 206,462 (3/3) | 33,923 (3/3) | 13,051 (3/3) | 1,016.03 (3/3) | 1,031.09 (3/3) | null (0/3) |
| simonw/sqlite-utils | N | 4,448,984 (3/3) | 4,219,648 (3/3) | 229,336 (3/3) | 34,918 (3/3) | 13,074 (3/3) | 1,073.82 (3/3) | 1,088.87 (3/3) | null (0/3) |
| simonw/sqlite-utils | S | 2,939,831 (3/3) | 2,670,592 (3/3) | 269,239 (3/3) | 34,930 (3/3) | 13,728 (3/3) | 1,060.18 (3/3) | 1,095.46 (3/3) | 17.33 (3/3) |
| wireservice/csvkit | F | 1,923,502 (3/3) | 1,775,744 (3/3) | 147,758 (3/3) | 22,540 (3/3) | 8,374 (3/3) | 628.43 (3/3) | 637.85 (3/3) | null (0/3) |
| wireservice/csvkit | N | 2,577,723 (3/3) | 2,385,280 (3/3) | 192,443 (3/3) | 27,079 (3/3) | 10,436 (3/3) | 768.57 (3/3) | 777.80 (3/3) | null (0/3) |
| wireservice/csvkit | S | 1,932,471 (3/3) | 1,788,416 (3/3) | 144,055 (3/3) | 23,157 (3/3) | 9,665 (3/3) | 595.12 (3/3) | 629.87 (3/3) | 18.27 (3/3) |

Parentheses give known/total attempts, not success counts. All costs are retained for policy-rejected or failed attempts. Null does not mean zero. N/F do not execute embedding/reranking; this was also checked in clean wheel environments without Torch/Transformers. S runs real online retrieval on MPS. It has local model work in addition to the listed Agent tokens; the observed single-trial token differences do not prove net savings.

Per-run records retain package preparation, capture and finalize timings; missing development measurements remain null. Pipeline wall time includes recommendation, workspace setup, execution, capture and validation; it is measured directly, not reconstructed by double-counting components. Separate cold installation, model-fetch time and total batch user waiting time were not measured and remain unknown. The dev cold index took 1.475 s; confirmation reused that identity-checked index. Route files expose constructor/index/retrieval/rerank and full recommendation wall time. Concurrency and other controller checks limit latency comparisons. Monetary cost and an all-resource cost comparison are unavailable.

Across the six confirmation families, S spent 35.61 s in online recommendation. Its observed uncached input was 413,294 tokens versus F’s 354,220, and output was 58,087 versus F’s 56,463. Lower total input in some S rows therefore does not establish lower paid usage or net cost; cached proportions differ and dollar accounting is unavailable. These are descriptive single-trial totals.

## Selection, exposure and observed reads

F always exposes `cli-api-regression` + `systematic-debugging`, selected only by repository configuration. N exposes the five-package registry. S selects by the real encoder/reranker scores below; final presentation uses the same registry order as F.

| Family | S ranked Top-2 (score) | Same set as F? | Successful read-command observations N / F / S |
|---|---|---|---|
| csvkit-1219 | [schema-change-regression (-5.158), cli-api-regression (-5.235)](../../artifacts/repo-portability/records/confirm-csvkit-1219-S-001/route.json) | False | 1 / 1 / 1 |
| csvkit-1247 | [schema-change-regression (-5.038), cli-api-regression (-5.113)](../../artifacts/repo-portability/records/confirm-csvkit-1247-S-001/route.json) | False | 1 / 1 / 1 |
| csvkit-1270 | [schema-change-regression (-5.227), cli-api-regression (-5.399)](../../artifacts/repo-portability/records/confirm-csvkit-1270-S-001/route.json) | False | 4 / 1 / 1 |
| sqlite-utils-131 | [cli-api-regression (-4.577), schema-change-regression (-4.703)](../../artifacts/repo-portability/records/confirm-sqlite-utils-131-S-001/route.json) | False | 1 / 3 / 1 |
| sqlite-utils-781-783 | [schema-change-regression (-3.600), cli-api-regression (-4.460)](../../artifacts/repo-portability/records/confirm-sqlite-utils-781-783-S-001/route.json) | False | 1 / 1 / 1 |
| sqlite-utils-828 | [schema-change-regression (-5.561), verification-before-completion (-5.604)](../../artifacts/repo-portability/records/confirm-sqlite-utils-828-S-001/route.json) | False | 3 / 1 / 0 |

Counts refer only to completed successful `cat`/`sed`/`head`/`tail` command observations mentioning an explicit skill file. Listing paths or failed reads are separate references, not successful reads. Zero means no observation by this extractor, not proof that no skill information was used. Sanitized event ordinals and paths are available per run; private full traces are not published. Exposure/read observations do not prove comprehension or causal contribution to the patch.

## Recompute and inspect

The [public index](../../artifacts/repo-portability/records/index.json) binds each patch, JUnit, route and event derivative; [summary.json](../../artifacts/repo-portability/records/summary.json) contains full rows and cost coverage. From an installed wheel:

```sh
hermes-maintain records --index artifacts/repo-portability/records/index.json --output /tmp/hermes-two-repo-records
```

Use a fresh output directory. This recomputes existing evidence without model, network or Docker calls; it does not rerun trusted tests. Full replay requires the assets/login/Docker environment in [usage](usage.md). Later delivery source discloses write roots and strengthens export/reporting; it is not claimed to have generated the frozen Agent runs.
