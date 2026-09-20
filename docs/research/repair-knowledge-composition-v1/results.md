# 修复知识与缺口组合：实际功能结果

功能成功仅指目标行为通过且保护回归无新增失败。表中未知不记作失败；覆盖、策略与成本不参与此判定。
本表采用统一v2后验验收，标记 `POSTHOC_ACCEPTANCE_REVALIDATION`；原版测试补丁安装冲突与UNKNOWN完整保留，见 [posthoc-acceptance.md](posthoc-acceptance.md)。没有新增Agent。
`invalid-host-field-errors` 的0/False错误分类缺乏明确公开合同依据，全部臂统一保留功能UNKNOWN；v2原始检查与空容器保护失败另存，不改判PASS。

## 开发功能主表

| 机制 | 原生探测 | N续跑 | G提醒 | L旧技能 | M同库MMR | H组合 | H−M |
|---|---|---|---|---|---|---|---|
| empty-keyed-group-naming | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 0.0 |
| invalid-host-field-errors | UNKNOWN (2/2) | UNKNOWN (2/2) | UNKNOWN (2/2) | UNKNOWN (2/2) | UNKNOWN (2/2) | UNKNOWN (2/2) | UNKNOWN |
| iterator-state-enum-compatibility | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 0.0 |
| mapping-subtype-combination | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) | 0.0 |

四机制等权 H−M：`UNKNOWN`；三个可判定机制各自均为0，不以其均值替代缺失机制。小样本条件比较不构成部署收益或因果普遍性证明。
冻结内容路线改善信号机制：`[]`。确认规则结果：`UNRESOLVED`。

## 消融与实际选择（诊断附表）

| 机制 | H | H-no-gap | H-no-exposure |
|---|---|---|---|
| empty-keyed-group-naming | 2/2 (未知 0) | 2/2 (未知 0) | 2/2 (未知 0) |
| invalid-host-field-errors | UNKNOWN (2/2) | UNKNOWN (2/2) | UNKNOWN (2/2) |

以下分解是选择函数值，不是修复增益；完整单元与来源见证据目录。

| 机制/方法 | 候选索引 | token | 覆盖 | 相关性奖励 | 冗余惩罚 | 暴露惩罚 | 总分 |
|---|---|---:|---:|---:|---:|---:|---:|
| empty-keyed-group-naming/M | [0, 2, 1, 3] | 1195 | 0.245454 | 0.225600 | 0.231493 | 0.016750 | 0.222810 |
| empty-keyed-group-naming/H | [19, 3, 0] | 696 | 0.255317 | 0.148651 | 0.095205 | 0.002083 | 0.306679 |
| empty-keyed-group-naming/H-no-gap | [5, 22] | 301 | 0.000000 | 0.084623 | 0.022199 | 0.000000 | 0.062424 |
| empty-keyed-group-naming/H-no-exposure | [19, 21, 3] | 420 | 0.257119 | 0.124307 | 0.057078 | 0.000000 | 0.324348 |
| invalid-host-field-errors/M | [0, 2, 3, 5] | 1064 | 0.281237 | 0.251378 | 0.210543 | 0.025317 | 0.296755 |
| invalid-host-field-errors/H | [1, 0] | 389 | 0.286523 | 0.140997 | 0.062262 | 0.005556 | 0.359702 |
| invalid-host-field-errors/H-no-gap | [0] | 238 | 0.000000 | 0.078792 | 0.000000 | 0.005556 | 0.073237 |
| invalid-host-field-errors/H-no-exposure | [9, 0, 2] | 571 | 0.282742 | 0.190591 | 0.115683 | 0.000000 | 0.357650 |
| iterator-state-enum-compatibility/M | [0, 1, 4, 3] | 1076 | 0.291328 | 0.212355 | 0.190876 | 0.017083 | 0.295724 |
| iterator-state-enum-compatibility/H | [10, 23, 0] | 475 | 0.308913 | 0.127765 | 0.072066 | 0.025000 | 0.339612 |
| iterator-state-enum-compatibility/H-no-gap | [8, 4] | 348 | 0.000000 | 0.092996 | 0.029275 | 0.005000 | 0.058720 |
| iterator-state-enum-compatibility/H-no-exposure | [10, 23, 0] | 475 | 0.308913 | 0.127765 | 0.072066 | 0.000000 | 0.364612 |
| mapping-subtype-combination/M | [0, 3, 5, 1] | 1138 | 0.239811 | 0.241424 | 0.183610 | 0.016680 | 0.280944 |
| mapping-subtype-combination/H | [8, 23, 0] | 503 | 0.297554 | 0.149810 | 0.105524 | 0.003333 | 0.338507 |
| mapping-subtype-combination/H-no-gap | [8, 0] | 381 | 0.000000 | 0.121394 | 0.038545 | 0.003333 | 0.079515 |
| mapping-subtype-combination/H-no-exposure | [8, 23, 22, 0] | 619 | 0.307568 | 0.179475 | 0.147238 | 0.000000 | 0.339805 |

## 确认与范围

继续证据判定 `UNRESOLVED`；确认执行状态 `NOT_TRIGGERED`（未执行），原因是合同歧义使完整可判定证据条件不满足。这不等于已证明所有机制没有改善线索；不以补零或追加样本处理。

没有合法固定续跑状态的开发机制：`[]`。
仅 Ansible 单仓库、4 个开发机制、每格2重复；没有未见仓库泛化证据，也不能排除预训练污染。iterator 保护范围含1个实际PASS与7个既有skip，不等于全仓保护。

旧六份原补丁只作 `POSTHOC_ACCEPTANCE_ONLY`，目标与保护均通过；不改写历史UNKNOWN，不称技能救回。
歧义机制的原始v2机械结果为G通过1/2，其他主臂与消融均0/2；保留这些原始检查，不能将它们升格为有效功能差异。

## 工程与复算

入口见 [reproduction.md](reproduction.md)。公共证据中的 replay 只重算原补丁身份、JUnit、冻结选择与功能表，不代表第二次Agent运行。
默认策略 `UNCHANGED`；新 gain/wait 训练 `NOT_IN_SCOPE`。成本、策略与来源支持均为附表。

原版裁判与统一后验裁判的区别（不是算法改善）：

| 相位/裁判 | 功能通过/计划（未知） |
|---|---|
| native/v1 | 2/8 (未知 6) |
| native/v2 | 6/8 (未知 0) |
| pilot/v1 | 14/48 (未知 34) |
| pilot/v2 | 35/48 (未知 0) |
