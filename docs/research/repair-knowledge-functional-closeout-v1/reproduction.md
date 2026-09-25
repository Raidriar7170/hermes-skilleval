# 执行记录

本轮依据完整 Goal 执行；继承 PR #55 的 `b6d9316`，保留旧研究。新工作树为 `hermes-functional-closeout`，私有输出为相邻 `hermes-functional-closeout-private/study-v1`。执行 Python 为 `/opt/anaconda3/bin/python`，命令统一 `PYTHONPATH=src`。

已成功执行：

```sh
python -m hermes_skilleval.intervention.functional_closeout prepare --assets .. --output ../hermes-functional-closeout-private/study-v1
python scripts/functional_closeout/prepare_acceptance.py .. ../hermes-functional-closeout-private/study-v1
python scripts/functional_closeout/resolve_supplemental_selectors.py ../hermes-functional-closeout-private/study-v1
python -m hermes_skilleval.intervention.functional_closeout qualify --assets .. --output ../hermes-functional-closeout-private/study-v1 --tasks ../hermes-functional-closeout-private/study-v1/tasks --overlays ../hermes-functional-closeout-private/study-v1/overlays
python -m hermes_skilleval.intervention.functional_closeout configure --assets .. --output ../hermes-functional-closeout-private/study-v1 --encoder /Users/raidriar/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41
python -m hermes_skilleval.intervention.functional_closeout preflight --assets .. --output ../hermes-functional-closeout-private/study-v1
```

有限队列沿用已有12个公开机制候选，稳定ID排序后以20260924 shuffle；实际资格预检限制在前6个。INI首项因资源接线不足及公开范围冲突不可用，其余5项检查有区分能力。按顺序选 identifier、filter forwarding、variable cache、invalid hosts，iterator仅作冻结前备用。四项都是探索性复用，不是新盲测。

可信侧只在新私有副本修复少量公开合同检查：Python 3类型/布尔、旧Jinja后备、hosts交叠拒绝类别与异常后的输入保持。首次新增参数化函数使用未展开选择器，检查被正确判无效；随后按实际收集用例展开并复验。原首轮checks/JUnit保留在qualification，资格通过记录在qualification-v2。首轮在未复制的第7项资源处退出，之后显式限制为已预定的前6项；没有运行修复Agent或依据Agent成败筛题。公共request的环境提示仅将旧units.json改为实际index.json，其余题面不变。

唯一一次旧开发状态关系预演使用 `gpt-5.6-sol / medium`、新空线程，完整获取41.312秒，NO_AFFORDABLE_BATCH终止。预演不生成修复补丁、语义行不预装正式R。代码只将PR55循环提取为显式公开输入函数；R分数、轮转、singleton规则、CostEnvelope和求解器均沿用。

冻结与前缀/组包已执行，固定尾程运行中；可信验收在全部尝试结束后进行。本文件只记录实际执行，不将接线或测试通过写成研究完成。

4个公共前缀和8条逐重复R获取已按初版冻结执行完成；实际成功命令为同入口的 `prefix` 和 `compose`，参数与上方configure相同。没有重抽前缀或R获取。

尾程开始前发现并独立确认计时缺口：初版compose在MethodBudget开始前读取并完整校验checkpoint，原耗时未单独测量。不能用重跑测量替代旧值。保留初版计划于artifacts中的initial-freeze.json及8个锁包摘要，源码身份仍为f8826f1。后续只修尚未开始的24尾程公共准备计时，增加checkpoint校验、输入绑定、token计数及共享auth准备实测费用；不重跑任何关系获取或前缀。原共同准备的未知费用仍影响全部M/R，报告预算为UNKNOWN_PREPARATION_COST，收益终态UNKNOWN，integration PARTIAL；原始功能标签仍由可信验收决定。这是明确的接线与证据限制，不把缺失费用当零，也不自动开启替代研究。

## 实际执行完成与仅读复算

以下各阶段已成功执行一次，`run`为24格固定矩阵，`accept`为24个原候选的可信验收；没有重新采样。执行时以下`python`均指`/opt/anaconda3/bin/python`，并设置`PYTHONPATH=src`。公共前缀/获取绑定f8826f1，尾程与验收绑定c02895d；当前交付仅追加报告、导出及复算脚本。

```sh
encoder_dir=/Users/raidriar/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41
study_dir=../hermes-functional-closeout-private/study-v1
python -m hermes_skilleval.intervention.functional_closeout freeze --assets .. --output "$study_dir" --encoder "$encoder_dir"
python -m hermes_skilleval.intervention.functional_closeout prefix --assets .. --output "$study_dir" --encoder "$encoder_dir"
python -m hermes_skilleval.intervention.functional_closeout compose --assets .. --output "$study_dir" --encoder "$encoder_dir"
python -m hermes_skilleval.intervention.functional_closeout run --assets .. --output "$study_dir" --encoder "$encoder_dir"
python -m hermes_skilleval.intervention.functional_closeout accept --assets .. --output "$study_dir" --encoder "$encoder_dir"
python -m hermes_skilleval.intervention.functional_closeout report --assets .. --output "$study_dir"
python -m hermes_skilleval.intervention.functional_closeout replay --assets .. --output "$study_dir"
python scripts/functional_closeout/export.py --private "$study_dir"
python scripts/functional_closeout/write_report.py --private "$study_dir"
```

上述是完成记录，不是授权重跑采样；原计划状态禁止再次freeze。仅读report/replay零模型调用、零验收调用，前后报告SHA-256均为`1d30a636e0be6af939d71cbb0c37b16f7a772b4a12d7736bc9409089329bc7a0`。

公开资料不包含完整第三方仓库、编码器、原始会话或认证材料。无需私有运行资源即可检查公开补丁摘要、原始JUnit计数、功能标签、等权对比与预算终态：

```sh
PYTHONPATH=src python scripts/functional_closeout/replay_public.py
```

该命令已成功执行，得到N=6 PASS/2 FAIL、M=8 PASS、R=8 PASS；它只证明导出的一致性，不独立重跑候选重建或补回缺失耗时。公开costs.json保留全部已计组件；selection目录保留有限候选、账本、检索、空store独立获取及锁包身份。packages.json按载荷摘要去重，knowledge-behavior.json逐格引用。完整验收只使用冻结overlay，没有后验语义改判，也未需要权限sidecar恢复。
