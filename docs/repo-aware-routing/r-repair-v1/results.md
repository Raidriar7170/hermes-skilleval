# R 支持与上下文修正：开发交付

**PARTIAL / DATA_SIGNAL_INSUFFICIENT / FALLBACK_ONLY / INCONCLUSIVE**。默认仍是 native；旧 pilot、Gate、模型与结果不改写。本轮修复了输入与评分接口，但没有验证有效的受支持 C2 分支，不具备晋升或 Gate 采集依据。

旧链路实际诊断有 45 条逐需求记录，支持指令前缀均未进入最终输入；sqlite-utils 大文件还被预算直接跳过。新链路使用独立扫描/片段预算及结构化 token 分段，恢复了 `delete_where` 的源码事实。非关键窗口不完整仍明确披露；关键覆盖不足按 partial 拒绝。详见 [诊断](diagnosis.md)。

两个独立模型上下文标注 100 条自然任务—技能记录：75 SUPPORTED、13 NOT_APPLICABLE、12 UNKNOWN（含 9 条分歧），没有自然 CONTRADICTED。引用已逐字核验，仍非人审真值。20 个任务按机制合并为 16 组：fit 10 任务/7 组、cal 6/5、check 4/4，均为已观察开发材料。整题是一个复合需求，支持某一步不等于技能足以修复整题。

真实独立支持输入与固定 base scorer 在冻结后评分，排序仍使用原 pairwise adapter。校准参数 `a=0.43083028403563833, b=3.1179371779909686` 已真实拟合并重载一致；阈值为 null。折外阈值覆盖至少两正例族时最高精度 0.8875，未达到预先固定的 0.90。fit 只有五条已知负例、三组，没有足够自然反例支持额外 LoRA。保留无效 editable-import 尝试，不把它算作 base 对照。详见 [拟合决定](support-fit-decision.md)。

表 A：输入与支持（每族五份完整技能；阈值均为 null）。

| 开发检查族 | 关键上下文/全部引用可见 | 正/负/未知 | 接受/错收/漏收 |
|---|---|---|---|
| content-key | usable / 5/5 | 3/1/1 | 0/0/3 |
| delete-transaction | usable / 5/5 | 4/1/0 | 0/0/4 |
| dotted-columns | usable / 5/5 | 3/1/1 | 0/0/3 |
| migration-stop-validation | usable / 5/5 | 4/1/0 | 0/0/4 |

检查总接受 0/20，已知正例召回 0/14，精度未定义，UNKNOWN 接受 0/2。Brier 0.175842，常量基线 0.174375；log-loss 0.544878。18 条已知标签预测均在 0.8–1.0 桶，均值 0.861632、实际正例占比 0.777778。没有可靠校准或高精度覆盖结论；无接受样本不能给出有意义的接受精度区间。按族/技能详细分母见 [可重算结果](../../../artifacts/repo-aware-routing-r-repair-v1/results.json)。旧链路与新支持的目标不同，旧 45 行不能直接与新 20 行拼成准确率提升。

表 B：完整尝试与选择。原计划四族×三条件共 12 格；支持前提失败后、Agent 结果出现前仅保留首个预定族作安装 smoke，另九格记录未执行，不能宣称完成主比较。

| 尝试 | 请求→实际 | 选中/完整物化 | 读取命令观测 | 独立重建与目标/回归 |
|---|---|---|---|---|
| delete-transaction N 002 | native→N | 5: systematic-debugging, verification-before-completion, cli-api-regression, schema-change-regression, import-data-regression | schema-change-regression, systematic-debugging, verification-before-completion | 重建通过；目标 1/1、回归 2/2 |
| delete-transaction B2 002 | repo-aware→R | 2: import-data-regression, cli-api-regression | cli-api-regression | 重建通过；目标 1/1、回归 2/2 |
| delete-transaction C2 002 | repo-aware→N | 5: systematic-debugging, verification-before-completion, cli-api-regression, schema-change-regression, import-data-regression | schema-change-regression, systematic-debugging, verification-before-completion | 重建通过；目标 1/1、回归 2/2 |
| N/B2/C2 各 001 | 启动前拒绝 | 未启动 Agent | 无 | workspace parent skill leakage；三条 UNKNOWN 保留 |
| 其他三族×三条件 | NOT_EXECUTED | 无 | 无 | NO_VALID_SUPPORT_OPERATING_POINT，九格未执行 |

C2 评分后因 `no_valid_operating_point` 回退 N，实际暴露五技能，不是严格 K=2 样本。B2 两个完整包与 N+/C2 暴露不同，读取记录只是命令观测，不证明认知使用或因果帮助。三份完整候选 patch 均在独立干净基线上重建并通过既定检查；同一族、每臂一次，全通过不构成非劣、等价或收益证据。原始第一次拒绝发生于启动前；迁移到隔离临时工作区没有观察成功结果后按臂加跑。

表 C：已测成本，单位秒。rank/support/预测/选择目前合并计时，未分别测到的字段为 null；不估算美元。

| 条件 | 上下文 | 检索 | rank+support+选择 | 路由总计 | Agent | 捕获/重建检查收尾 | 输入/缓存子集/输出 token |
|---|---:|---:|---:|---:|---:|---:|---|
| N | 0.092 | 0.000 | 0.000 | 0.092 | 158.148 | 0.260/4.822 | 572658/539648/5597 |
| B2 | 0.091 | 0.553 | 1.893 | 5.155 | 106.353 | 0.377/5.677 | 270690/248576/3508 |
| C2 | 0.091 | 0.525 | 5.068 | 8.288 | 102.250 | 0.390/5.392 | 398279/361984/3337 |

N+/B2/C2 的 heavy constructors 为 0/2/3，encoder query 为 0/1/1，rank+support forward 为 0/5/10；C2 回退前的计算没有归零。支持 cal 30+30 forwards 用时 22.879 秒，check 20+20 用时 14.921 秒（循环含上下文与 rank/support，不含构造/加载）。各候选单条计时保留；未测 batch、冷暖配对速度差，不主张性能优势。token 总量按 input+output，缓存是输入子集，reasoning 不额外累加。

验证：本地完整 1315 测试通过；OpenSpec 37 通过。仓库外干净 wheel 106 个 runtime 文件逐字匹配，help/support help、旧 records、无 Torch/Transformers/PEFT 的 native/fixed/auto 零重模型、校准重载和身份拒绝通过。上述三条真实执行使用仓库外安装 wheel 与另配模型依赖。旧 Gate 对新 R 明确版本不匹配。scratch 是每次执行独立 128MiB tmpfs；真实 canary 验证可写、网络关闭、凭据拒绝、兄弟目录不可见。

同 HEAD CI 以 [PR48 检查页](https://github.com/Raidriar7170/hermes-skilleval/pull/48/checks)为准；本页不拿旧 HEAD CI 代替新结果。交付保留 Draft、不合并、不发布。源码身份及完整 patch/JUnit 在新 records 内；旧研究保持原结论。下一步需要覆盖更多真实不适用/冲突机制的独立标签，并在冻结规则下证明非空受支持分支后才考虑 Gate 采集；本轮不执行。

入口：[使用与重算](usage.md) · [个人复盘](retrospective.md) · [原始校准](../../../artifacts/repo-aware-routing-r-repair-v1/calibration.json)。
