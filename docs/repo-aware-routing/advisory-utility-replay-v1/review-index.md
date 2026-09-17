# 建议模式：已观察任务的真实修复回放

**32/32 次真实隔离执行完成；效用 `INCONCLUSIVE`，保留 `KEEP_NATIVE`。** 这不是新的独立盲测，也不是高置信 C2 通过。冻结 J 第 3 个 checkpoint 真实评分后提供 Top-2，与原生十包、旧固定两包、冻结便宜文本两包比较；本轮没有训练。

| 原始固定检查 | N | F2 | T2 | J2 |
|---|---:|---:|---:|---:|
| 通过 / 计划 | 5/8 | 6/8 | 6/8 | 6/8 |
| 失败 | 3 | 2 | 2 | 2 |
| 超时 / 未知 / 未运行 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

这些不是无歧义的真实修复成功率。#368 标题要求包入口，正文示例却要求 CLI 子模块；八份补丁均实现正文，但未通过标题对应检查。csvkit 最后一次 N 正常退出并生成 `-_0.csv`，却因固定检查额外要求 `stdin_*.csv` 被拒绝；未找到该命令必须使用此命名的公开合同。**J2 对 N 的原始 1 胜 3 平恰好来自这一过窄验收，不能晋升为修复收益。** J2 对 T2、F2 均为四任务全平。全部原始结果保留，不重跑、不改判、不删除任务。

审阅顺序：

1. [一页中文复盘](retrospective.zh.md)与[完整结果、选择、读取、成本](results.md)。
2. [冻结方法与限制](method.md)、[协议](../../../configs/advisory-utility-replay-v1/protocol.json)、[环境恢复](../../../artifacts/advisory-utility-replay-v1/environment.json)。
3. [资格与实际检查身份](../../../artifacts/advisory-utility-replay-v1/qualification.json)、[原始检查文本](../../../artifacts/advisory-utility-replay-v1/checks-source)、[全部运行](../../../artifacts/advisory-utility-replay-v1/runs.json)。
4. [完整成功补丁例子](patch-example.md)、[32 份独立补丁复核](../../../artifacts/advisory-utility-replay-v1/patch-review.json)、[命名问题的单独诊断](../../../artifacts/advisory-utility-replay-v1/filename-diagnostic.json)。
5. [安装、恢复和零模型重算命令](usage.md)、[重算结果](../../../artifacts/advisory-utility-replay-v1/records.json)、[本地验证](../../../artifacts/advisory-utility-replay-v1/local-validation.json)。

每任务实际只有 1 个目标 + 1 个基础回归，不是全仓回归。参考与裁判未提供给修复 Agent；候选在新的干净 base 重建后验证。32 份补丁均经独立只读复核，未发现裁判/报告干扰，但不宣称对恶意候选的密码学隔离。读取痕迹只证明观察到的阅读，不证明因果贡献。共享主机与服务端负载未受控，token/时间差异不等于线上账单节省。

本地完整测试 **1416 passed**；仓库外干净 wheel 的 prepare、records、summarize、恢复跳过通过；旧 120/40 记录均零模型 `MATCHED`。精确最终 HEAD 的 CI 从同一 [Draft PR #48](https://github.com/Raidriar7170/hermes-skilleval/pull/48) 与交付消息核对，本地检查不替代它。没有合并、ready、归档或发布。

状态：`EXPLORATORY_REPLAY_ON_SEEN_TASKS` / `VERIFIED_FOR_SCOPE` / `runtime_comparison=COMPLETED`（冻结检查范围）/ `advisory_package_exposure=VERIFIED` / `utility=INCONCLUSIVE` / `support_certification=NOT_CLAIMED` / `KEEP_NATIVE`。旧实验记录与结论原样保留。
