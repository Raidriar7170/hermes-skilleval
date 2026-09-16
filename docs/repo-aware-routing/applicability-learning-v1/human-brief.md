# Human Brief：PR #48 条件适用性学习

本轮已经完成 24 个公开需求、10 项完整技能、240 行双轴弱标签，两个真实独立支持 LoRA 候选、六个 checkpoint 的新进程重载，以及冻结后的 cal/check。所有重载误差为 0。没有覆盖旧 rank、Gate 或历史实验。

结论是限定负结果：`data=READY`、`pointwise_training=TRAINED_AND_RELOADED`、`text_discrimination=NO_DEMONSTRATED_GAIN`、`supported_operating_point=NOT_ESTABLISHED`、`runtime=NOT_RUN`。相对冻结底座，原始 Brier 从 0.2503 降至 0.0961；但技能先验是 0.0900，便宜文本模型是 0.0688。校准后为 0.0692，数值接近不能证明等价；新模型特定 P@2 为 0.125，Fixed 为 0.375。

cal 只有两个上下文可用组，低于冻结的三个组要求；特异性也只有两个已知正例，未拟合该轴校准。因此阈值为 null，预选两个任务的六个修复执行单元全部 NOT_EXECUTED，没有再跑全回退 smoke。不能声称支持分支、补丁收益、默认策略升级或发布就绪。

只有四个 check 机制组，标签来自同一配置模型的两个独立上下文，未人工审核。技能名/文本先验、项目/格式词捷径和共同标注偏误没有被排除。原 rank 过滤与新 priority 排序分开；无特定正例任务未从全任务 P@2 分母移除。

独立只读复核重算了 40 行 records，核对六个 checkpoint 身份、重载、主要数字和声明边界，未发现 material 问题。它没有重新训练模型，也不认证弱标签语义。干净 wheel 的轻量 records 和仓库外真实模型推理均已运行。

先读 [结果](results.md) 与 [usage](usage.md)。发布证据以 [Draft PR #48](https://github.com/Raidriar7170/hermes-skilleval/pull/48) 当前 HEAD 的实际检查和最终交付记录为准；保持 Draft，不 merge、不 ready、不发布权重。
