# 条件适用性 Pointwise 研究结果

**结论：真实 pointwise 训练与重载完成，但未证明相对强便宜对照的新增优势；无合格支持操作点，未执行新的修复 Agent 对照。**

`data=READY` · `pointwise_training=TRAINED_AND_RELOADED` · `text_discrimination=NO_DEMONSTRATED_GAIN` · `supported_operating_point=NOT_ESTABLISHED` · `runtime=NOT_RUN`。

这里的 NO_DEMONSTRATED_GAIN 指相对技能先验、便宜文本和 Fixed 的新增优势未建立，不否定相对冻结底座的改善：原始 Brier 0.2503 → 0.0961。技能先验为 0.0900、便宜文本为 0.0688；校准模型为 0.0692，不能以数值接近宣称等价。新模型的特定 P@2 为 0.125，Fixed 为 0.375。只有四个 check 机制组，所有标签均为未人工审核的模型弱标签。


本轮研究完成情况与最终发布状态见下列证据。文本弱标签上的区分、支持资格和真实补丁效用分别判断；本研究不改变默认策略。

## 数据与先验

| 分区 | 任务/机制/需求 | 配对行 | 适用 | 不适用 | 未知 | 特定/通用/未知（仅适用） |
|---|---:|---:|---:|---:|---:|---:|
| fit | 12/12/12 | 120 | 41 | 75 | 4 | 17/24/0 |
| model-dev | 4/4/4 | 40 | 14 | 24 | 2 | 6/8/0 |
| cal | 4/4/4 | 40 | 10 | 29 | 1 | 2/8/0 |
| check | 4/4/4 | 40 | 11 | 26 | 3 | 3/8/0 |

共 24 个自然公开需求、24 个机制组、10 项技能、240 行；每个请求保留为 composite requirement。不是 240 个独立任务。两份同模型独立上下文判断形成弱标签，未人工审核。所有分歧保留 UNKNOWN，没有构造主集负例或按模型结果改标签。

全局/技能先验仅来自 fit，平滑度由 model-dev 决定。check 自身比例的事后参考 Brier 为 0.2100，单列而不充当训练基线。Fixed 只参与选择指标，不赋予虚构概率。

## 独立离线检查

以下均为四个未用于本轮训练/选择/校准的 check 机制组。Brier/log-loss 先按组内已知标签平均，再给机制组等权；AUC/AUPRC 表格列按机制组宏平均。单类项为 null，逐技能覆盖和概率可靠性桶见 results.json。

| 模型 | Brier ↓ | Log-loss ↓ | 组宏 AUC ↑ | 组宏 AUPRC ↑ | 特异性 Brier ↓ | 特定 P@2 ↑ | 特定 R@2 ↑ | 已知不适用@2 ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| global_prior | 0.2142 | 0.6203 | 0.5000 | 0.3000 | 0.2147 | 0.1250 | 0.2500 | 0.8750 |
| skill_prior | 0.0900 | 0.3055 | 0.8972 | 0.9003 | 0.0099 | 0.0000 | 0.0000 | 0.7500 |
| cheap_text | 0.0688 | 0.2275 | 0.9472 | 0.9458 | 0.0000 | 0.1250 | 0.2500 | 0.6250 |
| skill_only | 0.0896 | 0.2926 | 0.8833 | 0.9003 | 0.0000 | 0.0000 | 0.0000 | 0.7500 |
| learned_raw | 0.0961 | 0.3310 | 0.9722 | 0.9667 | 0.3418 | 0.1250 | 0.2500 | 0.0000 |
| frozen_raw | 0.2503 | 0.7835 | 0.7739 | 0.6381 | 0.2123 | 0.1250 | 0.2500 | 0.3750 |
| no_aux_raw | 0.0961 | 0.3310 | 0.9722 | 0.9667 | 0.3418 | 0.1250 | 0.2500 | 0.0000 |
| joint_raw | 0.1536 | 0.4668 | 0.8785 | 0.8107 | 0.2086 | 0.2500 | 0.5000 | 0.1250 |
| learned_no_context_raw | 0.2447 | 0.6710 | 0.6006 | 0.5441 | 0.2056 | 0.2500 | 0.5000 | 0.5000 |
| learned_calibrated | 0.0692 | 0.3488 | 0.9722 | 0.9667 | 0.3418 | 0.1250 | 0.2500 | 0.0000 |
| fixed_workflow | — | — | — | — | — | 0.3750 | 1.0000 | 0.5000 |

上述 Top-2 使用 p_app × p_specific 的文本优先级（Fixed 例外），不代表预期修复收益。原 rank 对照另列；原 rank 1024-token 预算与支持模型 8192-token 输入差异不隐藏。无辅助模型的特异性头没有直接监督。相同 checkpoint 的 learned/joint/no_aux 别名不是独立训练重复。

| 排序/过滤方法 | 特定 P@2 | 特定 R@2 | 已知不适用@2 | 选满两项任务/全部任务 |
|---|---:|---:|---:|---:|
| 原 rank B2 | 0.2500 | 0.7500 | 0.5000 | 4/4 |
| 原 rank + 支持过滤 C2 | 0.0000 | 0.0000 | 0.0000 | 0/4 |
| 新 priority + 支持资格 | 0.0000 | 0.0000 | 0.0000 | 0/4 |

原 rank 截断 40/40 行。空集合保留在全部任务分母中，不补齐、不记成成功；没有特定正例的任务也保留。实际选中 ID、正例排名、UNKNOWN 接受数均在逐任务/逐行 JSON 中。

### 配对 Brier 差值

差值为 learned_raw 减对照，负值更低；1000 次机制组重采样、seed 7170，仅探索性，不做等价/非劣/安全结论。

- 对 frozen_raw: -0.1543，95% percentile 区间 [-0.1978, -0.1168]。
- 对 global_prior: -0.1182，95% percentile 区间 [-0.1611, -0.0779]。
- 对 skill_prior: 0.0061，95% percentile 区间 [-0.0317, 0.0439]。
- 对 cheap_text: 0.0273，95% percentile 区间 [0.0051, 0.0495]。
- 对 skill_only: 0.0065，95% percentile 区间 [-0.0325, 0.0456]。

## 支持操作点与条件执行

cal 状态 `NOT_ESTABLISHED`，阈值 `None`，原因 `INSUFFICIENT_ELIGIBLE_GROUPS`。可用上下文仅覆盖 2 个 cal 机制组，低于冻结规则的至少 3 组；这一结构性资格不足不能单独证明文本分类无效。目标精度仍为 0.90，同时要求至少 6 行、已知覆盖 0.10、UNKNOWN 接受为 0。

完整 cal/check precision—coverage 曲线和文本-only 诊断分开保存。零接受 precision=null；机制 bootstrap 区间注明非空重采样数，不是安全置信保证。未根据 check 改阈值。

| 预选任务 | N+ | 原 rank B2 | 同 rank C2 | 原因 |
|---|---|---|---|---|
| sqlite-utils-issue-207 | NOT_EXECUTED | NOT_EXECUTED | NOT_EXECUTED | 无合格支持操作点 |
| csv-diff-issue-39 | NOT_EXECUTED | NOT_EXECUTED | NOT_EXECUTED | 无合格支持操作点 |

本轮新修复 Agent 执行数为 0，不再跑全部回退 smoke；没有支持分支的物化/读取、补丁或目标+回归证据，不宣称修复收益。旧 r-repair 的回退执行留在历史结果中。

## 真实训练与冻结选择

model-dev 选择 `training-lambda-0` epoch 3，组宏适用性 log-loss 0.2709。选中 adapter SHA-256：`cba6b64c0cbc2b031ad6f01e3b9923a6f8c580970692ffbe8ed84b4590cf3db7`。全部候选与 epoch 的选择指标、重载哈希和误差保留，未按 check 选模型。

- training-lambda-1: 2052.95 秒，60 次非零梯度更新，112 个张量变化，1146880 个可训练参数；ALL_EPOCHS_MATCHED。观察到的 MPS driver allocation 峰值 20606287872 bytes。
- training-lambda-0: 1494.04 秒，45 次非零梯度更新，112 个张量变化，1146880 个可训练参数；ALL_EPOCHS_MATCHED。观察到的 MPS driver allocation 峰值 19775815680 bytes。

底座/两种 adapter 身份、训练配方与限制见 [模型卡](model-card.md)。计时不含所有数据准备/依赖安装；内存是采样观察值。标注 per-call token 和金额未暴露，金额为 null；Goal 总 token 不当作算法在线成本。

[使用命令](usage.md) · [数据卡](data-card.md) · [复核索引](review-index.md) · [中文复盘](retrospective.md)

## 消融与错误走读

- 上下文：相同选中权重去掉公开上下文后，原始适用性 Brier 从 0.0961 变为 0.2447；这是该输入消融的观察，不能排除项目词、格式词等浅层关联，不能据此声称掌握仓库推理。
- 辅助任务：联合候选原始 Brier 0.1536、特定 P@2 0.250；无辅助主模型为 0.0961 / 0.125。两者有权衡，不在看见 check 后改选联合候选。主模型的条件特异性没有直接监督，且 cal 特异性仅 2 个正例，保持未校准。
- 通用帮助误当特定帮助：`csvkit-issue-1177::systematic-debugging` 的弱标签为 GENERAL_WORKFLOW，主模型特异性概率却为 0.945。其实际步骤是重现一行输入并区分 header/data；这是合理的通用适用帮助，不应因为排序目标而把它改成不适用。
- 格式范围与真实不适用：`sqlite-utils-issue-274::sql-query-export` 请求 reconstructable SQL dump，而技能讲 SQL 查询结果导出 CSV。弱标签不适用，主模型原始适用概率 0.047，属于正确的文本区分；不代表实际导出实现已经验证。
- 漏掉具体条件：`sqlite-utils-issue-207::sqlite-ingest` 的请求包含可选地将统计结果写回数据库。两份标注将此视为技能的具体部分帮助，主模型原始适用概率仅 0.059。相对于当前弱标签是漏判；两位标注者也可能共同把一个可选子步骤扩张为整项技能适用，引用的核验步骤不能代替人工语义复核。
- 否定/保留条件：csvkit #1177 明确说首行不匹配仍被返回，但具体 header 语义存在解释空间；`tabular-conversion` 的两份判断分别把 header 检查视为部分帮助、或认为格式转换不提供 grep 匹配语义，最终保持 UNKNOWN。没有足够自然冲突标签可报告冲突召回；构造的否定单元测试只验证程序行为，不证明模型理解这些条件。
- 技能名与先验捷径：`csv-diff-issue-39::keyed-csv-diff` 原始适用概率 0.897，可能利用请求与技能名称/操作词重合；没有单独的 name-only 消融，不能归因为深层语义。skill-only 名称/正文负控制 Brier 0.0896，优于主模型原始 0.0961。主模型跨任务分数并非常量，但这种变化并不足以证明相对先验的收益。
- 不只看成功：同一 diff 输出需求下，`csv-dialect` 被双方标为 TASK_SPECIFIC，主模型原始适用概率仅 0.468，便宜文本模型更低（0.066）；完整目录与 UNKNOWN 都保留，没有据此补标或扩充训练。

这些案例的原请求、完整技能正文、两份判断与逐字引用分别在 tasks.json、registry.json 和 labels.jsonl 中；逐行预测在 check-predictions.jsonl 中。它们是对现有弱标签的误差分析，不是人工真值认证。

check 的特定正例仅 3 行，分布于 2/4 个任务。P@2 对全部 4 个任务计算；R@2 和正例平均排名在无正例任务上为 null，宏平均覆盖其余 2 个任务，并单列零正例任务数。逐技能 AUC 仅覆盖 csv-dialect、keyed-csv-diff、sqlite-ingest，其余单类/未知项不填成 1。操作点表的 mean_positive_rank 是过滤前排序诊断，即使接受集合为空也不代表选中了正例。
