# 第二阶段决策

**本范围未建立额外候选导航的功能收益，暂不训练通用 Router，默认策略保持不变。** 两臂各 4/8 PASS、4/8 FAIL；四个任务功能全部持平，任务等权差值 0。ASSIST 全部八格总用时与 token 更高，但小样本、顺序不平衡及路径差异不支持因果成本结论。

唯一保留的下一研究问题是：**如何在不读取目标答案的前提下，确认历史经验覆盖了当前任务所需的输入/输出契约，而不仅是主题相似？** 这只是待规划的内容覆盖问题，不自动启动新实验、扩库、oracle 提示或训练。

12 条技能来自 12 个独立问题、两个仓库各六条；同库不保证本题必有适用经验。16 格没有观察到 catalog、正文或 references 的显式读取，自动正文上下文为 UNKNOWN。不能由此判漏召回或宣称经验毫无作用。系统资源只读接线已修复，也不构成排序算法创新。

HTTPX-2523 的公开标题与正文对 bytes 输入契约存在歧义，作者选择 TypeError，而四份候选选择支持 bytes。主表保持冻结作者 FAIL；这不是已证明的技能适用性、路由或推理能力缺陷。HTTPX-861 是空 body 与作者 header 边界的差异。两项都不能用目标自测通过代替可信验收。

## 人工审阅摘要

- 固定规模实际完成：已有 30 源问题池，12 条/12 源组，4 批初始转换，4 个新任务，2 次无害模型预演，16 次真实修复；3 次权限 canary 不调用模型。
- 所有 16 格正常结束、在预算内、原候选已捕获；全部独立重建并验收，8 PASS / 8 FAIL / 0 UNKNOWN。未替换失败，未追加修复。
- 两臂完整资产相同，记忆使用/生成关闭，8 次 ASSIST 无回退；真实 MiniLM 元数据 MMR 未训练参数。完整新在线成本有父监督器记录；镜像传输字节仍 UNKNOWN，金额 null。
- 4 个任务不是 16 个独立任务；固定顺序 7/8 块 ASSIST 在先。离线网络、预装镜像、Apple Silicon 上 amd64 仿真、有限库与非时序数据都限制外推；不代表完整长期记忆桌面产品。
- 独立只读模型 Reviewer 已核对导出证据、候选身份、冻结资产、作者解析/JUnit 和隐私边界；文档与最终 SHA/CI 收口另以交付记录为准，模型审阅不是人工 gold。

```yaml
stage: native-gap-phase2-same-library-v1
implementation: COMPLETE
native_system_skill_access: VERIFIED
same_library_identity: VERIFIED
memory_scope: SKILLS_ONLY_NO_GENERATION_NO_USE
source_issue_count: 30
library_skill_count: 12
library_source_groups: 12
pilot_task_count: 4
repair_runs_planned: 16
repair_runs_started: 16
trusted_functional_results: 16
comparison: COMPLETE
full_online_cost: VERIFIED_FOR_NEW_RUNS
same_library_navigation_signal: NOT_ESTABLISHED
primary_gap_hypothesis: CONTENT  # post-hoc coverage question, not demonstrated causal gap
new_learned_algorithm_advantage: NOT_TESTED
new_training: NONE
default_policy: UNCHANGED
publication: DRAFT_PR_ONLY
next_automatic_experiment: NONE
```

[协议与实际命令](protocol.md) · [完整结果与案例](results.md) · [Draft PR #58](https://github.com/Raidriar7170/hermes-skilleval/pull/58)。停在 Draft，不合并、不 ready、不发布。
