# Decision alignment / calibration preflight

本轮是旧数据的 `RETROSPECTIVE_DIAGNOSTIC`。默认 native 不变；没有重训、模型 forward、校准拟合、Agent 矩阵或 fallback smoke。A/J 使用已有六 checkpoint 的保存分数。

## 结论与证据边界

- 工程：两个目标的开发选模、排序合同、零 forward 预检和可安装入口已实现；回归和交付状态见 [validation.json](../../../artifacts/decision-alignment-v1/validation.json)。
- 资格：旧上下文最多 2 组，修复后上下文 4 组；40/40 候选 token 完整。但存档只确认文本研究环境、仓库依赖未验证，新严格支持资格仍为 `BLOCKED`。
- 支持操作点：`NOT_ESTABLISHED`。A 的映射类别必要条件满足，J 的条件特异性正例只有 2，低于原每类 3；后者不阻断 A。
- 效用：`runtime_effectiveness=NOT_RUN`；用户掌握情况 `NOT_ASSESSED`。旧 check 已看过，不是独立确认；不能声称修复率、在线降本或安全保证。

## 实际选模与排序

旧规则以适用性 loss 选出 lambda=0 / epoch 3，却以无直接特异性监督的两轴乘积排序。共享 causal 模型仍可能保留底座特异性能力，但这不是本轮直接监督。旧结果保持 legacy，不重写。

A 在六候选中以机制宏平均适用性 loss 选中 lambda=0 / epoch 3（0.2708732148），只读适用性轴。J 只允许两轴监督分母非零的三个 joint checkpoint，以同一原始乘积的联合事件 loss 选中 lambda=1 / epoch 3（0.2248473067）。模型名不代替监督证据，cal/check 不参与选择。

csv-diff #39 的完整十项顺序如下；数值是建议分数，J 不是联合成功概率。

| 名次 | 旧 legacy 乘积 | A 适用性 | J 任务特定优先级 |
|---|---|---|---|
| 1 | keyed-csv-diff (0.5820) | keyed-csv-diff (0.8972) | keyed-csv-diff (0.5592) |
| 2 | systematic-debugging (0.3012) | verification-before-completion (0.6673) | csv-dialect (0.2274) |
| 3 | verification-before-completion (0.1852) | systematic-debugging (0.6063) | sql-query-export (0.1650) |
| 4 | csv-dialect (0.1414) | csv-dialect (0.4682) | sqlite-schema (0.1481) |
| 5 | sqlite-schema (0.1040) | sqlite-schema (0.4117) | tabular-conversion (0.1218) |
| 6 | sql-query-export (0.0883) | sql-query-export (0.4078) | systematic-debugging (0.1215) |
| 7 | tabular-conversion (0.0670) | csv-relational-join (0.3693) | csv-relational-join (0.1144) |
| 8 | csv-relational-join (0.0575) | tabular-conversion (0.3606) | verification-before-completion (0.0849) |
| 9 | sqlite-ingest (0.0317) | sqlite-fulltext (0.3032) | sqlite-ingest (0.0740) |
| 10 | sqlite-fulltext (0.0253) | sqlite-ingest (0.2352) | sqlite-fulltext (0.0537) |

A 第二项通用验证可能符合适用性目标；J 第二项 csv-dialect 更特定，但不能推导补丁收益。完整分轴指标、P@2/R@2、已知不适用@2、UNKNOWN@2、填满K比例和所有 check 任务顺序见 [ranking-replay.json](../../../artifacts/decision-alignment-v1/ranking-replay.json)。cheap_text / skill_prior / skill_only 均为旧冻结 fit/dev 基线，任务特定列只是同目标原始乘积诊断，不冒充重新优化的强对照。原 rank 保持原顺序；其1024-token与支持模型8192-token预算不同。rank＋support 无阈值、接受precision为null，不以回退全目录冒充Top-2。

## 四个 cal 组的资格

| 任务／机制 | 旧状态 → 修复后 | 原关键缺失（受影响候选） | token | 已知适用性 | 上下文可贡献组 |
|---|---|---|---|---|---|
| sqlite-utils-issue-211 / trigger-introspection | usable → usable | 无 (0/10) | 10/10完整 | 10/10 | 1 → 1 |
| sqlite-utils-issue-236 / database-attachment | usable → usable | 无 (0/10) | 10/10完整 | 10/10 | 1 → 1 |
| csvkit-issue-1148 / multiline-display | partial → usable | or: explicit_call_unlocated (10/10) | 10/10完整 | 9/10 | 0 → 1 |
| csv-diff-issue-31 / duplicate-diff-key | partial → usable | warning: explicit_call_unlocated (10/10) | 10/10完整 | 10/10 | 0 → 1 |

来源：[原 tasks/context](../../../artifacts/conditional-applicability-v1/tasks.json)、[原协议](../../../configs/conditional-applicability-v1/protocol.json)、[旧预检](../../../artifacts/decision-alignment-v1/calibration-preflight.json)、[修复后预检](../../../artifacts/decision-alignment-v1/calibration-preflight-repaired.json)。所有行的执行环境条件仍 UNKNOWN；故严格可接受组为0。初始无tokenizer预检仍能从上下文上界2直接证明小于3，不能把UNKNOWN token报为已验证。

## 两个实际根因与未放行反例

csvkit #1148 的 `or (the easier way)` 与 csv-diff #31 的 `warning (maybe allowing…)` 被旧 `extract_fragments` 中宽泛的 identifier＋可选空白＋左括号规则当成必须找到的函数。实际选中窗口分别包含完整 CSVLook 与 load_csv 等声明；原快照所有已存完整文件摘要均匹配，问题不是新版本源码替代或预算扩容。

新 `extract_repaired` 保留原提取器，逐一识别普通散文中的明确括号补充语；代码块、反引号、相邻调用和语义不明的空格调用仍严格处理。仅移除已证实的假调用原因，保留其他关键缺失和扫描预算阻塞。新context版本与身份单独记录，原tasks、旧logits和旧calibrator未改。

`missing_call()`、`warning (value)`、明确缺失文件、过小扫描预算与越界／symlink路径仍不合格。修复不是把所有partial改usable；源码事实和原文未新增，仅移除误判，旧弱标签仍只作为诊断标签。完整修复证据见 [context-repair.json](../../../artifacts/decision-alignment-v1/context-repair.json)。

## 安装与调用

参见 [usage.md](usage.md)。历史 records 委托原冻结模块；新支持校准使用共享资格结果，不删除历史源码哈希检查。在线 manifest 不含标签/quote_refs，也不读训练档案。supported 是显式路径，无阈值不能退化成Top-2；当前没有可用新阈值。现阶段生成的校准对象只允许其明确绑定且合格的公共输入，不认证对新任务的外推。

## 后续所需证据

先独立确认实际环境与必要条件；未来独立校准/检查必须在新规则及未知模型分数下选定新来源。本轮不加新组、不移check到cal、不补训练、不自动扩展。即使以后获得旧数据阈值，也最多是后验结果。
