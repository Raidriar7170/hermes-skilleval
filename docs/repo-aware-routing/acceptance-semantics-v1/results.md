# 原判分与后验行为对照

**32份旧记录已核对、16份原候选已重新执行。** 原始补丁及旧记录保持原字节；全部16份的旧目标/回归检查均复现一致。另16份（#344、#400）本轮没有重验。

分析范围：`POSTHOC_REVALIDATION_OF_FROZEN_PATCHES`。没有新增独立效果实验，不能汇总为四任务的新修复率。

## 表一：原始32格（原定义）

| 任务 | N r1 | N r2 | F2 r1 | F2 r2 | T2 r1 | T2 r2 | J2 r1 | J2 r2 |
|---|---|---|---|---|---|---|---|---|
| csvkit-issue-1225 | PASS | FAIL | PASS | PASS | PASS | PASS | PASS | PASS |
| sqlite-utils-issue-368 | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| sqlite-utils-issue-344 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| sqlite-utils-issue-400 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

原定义合计：N 5/8，F2/T2/J2 各6/8。CSV 前缀限制没有公开依据；#368 原检查只覆盖标题对应的包入口。原结果保留，解释范围予以勘误。

## 表二：16份原候选行为

CSV：内容列同时要求真实退出0、精确CSV解析内容和完整工作表多重集；stdout默认工作表单独解析后参与判断。文件回归为原夹具/新增夹具默认表输出。

| 原候选 | 原目标/回归 | 旧检查复现 | 原夹具内容 | 新多表内容 | 文件回归（原/新） | 原因 |
|---|---|---|---|---|---|---|
| F2 r1 | PASS/PASS | MATCHED | PASS | PASS | PASS/PASS | 内容完整，旧定义与新维度均通过 |
| F2 r2 | PASS/PASS | MATCHED | PASS | PASS | PASS/PASS | 内容完整，旧定义与新维度均通过 |
| J2 r1 | PASS/PASS | MATCHED | PASS | PASS | PASS/PASS | 内容完整，旧定义与新维度均通过 |
| J2 r2 | PASS/PASS | MATCHED | PASS | PASS | PASS/PASS | 内容完整，旧定义与新维度均通过 |
| N r1 | PASS/PASS | MATCHED | PASS | PASS | PASS/PASS | 内容完整，旧定义与新维度均通过 |
| N r2 | FAIL/PASS | MATCHED | PASS | PASS | PASS/PASS | 旧前缀拒绝 -_0.csv；内容完整 |
| T2 r1 | PASS/PASS | MATCHED | PASS | PASS | PASS/PASS | 内容完整，旧定义与新维度均通过 |
| T2 r2 | PASS/PASS | MATCHED | PASS | PASS | PASS/PASS | 内容完整，旧定义与新维度均通过 |

SQLite：每个入口的 help / 已有表查询功能分别观察，不要求两种新入口同时通过，也不取较好者替换旧分数。

| 原候选 | 原目标/回归 | 旧检查复现 | 包 help/功能 | 子模块 help/功能 | 原CLI help/功能 | 原因 |
|---|---|---|---|---|---|---|
| F2 r1 | FAIL/PASS | MATCHED | FAIL/FAIL | PASS/PASS | PASS/PASS | 实现正文子模块入口，未实现标题包入口 |
| F2 r2 | FAIL/PASS | MATCHED | FAIL/FAIL | PASS/PASS | PASS/PASS | 实现正文子模块入口，未实现标题包入口 |
| J2 r1 | FAIL/PASS | MATCHED | FAIL/FAIL | PASS/PASS | PASS/PASS | 实现正文子模块入口，未实现标题包入口 |
| J2 r2 | FAIL/PASS | MATCHED | FAIL/FAIL | PASS/PASS | PASS/PASS | 实现正文子模块入口，未实现标题包入口 |
| N r1 | FAIL/PASS | MATCHED | FAIL/FAIL | PASS/PASS | PASS/PASS | 实现正文子模块入口，未实现标题包入口 |
| N r2 | FAIL/PASS | MATCHED | FAIL/FAIL | PASS/PASS | PASS/PASS | 实现正文子模块入口，未实现标题包入口 |
| T2 r1 | FAIL/PASS | MATCHED | FAIL/FAIL | PASS/PASS | PASS/PASS | 实现正文子模块入口，未实现标题包入口 |
| T2 r2 | FAIL/PASS | MATCHED | FAIL/FAIL | PASS/PASS | PASS/PASS | 实现正文子模块入口，未实现标题包入口 |

## 表三：验收定义敏感性

| 任务/新维度 | 原目标FAIL→新PASS | 原目标PASS→新FAIL | 未变 | UNKNOWN |
|---|---:|---:|---:|---:|
| csvkit-issue-1225 / csv_original_fixture_content | 1 | 0 | 7 | 0 |
| csvkit-issue-1225 / csv_multisheet_content | 1 | 0 | 7 | 0 |
| csvkit-issue-1225 / csv_file_input_regression | 1 | 0 | 7 | 0 |
| csvkit-issue-1225 / csv_multisheet_file_regression | 1 | 0 | 7 | 0 |
| sqlite-utils-issue-368 / package_help | 0 | 0 | 8 | 0 |
| sqlite-utils-issue-368 / package_function | 0 | 0 | 8 | 0 |
| sqlite-utils-issue-368 / submodule_help | 8 | 0 | 0 | 0 |
| sqlite-utils-issue-368 / submodule_function | 8 | 0 | 0 | 0 |
| sqlite-utils-issue-368 / console_help | 8 | 0 | 0 | 0 |
| sqlite-utils-issue-368 / console_function | 8 | 0 | 0 | 0 |

这里的箭头只是旧目标标签与新维度的交叉计数。原CLI和文件回归本来就通过，其箭头不是“回归被修复”；新增功能/多表覆盖也不是旧裁判误判的自动证据。每个任务的两次重复仍属于同一任务。

## 两个具体例子

CSV N-r2（candidate-06）：原目标 FAIL 在新执行中原样重现，因为生成的是 `-_0.csv`。该文件解析为 `a,b,c` / `True,2,3`，与原XLSX及固定版本默认类型推断一致；新增两表内容、重复行、逗号和引号也完整保留。新内容维度 PASS 有实际执行依据，不只是放宽 glob。

SQLite F2-r1（candidate-17）：`python -m sqlite_utils` 无可执行包入口，help与查询都失败；`python -m sqlite_utils.cli` 能显示help并返回控制器数据库的 `acceptance_items` 表，原CLI也正常。它满足正文示例对应行为，未满足标题对应行为。两种表述都在原prompt中，因此保留歧义。

## 结论与限制

CSV 的旧表面差异对无依据前缀规则敏感；当前8份补丁在本轮有界内容范围均通过。SQLite 的8份补丁在两种解释下得到相同的入口分布。以上不能证明方法等价、泛化收益或所有路由无效。`NO_NEW_INDEPENDENT_GAIN_CLAIM / NOT_CLAIMED / KEEP_NATIVE`。

源码重建逐文件匹配原捕获清单（沿用原流程排除注入技能与运行缓存）；没有修改候选或抽取补丁片段。测试仅覆盖简单XLSX及已支持只读表查询，不覆盖一般Excel兼容性或全部CLI。候选执行是隔离的有界检查，继承的旧pytest包装器仍不是任意恶意代码下的安全证明。

[语义与来源](semantics.md) · [实际命令](usage.md) · [审阅入口](review-index.md)
