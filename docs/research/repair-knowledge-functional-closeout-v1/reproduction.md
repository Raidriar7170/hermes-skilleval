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

正式冻结、前缀、尾程与验收尚待执行。本文件只追加实际完成命令，不将接线或测试通过写成研究完成。
