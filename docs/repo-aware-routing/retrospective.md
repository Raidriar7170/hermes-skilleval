# 一页复盘：一次正确回退，而非路由增益

案例：`sqlite-utils-delete-transaction`。来源是本轮冻结后实际运行的 N、R、H 三条记录，见[结构化案例](../../artifacts/repo-aware-routing/case-study.json)。

## 1. 问题与仓库事实

请求涉及删除后事务持久化。仅凭请求文本，无法确定事务由表方法、数据库执行层还是调用者负责。静态提取确实从 `pyproject.toml:72` 取得 `sqlite-utils → sqlite_utils.cli:cli` 的入口事实，并保存源文件 SHA。

但真正要修改的 `sqlite_utils/db.py` 超过单文件读取预算，被标为 `byte_budget`；上下文因此是 **unsupported/incomplete**。本次提取没有找到核心事务实现，不能把“提取到了入口”说成理解了故障。

## 2. 训练模型与集合决策

R 实际加载本轮训练的 0.6B LoRA checkpoint 并打分。五个候选整体 logits 约为 −3.63 到 −2.96；逐需求支持未达到冻结阈值，全部保留 UNKNOWN。优化器实际返回空集，然后回退原生完整技能池。

这暴露了方法限制：八个文本相对偏好不足以证明绝对支持分已校准。优化器遵守了它的代理目标，但这次没有产生有用的技能子集。

## 3. Gate 与实际执行

H 在 Agent 启动前读取已封存 gate。它因上下文不完整选择 N，重模型构造、encoder 查询、reranker forward 均为 **0**。拟合集也没有族内动作质量差异，gate 的总体信号为 INSUFFICIENT，不能声称学会了何时需要 R。

Agent 随后读取实际源码，生成[真实补丁](../../artifacts/repo-aware-routing/final-test/final-sqlite-utils-delete-transaction-auto-001/candidate.patch)：把删除及可选分析纳入 `self.db.atomic()`，并增加关闭、重新打开数据库后检查删除持久化的测试。补丁被独立重建，限定目标与回归检查通过。Agent 自写测试没有替代控制器验收。

## 4. 简单方案与失败边界

单独 N 也通过这个任务。N、R、H 的这次结果都是成功；R 最终仍开放原生技能池，不能归因于新选择算法。三次耗时不同只是单次观测，不构成延迟收益。

本轮可交代的贡献是：真实训练与重载、可追溯上下文、精确预算集合接口、前置 gate、实际补丁闭环及独立重算。明确失败点是核心文件预算遗漏、支持信号不足和 gate 无动作区分信号。结论与完整四族五臂统计见[结果](results.md)；继续保留 native 默认，不自动晋升或扩展算法层。
