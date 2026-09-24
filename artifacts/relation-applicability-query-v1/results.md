# 关系适用性与获取成本研究

MODEL_ASSISTED_SOURCE_AUDIT_NOT_HUMAN_GOLD；human_reviewer_count=0。同模型独立上下文仍可能共享语义错误。功能修复收益 NOT_TESTED_THIS_STAGE。

## 配对排序

| 状态 | 方法 | k | 支持正关系 | 支持零 | 争议 | 未知/未抽样 |
| --- | --- | --- | --- | --- | --- | --- |
| empty-keyed-group-naming | S | 8 | 0 | 8 | 0 | 0 |
| empty-keyed-group-naming | S | 16 | 2 | 12 | 0 | 2 |
| empty-keyed-group-naming | S | 24 | 2 | 20 | 0 | 2 |
| empty-keyed-group-naming | S | 32 | 2 | 26 | 2 | 2 |
| empty-keyed-group-naming | A0 | 8 | 0 | 8 | 0 | 0 |
| empty-keyed-group-naming | A0 | 16 | 1 | 13 | 0 | 2 |
| empty-keyed-group-naming | A0 | 24 | 3 | 16 | 2 | 3 |
| empty-keyed-group-naming | A0 | 32 | 3 | 22 | 3 | 4 |
| empty-keyed-group-naming | R | 8 | 1 | 5 | 0 | 2 |
| empty-keyed-group-naming | R | 16 | 2 | 8 | 3 | 3 |
| empty-keyed-group-naming | R | 24 | 3 | 13 | 4 | 4 |
| empty-keyed-group-naming | R | 32 | 3 | 20 | 4 | 5 |
| empty-keyed-group-naming | V | 8 | 1 | 6 | 0 | 1 |
| empty-keyed-group-naming | V | 16 | 1 | 13 | 0 | 2 |
| empty-keyed-group-naming | V | 24 | 3 | 15 | 2 | 4 |
| empty-keyed-group-naming | V | 32 | 3 | 20 | 4 | 5 |
| empty-keyed-group-naming | V-no-cost | 8 | 1 | 6 | 0 | 1 |
| empty-keyed-group-naming | V-no-cost | 16 | 2 | 9 | 2 | 3 |
| empty-keyed-group-naming | V-no-cost | 24 | 3 | 15 | 2 | 4 |
| empty-keyed-group-naming | V-no-cost | 32 | 3 | 20 | 4 | 5 |
| mapping-subtype-combination | S | 8 | 1 | 4 | 2 | 1 |
| mapping-subtype-combination | S | 16 | 2 | 7 | 2 | 5 |
| mapping-subtype-combination | S | 24 | 4 | 10 | 2 | 8 |
| mapping-subtype-combination | S | 32 | 5 | 13 | 6 | 8 |
| mapping-subtype-combination | A0 | 8 | 1 | 3 | 1 | 3 |
| mapping-subtype-combination | A0 | 16 | 3 | 6 | 3 | 4 |
| mapping-subtype-combination | A0 | 24 | 4 | 9 | 4 | 7 |
| mapping-subtype-combination | A0 | 32 | 5 | 11 | 5 | 11 |
| mapping-subtype-combination | R | 8 | 3 | 0 | 1 | 4 |
| mapping-subtype-combination | R | 16 | 4 | 0 | 2 | 10 |
| mapping-subtype-combination | R | 24 | 4 | 4 | 5 | 11 |
| mapping-subtype-combination | R | 32 | 4 | 8 | 8 | 12 |
| mapping-subtype-combination | V | 8 | 3 | 3 | 1 | 1 |
| mapping-subtype-combination | V | 16 | 5 | 5 | 2 | 4 |
| mapping-subtype-combination | V | 24 | 6 | 8 | 3 | 7 |
| mapping-subtype-combination | V | 32 | 6 | 8 | 6 | 12 |
| mapping-subtype-combination | V-no-cost | 8 | 3 | 3 | 1 | 1 |
| mapping-subtype-combination | V-no-cost | 16 | 5 | 5 | 2 | 4 |
| mapping-subtype-combination | V-no-cost | 24 | 6 | 8 | 3 | 7 |
| mapping-subtype-combination | V-no-cost | 32 | 6 | 9 | 5 | 12 |
| documentation-macro-boundaries | S | 8 | 1 | 7 | 0 | 0 |
| documentation-macro-boundaries | S | 16 | 1 | 13 | 0 | 2 |
| documentation-macro-boundaries | S | 24 | 2 | 17 | 0 | 5 |
| documentation-macro-boundaries | S | 32 | 2 | 22 | 0 | 8 |
| documentation-macro-boundaries | A0 | 8 | 1 | 6 | 0 | 1 |
| documentation-macro-boundaries | A0 | 16 | 1 | 14 | 0 | 1 |
| documentation-macro-boundaries | A0 | 24 | 2 | 19 | 0 | 3 |
| documentation-macro-boundaries | A0 | 32 | 2 | 26 | 0 | 4 |
| documentation-macro-boundaries | R | 8 | 0 | 6 | 0 | 2 |
| documentation-macro-boundaries | R | 16 | 0 | 10 | 0 | 6 |
| documentation-macro-boundaries | R | 24 | 0 | 18 | 0 | 6 |
| documentation-macro-boundaries | R | 32 | 0 | 24 | 0 | 8 |
| documentation-macro-boundaries | V | 8 | 0 | 8 | 0 | 0 |
| documentation-macro-boundaries | V | 16 | 1 | 14 | 0 | 1 |
| documentation-macro-boundaries | V | 24 | 1 | 20 | 0 | 3 |
| documentation-macro-boundaries | V | 32 | 1 | 24 | 0 | 7 |
| documentation-macro-boundaries | V-no-cost | 8 | 0 | 8 | 0 | 0 |
| documentation-macro-boundaries | V-no-cost | 16 | 1 | 14 | 0 | 1 |
| documentation-macro-boundaries | V-no-cost | 24 | 1 | 20 | 0 | 3 |
| documentation-macro-boundaries | V-no-cost | 32 | 1 | 23 | 0 | 8 |
| variable-file-cache | S | 8 | 2 | 5 | 0 | 1 |
| variable-file-cache | S | 16 | 3 | 10 | 0 | 3 |
| variable-file-cache | S | 24 | 3 | 16 | 0 | 5 |
| variable-file-cache | S | 32 | 3 | 22 | 0 | 7 |
| variable-file-cache | A0 | 8 | 0 | 7 | 0 | 1 |
| variable-file-cache | A0 | 16 | 3 | 10 | 0 | 3 |
| variable-file-cache | A0 | 24 | 3 | 18 | 0 | 3 |
| variable-file-cache | A0 | 32 | 5 | 22 | 1 | 4 |
| variable-file-cache | R | 8 | 2 | 1 | 0 | 5 |
| variable-file-cache | R | 16 | 3 | 5 | 1 | 7 |
| variable-file-cache | R | 24 | 5 | 10 | 1 | 8 |
| variable-file-cache | R | 32 | 5 | 17 | 1 | 9 |
| variable-file-cache | V | 8 | 2 | 4 | 0 | 2 |
| variable-file-cache | V | 16 | 2 | 11 | 0 | 3 |
| variable-file-cache | V | 24 | 4 | 15 | 0 | 5 |
| variable-file-cache | V | 32 | 4 | 20 | 1 | 7 |
| variable-file-cache | V-no-cost | 8 | 2 | 4 | 0 | 2 |
| variable-file-cache | V-no-cost | 16 | 2 | 11 | 0 | 3 |
| variable-file-cache | V-no-cost | 24 | 4 | 15 | 0 | 5 |
| variable-file-cache | V-no-cost | 32 | 4 | 20 | 1 | 7 |

三层明细见 pair-ranking.json；混合面板含 R 构造的相关层，不能解释成全域先验。面板外关系保持未知。

## 真实获取

| 运行 | 严格合格 | 请求位置 | 合法行 | 支持正 | 支持零 | 秒 | 停止原因 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 00-variable-file-cache-R-r1 | True | 8 | 8 | 2 | 1 | 41.139 | NO_AFFORDABLE_BATCH |
| 01-variable-file-cache-R-r0 | True | 8 | 8 | 2 | 1 | 42.227 | NO_AFFORDABLE_BATCH |
| 02-documentation-macro-boundaries-R-r0 | True | 4 | 4 | 1 | 1 | 32.006 | NO_AFFORDABLE_BATCH |
| 03-documentation-macro-boundaries-A0-r0 | True | 8 | 8 | 0 | 5 | 35.671 | NO_AFFORDABLE_BATCH |
| 04-documentation-macro-boundaries-A0-r1 | True | 8 | 8 | 0 | 4 | 33.881 | NO_AFFORDABLE_BATCH |
| 05-variable-file-cache-A0-r0 | True | 8 | 6 | 0 | 6 | 34.695 | NO_AFFORDABLE_BATCH |
| 06-variable-file-cache-A0-r1 | True | 8 | 8 | 0 | 7 | 33.653 | NO_AFFORDABLE_BATCH |
| 07-variable-file-cache-V-r0 | True | 8 | 6 | 1 | 5 | 36.514 | NO_AFFORDABLE_BATCH |
| 08-variable-file-cache-V-r1 | True | 8 | 8 | 0 | 7 | 32.348 | NO_AFFORDABLE_BATCH |
| 09-documentation-macro-boundaries-V-r0 | True | 10 | 10 | 1 | 8 | 39.038 | NO_AFFORDABLE_BATCH |
| 10-documentation-macro-boundaries-R-r1 | False | 5 | 5 | 0 | 1 | 35.576 | NO_AFFORDABLE_BATCH |
| 11-documentation-macro-boundaries-V-r1 | True | 8 | 8 | 0 | 7 | 33.104 | NO_AFFORDABLE_BATCH |

宏R-r1违反单对批次限制；保留原记录，但严格比较排除。12次尝试、11次严格合格，online_acquisition=PARTIAL。

## 接口因素

| 序列 | 生命周期 | 批量 | 合法行 | 完整秒 | 初始化秒 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | cold | 2 | 2 | 12.377 | 0.795 | COMPLETED |
| 0 | cold | 2 | 2 | 14.962 | 1.005 | COMPLETED |
| 0 | cold | 2 | 2 | 14.619 | 0.733 | COMPLETED |
| 0 | cold | 2 | 2 | 17.251 | 0.74 | COMPLETED |
| 1 | cold | 2 | 2 | 12.596 | 0.721 | COMPLETED |
| 1 | cold | 2 | 2 | 14.964 | 0.632 | COMPLETED |
| 1 | cold | 2 | 2 | 10.772 | 0.622 | COMPLETED |
| 1 | cold | 2 | 2 | 15.437 | 0.702 | COMPLETED |
| 2 | reuse | 8 | 8 | 37.183 | 0.635 | COMPLETED |
| 3 | reuse | 2 | 2 | 10.714 | 0.633 | COMPLETED |
| 3 | reuse | 2 | 2 | 13.646 | 0.0 | COMPLETED |
| 3 | reuse | 2 | 2 | 13.495 | 0.0 | COMPLETED |
| 3 | reuse | 2 | 2 | 11.298 | 0.0 | COMPLETED |
| 4 | reuse | 8 | 8 | 39.574 | 0.648 | COMPLETED |
| 5 | reuse | 2 | 2 | 12.39 | 0.62 | COMPLETED |
| 5 | reuse | 2 | 2 | 12.36 | 0.0 | COMPLETED |
| 5 | reuse | 2 | 2 | 11.809 | 0.0 | COMPLETED |
| 5 | reuse | 2 | 2 | 18.402 | 0.0 | COMPLETED |
| 6 | cold | 8 | 8 | 40.277 | 0.712 | COMPLETED |
| 7 | cold | 8 | 8 | 37.076 | 0.634 | COMPLETED |

只报告两次测量序列的原始值；不估计可靠 p95。

## 知识包

| 状态 | 运行 | 相对MMR变化 | 直接规范 | 验证模式 | 实现上下文 | 未知 |
| --- | --- | --- | --- | --- | --- | --- |
| empty-keyed-group-naming | replay | True | 0 | 0 | 3 | 21 |
| empty-keyed-group-naming | replay | True | 0 | 0 | 5 | 19 |
| empty-keyed-group-naming | replay | True | 0 | 0 | 5 | 19 |
| empty-keyed-group-naming | replay | True | 0 | 0 | 5 | 19 |
| empty-keyed-group-naming | replay | True | 0 | 0 | 5 | 19 |
| mapping-subtype-combination | replay | True | 1 | 0 | 6 | 7 |
| mapping-subtype-combination | replay | True | 1 | 1 | 6 | 11 |
| mapping-subtype-combination | replay | True | 0 | 1 | 6 | 6 |
| mapping-subtype-combination | replay | True | 1 | 1 | 6 | 13 |
| mapping-subtype-combination | replay | True | 1 | 1 | 6 | 13 |
| documentation-macro-boundaries | replay | True | 0 | 0 | 1 | 20 |
| documentation-macro-boundaries | replay | True | 0 | 0 | 1 | 20 |
| documentation-macro-boundaries | replay | True | 0 | 0 | 1 | 20 |
| documentation-macro-boundaries | replay | True | 0 | 0 | 1 | 20 |
| documentation-macro-boundaries | replay | True | 0 | 0 | 1 | 20 |
| variable-file-cache | replay | True | 0 | 0 | 3 | 4 |
| variable-file-cache | replay | True | 0 | 0 | 3 | 4 |
| variable-file-cache | replay | True | 0 | 0 | 3 | 4 |
| variable-file-cache | replay | True | 0 | 0 | 3 | 4 |
| variable-file-cache | replay | True | 0 | 0 | 3 | 4 |
| variable-file-cache | 00-variable-file-cache-R-r1 | True | 0 | 0 | 4 | 0 |
| variable-file-cache | 01-variable-file-cache-R-r0 | True | 0 | 0 | 4 | 0 |
| documentation-macro-boundaries | 02-documentation-macro-boundaries-R-r0 | True | 0 | 0 | 14 | 0 |
| documentation-macro-boundaries | 03-documentation-macro-boundaries-A0-r0 | False | 0 | 0 | 12 | 2 |
| documentation-macro-boundaries | 04-documentation-macro-boundaries-A0-r1 | True | 0 | 0 | 12 | 1 |
| variable-file-cache | 05-variable-file-cache-A0-r0 | False | 0 | 0 | 4 | 0 |
| variable-file-cache | 06-variable-file-cache-A0-r1 | False | 0 | 0 | 4 | 0 |
| variable-file-cache | 07-variable-file-cache-V-r0 | True | 0 | 0 | 4 | 0 |
| variable-file-cache | 08-variable-file-cache-V-r1 | True | 0 | 0 | 4 | 0 |
| documentation-macro-boundaries | 09-documentation-macro-boundaries-V-r0 | True | 0 | 0 | 12 | 1 |
| documentation-macro-boundaries | 10-documentation-macro-boundaries-R-r1 | True | 0 | 0 | 14 | 0 |
| documentation-macro-boundaries | 11-documentation-macro-boundaries-V-r1 | True | 0 | 0 | 12 | 1 |
