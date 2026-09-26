# 同经验导航比较结果

16 格真实调用与独立验收全部完成。NATIVE 为 **4 PASS / 4 FAIL / 0 UNKNOWN**，ASSIST 亦为 **4 / 4 / 0**；四个任务全部功能持平，任务等权 `ASSIST − NATIVE = 0`。这不是总体等价、严格非劣或“原生已足够”的证明。

执行版本 `697427ca7859e9ab9f8c9205a0230ffd7a954677`；后续 `07705d4a413453ad9b5b5bfc0ccb8899e9e204d2` 仅补测试入口的非空类型检查与协议说明，冻结研究输入未变。完整条件见 [protocol](protocol.md)，唯一后续决策见 [decision](decision.md)。

## 逐任务结果

| 任务单位 | NATIVE r1/r2 | ASSIST r1/r2 | 差值 | 判定 |
|---|---|---|---:|---|
| asottile__pyupgrade-127 | PASS / PASS | PASS / PASS | 0.0 | 平 |
| asottile__pyupgrade-251 | PASS / PASS | PASS / PASS | 0.0 | 平 |
| encode__httpx-2523 | FAIL / FAIL | FAIL / FAIL | 0.0 | 平 |
| encode__httpx-861 | FAIL / FAIL | FAIL / FAIL | 0.0 | 平 |

独立任务单位为 4，重复不能当作 16 个独立任务。无功能 UNKNOWN；缺失最坏/最好界均为 0，只是代数界，不是置信区间。所有标签均为冻结作者目标与保护检查结果，不能推广为整个项目全部行为正确。

## 表 A：每格功能与完整在线成本

I/O/C 分别为 input/output/cached-input tokens；C 是 I 子集。目录/正文列只指公开显式读取。每格有独立线程、工作副本和完整原补丁。行链接包含原提示、公开事件、实际候选和完整身份；检查链接包含作者标签及 JUnit。

| 原始格 | 结果 | FTP / PTP 通过 | JUnit 总/失败/错/跳过 | 协议 | 在线秒 | I / O / C | 导航秒 | 目录/正文读取 | 回退 |
|---|---|---|---|---|---:|---|---:|---|---|
| [pyupgrade-127-assist-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-127-assist-r1/result.json) | [PASS](../../../artifacts/native-gap-phase2-same-library-v1/checks/asottile__pyupgrade-127-assist-r1/result.json) | 2/2 / 241/241 | 335/0/0/12 | VERIFIED | 99.34 | 193,609 / 3,891 / 163,712 | 3.221 | 否 / 否 | 否 |
| [pyupgrade-127-native-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-127-native-r1/result.json) | [PASS](../../../artifacts/native-gap-phase2-same-library-v1/checks/asottile__pyupgrade-127-native-r1/result.json) | 2/2 / 241/241 | 335/0/0/12 | VERIFIED | 115.57 | 269,094 / 4,593 / 239,232 | 0.000 | 否 / 否 | 否 |
| [pyupgrade-251-assist-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-251-assist-r1/result.json) | [PASS](../../../artifacts/native-gap-phase2-same-library-v1/checks/asottile__pyupgrade-251-assist-r1/result.json) | 1/1 / 41/41 | 72/0/0/0 | VERIFIED | 248.48 | 655,131 / 10,477 / 609,024 | 3.262 | 否 / 否 | 否 |
| [pyupgrade-251-native-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-251-native-r1/result.json) | [PASS](../../../artifacts/native-gap-phase2-same-library-v1/checks/asottile__pyupgrade-251-native-r1/result.json) | 1/1 / 41/41 | 72/0/0/0 | VERIFIED | 149.45 | 498,082 / 5,419 / 470,016 | 0.000 | 否 / 否 | 否 |
| [httpx-861-assist-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-861-assist-r1/result.json) | [FAIL](../../../artifacts/native-gap-phase2-same-library-v1/checks/encode__httpx-861-assist-r1/result.json) | 0/1 / 10/10 | 11/1/0/0 | VERIFIED | 163.29 | 327,787 / 3,148 / 297,344 | 3.047 | 否 / 否 | 否 |
| [httpx-861-native-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-861-native-r1/result.json) | [FAIL](../../../artifacts/native-gap-phase2-same-library-v1/checks/encode__httpx-861-native-r1/result.json) | 0/1 / 10/10 | 11/1/0/0 | VERIFIED | 194.96 | 480,221 / 4,356 / 450,176 | 0.000 | 否 / 否 | 否 |
| [httpx-2523-assist-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-2523-assist-r1/result.json) | [FAIL](../../../artifacts/native-gap-phase2-same-library-v1/checks/encode__httpx-2523-assist-r1/result.json) | 7/8 / 7/7 | 15/1/0/0 | VERIFIED | 440.70 | 1,165,350 / 13,137 / 1,118,464 | 3.662 | 否 / 否 | 否 |
| [httpx-2523-native-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-2523-native-r1/result.json) | [FAIL](../../../artifacts/native-gap-phase2-same-library-v1/checks/encode__httpx-2523-native-r1/result.json) | 7/8 / 7/7 | 15/1/0/0 | VERIFIED | 418.87 | 1,072,979 / 11,420 / 1,023,360 | 0.000 | 否 / 否 | 否 |
| [pyupgrade-127-assist-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-127-assist-r2/result.json) | [PASS](../../../artifacts/native-gap-phase2-same-library-v1/checks/asottile__pyupgrade-127-assist-r2/result.json) | 2/2 / 241/241 | 335/0/0/12 | VERIFIED | 83.71 | 205,930 / 3,144 / 188,672 | 3.174 | 否 / 否 | 否 |
| [pyupgrade-127-native-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-127-native-r2/result.json) | [PASS](../../../artifacts/native-gap-phase2-same-library-v1/checks/asottile__pyupgrade-127-native-r2/result.json) | 2/2 / 241/241 | 335/0/0/12 | VERIFIED | 98.08 | 263,306 / 4,038 / 242,816 | 0.000 | 否 / 否 | 否 |
| [pyupgrade-251-assist-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-251-assist-r2/result.json) | [PASS](../../../artifacts/native-gap-phase2-same-library-v1/checks/asottile__pyupgrade-251-assist-r2/result.json) | 1/1 / 41/41 | 72/0/0/0 | VERIFIED | 106.59 | 323,902 / 3,835 / 297,600 | 3.143 | 否 / 否 | 否 |
| [pyupgrade-251-native-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-251-native-r2/result.json) | [PASS](../../../artifacts/native-gap-phase2-same-library-v1/checks/asottile__pyupgrade-251-native-r2/result.json) | 1/1 / 41/41 | 72/0/0/0 | VERIFIED | 135.57 | 415,388 / 4,422 / 376,192 | 0.000 | 否 / 否 | 否 |
| [httpx-861-assist-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-861-assist-r2/result.json) | [FAIL](../../../artifacts/native-gap-phase2-same-library-v1/checks/encode__httpx-861-assist-r2/result.json) | 0/1 / 10/10 | 11/1/0/0 | VERIFIED | 70.73 | 137,330 / 2,117 / 118,400 | 3.882 | 否 / 否 | 否 |
| [httpx-861-native-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-861-native-r2/result.json) | [FAIL](../../../artifacts/native-gap-phase2-same-library-v1/checks/encode__httpx-861-native-r2/result.json) | 0/1 / 10/10 | 11/1/0/0 | VERIFIED | 69.84 | 167,461 / 2,330 / 138,880 | 0.000 | 否 / 否 | 否 |
| [httpx-2523-native-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-2523-native-r2/result.json) | [FAIL](../../../artifacts/native-gap-phase2-same-library-v1/checks/encode__httpx-2523-native-r2/result.json) | 7/8 / 7/7 | 15/1/0/0 | VERIFIED | 496.41 | 1,319,494 / 11,347 / 1,269,760 | 0.000 | 否 / 否 | 否 |
| [httpx-2523-assist-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-2523-assist-r2/result.json) | [FAIL](../../../artifacts/native-gap-phase2-same-library-v1/checks/encode__httpx-2523-assist-r2/result.json) | 7/8 / 7/7 | 15/1/0/0 | VERIFIED | 766.71 | 2,054,560 / 16,436 / 1,982,720 | 3.852 | 否 / 否 | 否 |

16 格均正常 completed，未触及截止；父监督器 t0 在描述符读取/准备前，t1 包括结束与捕获。逐格协议 VERIFIED 仅指本轮绑定、发现身份、预算与停止检查，不是完整桌面产品认证。pyupgrade-127 的 12 项 skipped 保留原 JUnit 口径；作者去参数化标签数与完整用例数不相加。

| 全部 8 格（含失败） | 在线总秒 / 均值秒 | 输入 token | 输出 token | 缓存输入 token | 总 token | 导航总秒 |
|---|---:|---:|---:|---:|---:|---:|
| NATIVE | 1678.75 / 209.84 | 4,486,025 | 47,925 | 4,210,432 | 4,533,950 | 0.000 |
| ASSIST | 1979.55 / 247.44 | 5,063,599 | 56,185 | 4,775,936 | 5,119,784 | 27.243 |

ASSIST 在本次全部样本合计用时和总 token 均更高；不能据此断言候选提示造成退化。7/8 块 ASSIST 先运行、服务端缓存、样本路径差异和两次重复都限制成本因果解释。两臂都没有观察到目录/正文读取，未建立“减少检索开销”的机制链。没有报告只看成功格的效率收益；金额缺少账单，保持 null。准备成本另见 protocol 与 usage-costs.json。

## 表 B：候选与后续行为

每条候选均使用双方完整目录已有的原名称、原 description、同一逻辑路径；没有分数、答案或强制激活。以下逐格列出原名称；description/path 与实际提示见行链接。正文自动进入初始上下文的可见性在全部 16 格都是 **UNKNOWN**；未见 cat 不等于未使用。未观察到 references 读取或公开的技能适用性采用/拒绝理由，不能把没有读取写成主动拒绝。

| 格 | 原候选名称（均在双方目录） | 正文证据 | 后续代码行为 | 功能 | 至少一个竞争解释 |
|---|---|---|---|---|---|
| [pyupgrade-127-assist-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-127-assist-r1/result.json) | pyupgrade-del-name-context；pyupgrade-invalid-format-fstring；pyupgrade-six-iterator-next | 显式未观察；自动 UNKNOWN | 保留 yield 参数所需括号；四份候选均通过。 | PASS | 任务可直接由局部源码完成；推荐的 del/format/iterator 前提与 yield 括号不同。 |
| [pyupgrade-127-native-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-127-native-r1/result.json) | 无宿主候选；完整目录同样可用 | 显式未观察；自动 UNKNOWN | 保留 yield 参数所需括号；四份候选均通过。 | PASS | 任务可直接由局部源码完成；推荐的 del/format/iterator 前提与 yield 括号不同。 |
| [pyupgrade-251-assist-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-251-assist-r1/result.json) | pyupgrade-invalid-format-fstring；pyupgrade-six-iterator-next；pyupgrade-six-reraise-arity | 显式未观察；自动 UNKNOWN | 在 metaclass 重写时处理 object 基类；两次 r2 生产代码相同。 | PASS | 同仓库 six 主题相似不等于同一前提；边界用例探索与随机执行差异可解释成本。 |
| [pyupgrade-251-native-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-251-native-r1/result.json) | 无宿主候选；完整目录同样可用 | 显式未观察；自动 UNKNOWN | 在 metaclass 重写时处理 object 基类；两次 r2 生产代码相同。 | PASS | 同仓库 six 主题相似不等于同一前提；边界用例探索与随机执行差异可解释成本。 |
| [httpx-861-assist-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-861-assist-r1/result.json) | httpx-line-decoder-performance；pyupgrade-invalid-format-fstring；httpx-redirect-body-headers | 显式未观察；自动 UNKNOWN | 四份生产改动均将 files is not None 改为 files；空 body 仍带 URLencoded headers。 | FAIL | 公开题面强调 body，作者还要求 headers 为空；推荐重定向技能属不同前提，不能归因误用。 |
| [httpx-861-native-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-861-native-r1/result.json) | 无宿主候选；完整目录同样可用 | 显式未观察；自动 UNKNOWN | 四份生产改动均将 files is not None 改为 files；空 body 仍带 URLencoded headers。 | FAIL | 公开题面强调 body，作者还要求 headers 为空；推荐重定向技能属不同前提，不能归因误用。 |
| [httpx-2523-assist-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-2523-assist-r1/result.json) | httpx-valueless-query-params；pyupgrade-invalid-format-fstring；httpx-proxy-certificate-flow | 显式未观察；自动 UNKNOWN | 四份候选均解码 bytes 并扩展 QueryParams；作者要求 TypeError，均未抛出。 | FAIL | 标题支持 bytes 与正文异常预期存在歧义；旧 valueless-key 经验不决定 bytes 输入契约。 |
| [httpx-2523-native-r1](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-2523-native-r1/result.json) | 无宿主候选；完整目录同样可用 | 显式未观察；自动 UNKNOWN | 四份候选均解码 bytes 并扩展 QueryParams；作者要求 TypeError，均未抛出。 | FAIL | 标题支持 bytes 与正文异常预期存在歧义；旧 valueless-key 经验不决定 bytes 输入契约。 |
| [pyupgrade-127-assist-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-127-assist-r2/result.json) | pyupgrade-del-name-context；pyupgrade-invalid-format-fstring；pyupgrade-six-iterator-next | 显式未观察；自动 UNKNOWN | 保留 yield 参数所需括号；四份候选均通过。 | PASS | 任务可直接由局部源码完成；推荐的 del/format/iterator 前提与 yield 括号不同。 |
| [pyupgrade-127-native-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-127-native-r2/result.json) | 无宿主候选；完整目录同样可用 | 显式未观察；自动 UNKNOWN | 保留 yield 参数所需括号；四份候选均通过。 | PASS | 任务可直接由局部源码完成；推荐的 del/format/iterator 前提与 yield 括号不同。 |
| [pyupgrade-251-assist-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-251-assist-r2/result.json) | pyupgrade-invalid-format-fstring；pyupgrade-six-iterator-next；pyupgrade-six-reraise-arity | 显式未观察；自动 UNKNOWN | 在 metaclass 重写时处理 object 基类；两次 r2 生产代码相同。 | PASS | 同仓库 six 主题相似不等于同一前提；边界用例探索与随机执行差异可解释成本。 |
| [pyupgrade-251-native-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/asottile__pyupgrade-251-native-r2/result.json) | 无宿主候选；完整目录同样可用 | 显式未观察；自动 UNKNOWN | 在 metaclass 重写时处理 object 基类；两次 r2 生产代码相同。 | PASS | 同仓库 six 主题相似不等于同一前提；边界用例探索与随机执行差异可解释成本。 |
| [httpx-861-assist-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-861-assist-r2/result.json) | httpx-line-decoder-performance；pyupgrade-invalid-format-fstring；httpx-redirect-body-headers | 显式未观察；自动 UNKNOWN | 四份生产改动均将 files is not None 改为 files；空 body 仍带 URLencoded headers。 | FAIL | 公开题面强调 body，作者还要求 headers 为空；推荐重定向技能属不同前提，不能归因误用。 |
| [httpx-861-native-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-861-native-r2/result.json) | 无宿主候选；完整目录同样可用 | 显式未观察；自动 UNKNOWN | 四份生产改动均将 files is not None 改为 files；空 body 仍带 URLencoded headers。 | FAIL | 公开题面强调 body，作者还要求 headers 为空；推荐重定向技能属不同前提，不能归因误用。 |
| [httpx-2523-native-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-2523-native-r2/result.json) | 无宿主候选；完整目录同样可用 | 显式未观察；自动 UNKNOWN | 四份候选均解码 bytes 并扩展 QueryParams；作者要求 TypeError，均未抛出。 | FAIL | 标题支持 bytes 与正文异常预期存在歧义；旧 valueless-key 经验不决定 bytes 输入契约。 |
| [httpx-2523-assist-r2](../../../artifacts/native-gap-phase2-same-library-v1/runs/encode__httpx-2523-assist-r2/result.json) | httpx-valueless-query-params；pyupgrade-invalid-format-fstring；httpx-proxy-certificate-flow | 显式未观察；自动 UNKNOWN | 四份候选均解码 bytes 并扩展 QueryParams；作者要求 TypeError，均未抛出。 | FAIL | 标题支持 bytes 与正文异常预期存在歧义；旧 valueless-key 经验不决定 bytes 输入契约。 |

## 三个保存记录案例

### 1. pyupgrade-127：无显式经验读取，也可完成当前局部任务

四份候选均在 `_fix_extraneous_parens` 保留 yield 表达式必需的括号，通过 2/2 作者目标、241/241 保护标签。ASSIST r1 和 NATIVE r2 的生产改动相同。第一候选 `pyupgrade-del-name-context` 源自 pyupgrade-308，正文前提为 `ast.Del` 与 `FindPy3Plus.visit_Name`；本题是 yield 调用参数的 token 括号。两者同属 pyupgrade 不能证明经验转移。未观察到显式正文读取或公开采用理由，也没有功能差值；局部源码足够是竞争解释，不判漏召回。

### 2. HTTPX-861：同一生产改动，没有满足作者 header 边界

四份候选的生产改动完全相同：`if files is not None` → `if files`。公开自测验证了空 body，但作者 `test_empty_request` 还断言 `stream.get_headers() == {}`；四格均留下 `Content-Length: 0` 和 form Content-Type，目标 0/1、保护 10/10。候选中的 `httpx-redirect-body-headers` 源自 HTTPX-310，确实要求检查 method 与 headers，但前提是 POST→GET 重定向，而本题没有重定向。它是一个事后可理解的类比，不是已观察到的使用或足以修复此题的覆盖证据。保留 FAIL，不将“读技能本可救回”当事实。

### 3. HTTPX-2523：公开需求歧义与更高成本，没有导航因果证据

标题是 “Support passing bytes keys/values in `params=...`”，正文又说预期应抛异常；冻结作者检查要求 `QueryParams({"a": b"bytes"})` 抛出 TypeError。四份候选均实现 bytes 解码/编码支持，因此作者目标 7/8、保护 7/7，冻结结果均 FAIL。ASSIST r2 进一步处理非 UTF-8 bytes 和类型边界，耗时 766.71 秒；NATIVE r2 496.41 秒，但两者都未满足异常契约。推荐的 `httpx-valueless-query-params` 源自 HTTPX-2354，关注 `keep_blank_values=True` 与无值键保留，不决定 bytes 值应支持还是拒绝。不得把主题相近、成本较高或模型公开自述单独当作误用、路由损害或原生推理缺陷。

本轮不改作者检查、不重标胜例、不追加诊断修复。具体源正文、候选改动与公开事件定位见 [case-evidence.json](../../../artifacts/native-gap-phase2-same-library-v1/case-evidence.json)。没有观测到导航功能获胜或功能退化，故不编造这两类案例。
