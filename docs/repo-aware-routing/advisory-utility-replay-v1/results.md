# 冻结检查的原始对照与成本

范围：`EXPLORATORY_REPLAY_ON_SEEN_TASKS`；四个独立任务，32 次计划调用。每任务每臂两次。成功仅指固定目标检查与基本回归通过，不是完整上游回归。

| 臂 | 固定检查通过 | 固定检查失败 | 策略拒绝 | 超时未成功 | 未知 | 未运行 |
|---|---:|---:|---:|---:|---:|---:|
| N | 5 | 3 | 0 | 0 | 0 | 0 |
| F2 | 6 | 2 | 0 | 0 | 0 | 0 |
| T2 | 6 | 2 | 0 | 0 | 0 | 0 |
| J2 | 6 | 2 | 0 | 0 | 0 | 0 |

| 任务 | N 均值 | F2 均值 | T2 均值 | J2 均值 | J2 对 N / F2 / T2 |
|---|---:|---:|---:|---:|---|
| sqlite-utils-issue-344 | 1.0 | 1.0 | 1.0 | 1.0 | TIE / TIE / TIE |
| sqlite-utils-issue-400 | 1.0 | 1.0 | 1.0 | 1.0 | TIE / TIE / TIE |
| sqlite-utils-issue-368 | 0.0 | 0.0 | 0.0 | 0.0 | TIE / TIE / TIE |
| csvkit-issue-1225 | 0.5 | 1.0 | 1.0 | 1.0 | WIN / TIE / TIE |

| 比较 | 任务级胜 / 负 / 平 / 未知 |
|---|---|
| J2 vs N | 1 / 0 / 3 / 0 |
| J2 vs F2 | 0 / 0 / 4 / 0 |
| J2 vs T2 | 0 / 0 / 4 / 0 |

#368 标注 `REQUEST_ENTRYPOINT_AMBIGUITY`：公开标题要求 package 入口，正文示例要求 cli 子模块；冻结检查采用标题。因此相关胜负仅是固定检查差异，不代表无歧义的请求正确性。详见 [method](method.md) 和 [task-limitations](../../../artifacts/advisory-utility-replay-v1/task-limitations.json)。

csvkit 标注 `OVER_SPECIFIC_ORACLE_FILENAME`：N 第二次命令正常退出并生成 `-_0.csv`，但冻结检查要求 `stdin_*.csv`，而公开 in2csv 合同未规定这一前缀。保留原始 WIN/FAIL，不改判或删格；唯一 J2/N 表面胜负不能证明修复收益。最终 `utility=INCONCLUSIVE`，保持 `KEEP_NATIVE`。

## 全部计划记录

| 任务 | 臂 | 重复 | 结果 | Agent 秒 | 完整补丁 |
|---|---|---:|---|---:|---|
| sqlite-utils-issue-344 | J2 | 1 | SUCCESS | 359.30 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-344-J2-r1.patch) |
| sqlite-utils-issue-344 | N | 1 | SUCCESS | 321.49 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-344-N-r1.patch) |
| sqlite-utils-issue-344 | T2 | 1 | SUCCESS | 311.81 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-344-T2-r1.patch) |
| sqlite-utils-issue-344 | F2 | 1 | SUCCESS | 339.77 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-344-F2-r1.patch) |
| sqlite-utils-issue-344 | J2 | 2 | SUCCESS | 245.73 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-344-J2-r2.patch) |
| sqlite-utils-issue-344 | N | 2 | SUCCESS | 538.45 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-344-N-r2.patch) |
| sqlite-utils-issue-344 | T2 | 2 | SUCCESS | 334.66 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-344-T2-r2.patch) |
| sqlite-utils-issue-344 | F2 | 2 | SUCCESS | 296.74 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-344-F2-r2.patch) |
| sqlite-utils-issue-400 | J2 | 1 | SUCCESS | 94.95 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-400-J2-r1.patch) |
| sqlite-utils-issue-400 | T2 | 1 | SUCCESS | 108.93 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-400-T2-r1.patch) |
| sqlite-utils-issue-400 | N | 1 | SUCCESS | 148.38 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-400-N-r1.patch) |
| sqlite-utils-issue-400 | F2 | 1 | SUCCESS | 105.23 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-400-F2-r1.patch) |
| sqlite-utils-issue-400 | N | 2 | SUCCESS | 108.09 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-400-N-r2.patch) |
| sqlite-utils-issue-400 | F2 | 2 | SUCCESS | 82.49 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-400-F2-r2.patch) |
| sqlite-utils-issue-400 | J2 | 2 | SUCCESS | 97.35 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-400-J2-r2.patch) |
| sqlite-utils-issue-400 | T2 | 2 | SUCCESS | 126.81 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-400-T2-r2.patch) |
| sqlite-utils-issue-368 | T2 | 1 | FUNCTIONAL_FAILURE | 85.52 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-368-T2-r1.patch) |
| sqlite-utils-issue-368 | F2 | 1 | FUNCTIONAL_FAILURE | 60.36 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-368-F2-r1.patch) |
| sqlite-utils-issue-368 | N | 1 | FUNCTIONAL_FAILURE | 83.05 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-368-N-r1.patch) |
| sqlite-utils-issue-368 | J2 | 1 | FUNCTIONAL_FAILURE | 60.94 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-368-J2-r1.patch) |
| sqlite-utils-issue-368 | F2 | 2 | FUNCTIONAL_FAILURE | 77.06 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-368-F2-r2.patch) |
| sqlite-utils-issue-368 | N | 2 | FUNCTIONAL_FAILURE | 95.72 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-368-N-r2.patch) |
| sqlite-utils-issue-368 | J2 | 2 | FUNCTIONAL_FAILURE | 73.36 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-368-J2-r2.patch) |
| sqlite-utils-issue-368 | T2 | 2 | FUNCTIONAL_FAILURE | 95.41 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-sqlite-utils-issue-368-T2-r2.patch) |
| csvkit-issue-1225 | T2 | 1 | SUCCESS | 127.28 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-csvkit-issue-1225-T2-r1.patch) |
| csvkit-issue-1225 | J2 | 1 | SUCCESS | 187.99 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-csvkit-issue-1225-J2-r1.patch) |
| csvkit-issue-1225 | N | 1 | SUCCESS | 198.63 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-csvkit-issue-1225-N-r1.patch) |
| csvkit-issue-1225 | F2 | 1 | SUCCESS | 139.02 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-csvkit-issue-1225-F2-r1.patch) |
| csvkit-issue-1225 | F2 | 2 | SUCCESS | 146.92 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-csvkit-issue-1225-F2-r2.patch) |
| csvkit-issue-1225 | J2 | 2 | SUCCESS | 153.25 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-csvkit-issue-1225-J2-r2.patch) |
| csvkit-issue-1225 | T2 | 2 | SUCCESS | 155.71 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-csvkit-issue-1225-T2-r2.patch) |
| csvkit-issue-1225 | N | 2 | FUNCTIONAL_FAILURE | 225.12 | [patch](../../../artifacts/advisory-utility-replay-v1/patches/advisory-csvkit-issue-1225-N-r2.patch) |



## 包选择与读取

N 对四任务提供相同完整十技能目录；其余如下。这里列分数排序，实际挂载采用冻结 registry 顺序，最终 CLI 元数据排序未独立捕获。

| 任务 | F2 | T2 | J2 |
|---|---|---|---|
| sqlite-utils-issue-344 | sqlite-ingest, sqlite-fulltext | systematic-debugging, verification-before-completion | sqlite-schema, tabular-conversion |
| sqlite-utils-issue-400 | sqlite-ingest, sqlite-fulltext | systematic-debugging, verification-before-completion | sqlite-schema, sqlite-fulltext |
| sqlite-utils-issue-368 | sqlite-ingest, sqlite-fulltext | systematic-debugging, verification-before-completion | sqlite-schema, systematic-debugging |
| csvkit-issue-1225 | tabular-conversion, csv-dialect | systematic-debugging, verification-before-completion | tabular-conversion, systematic-debugging |

J2/T2 集合相同率：0/4。

J2/F2 集合相同率：0/4。

T2/F2 集合相同率：0/4。

任务×臂推荐记录 fallback：0/16。

| 臂 | 至少一次可验证正文读取的运行 | 未见此强度证据的运行 |
|---|---:|---:|
| N | 2/8 | 6/8 |
| F2 | 0/8 | 8/8 |
| T2 | 3/8 | 5/8 |
| J2 | 2/8 | 6/8 |

未知不等于没有使用。复合命令、无法核对正文的读取线索保留为 `read_candidate_unknown`；不把挂载或读取等同于因果贡献。六个 CLI 内置系统技能构成共同背景，其正文路径不可由工具读取，元数据可见性未独立捕获。

## 成本

供应方 input 包含 cached input；两列分别展示，不相加。Dollar 未知。下表 Agent 秒为各次执行之和，不是用户端墙钟。

| 臂 | input | cached input | output | Agent 秒合计 | 包/源码准备秒 | 外部验证秒 | post-Agent 区间秒 |
|---|---:|---:|---:|---:|---:|---:|---:|
| N | 8098998 | 7657600 | 60070 | 1718.941 | 0.198 | 25.227 | 28.646 |
| F2 | 5944258 | 5587712 | 47084 | 1247.593 | 0.149 | 25.258 | 28.410 |
| T2 | 5263496 | 4890880 | 45570 | 1346.118 | 0.149 | 25.270 | 28.490 |
| J2 | 5918317 | 5574784 | 46723 | 1272.877 | 0.141 | 25.268 | 28.452 |

共享 J 模型加载 3.072 秒；四任务合计建议计算阶段 52.774 秒（40 次 forward、40 候选对、80 轴输出，包含少量 T/记录处理）。T 独立计算时间未单独计时，记未知。两次重复复用同一建议，不重复计算或收费；本轮没有在线每请求延迟实测。

四任务资格准备累计 25.460 秒，作为共享准备成本。环境恢复/构建与公共上下文处理未取得完整独立墙钟计时，记未知；不虚构总账。

post-Agent 区间由文件时间戳推导，涵盖归档、捕获、重建与检查，已经包含 verification，不能再次相加。包准备使用执行器原计时口径，包含源码/工作目录准备。开发成本不属于算法在线成本。

完整原始 trace 保留本地，公开 patch、JUnit、身份与必要脱敏读取片段。零模型重算核对公开证据，不重跑模型，也不证明对恶意候选的密码学裁判隔离。

另有 1 次非研究 transport smoke：15.488 秒，input 36,045（其中 cached 27,776）、output 204；它不在 32 次矩阵内，不计入任何臂。干净安装的资格复验和末次候选命名诊断均为零 Agent 调用的工程验证，未改写主表。共享环境准备与全部工程开销没有完整独立计时，不能把已知分项之和称为完整在线总成本。


Posthoc appendix: [acceptance semantics and original-patch revalidation](../acceptance-semantics-v1/review-index.md). Original data and scores above are unchanged.
