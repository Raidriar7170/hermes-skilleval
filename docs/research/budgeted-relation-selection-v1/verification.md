# 验证范围与完成依据

本轮验证边界是预算化来源关系选择实现与两个已观察机制上的有限研究交付；不声称算法增益、生产部署、训练、发布或默认策略晋升。主结果、限制及分项终态见 results.md。

## 四个范围

- `read scope`：仓库 `.`，以及复算说明中明确列出的本地任务、最终索引、冻结编码器、覆盖与新研究记录。
- `write scope`：本轮8个新增 `src/hermes_skilleval/intervention` 模块；`scripts/budgeted_relation_selection`；3个 `tests/test_budgeted_*.py`；`configs/budgeted-relation-selection-v1`；`artifacts/budgeted-relation-selection-v1`；`docs/research/budgeted-relation-selection-v1`；本轮 Goal 文件；`openspec/changes/budgeted-relation-selection-v1`。旧研究文件不在写范围。
- `frozen asset scope`：冻结计划所列50个执行/辅助文件，两个任务的base/evaluation、要求、公共索引、可信覆盖、表示模型和Docker/CLI身份。最终重新执行原 `budgeted_study_assets.verify`，包括编码器和覆盖，3.63秒通过；不存在以新算法版本替换旧功能结果的情况。
- `final repository scope`：`.`，明确基线 `d1ed9cefeb39be856057392c2abd962350dc91a9`。完整tracked delta、冻结计划和公开声明证据以新读SHA-256核对；缓存、权重、完整第三方源码和私密会话不进入公开材料。最终SHA-256报告保存在本地私有研究目录并在交付状态中报告，避免把报告自身循环纳入其摘要。

## 合同验收对应

| Goal要求 | 当前依据与边界 |
|---|---|
| §1–5、19–20：历史、最终索引、冻结与两个机制 | 原Goal、冻结plan、50个执行文件摘要、最终索引身份与新前缀；旧PR53/UNKNOWN未改写 |
| §6–7、12–14：基线解耦、稀疏行、恢复和费用 | 新模块及25项机制测试；真实开发保存/加载/续接；旧322/336独立导入；失败调用与原始attempt保留 |
| §8–11：固定目标、精确求解、优先级与停止 | 同一A/D求解器、完整要求域、A真实query_basis与trace；无正关系时MMR回退；上下界不是语义真值 |
| §15–16、21–24：P/C与可信功能 | 2前缀、12P和8C原始尾程；4D未运行；20完整原候选重建；80目标/370保护JUnit；预算独立复算 |
| §17–18：A/S/D与实际恢复预演 | development.json与正式隐藏表回放；两种证据分开；D PARTIAL不填零，无获取效率结论 |
| §23、25–26：成本、三张表与结论 | results.md、costs.json、functional-results.json、acquisition.json；本地准备只有实测合计，明确缺少精确细分 |
| §27–29：实际入口、回归与交付 | prepare/freeze/prefix/compose/P/D/C/evaluate/report/replay实际执行；验收权限修复有独立版本；1582测试通过；新Draft PR54 |
| §30–32：有限结束、不扩张 | P COMPLETE、C PARTIAL/D PARTIAL；功能和获取效率NOT_ESTABLISHED；默认UNCHANGED；不训练、不合并、不发布 |

## 独立证据核对

`artifacts/budgeted-relation-selection-v1/independent-review.json`记录独立复核：20个原补丁均在临时干净base重建，19个仅补丁、1个加原权限sidecar；完整清单与source/capture一致。所有目标/保护用例独立解析并与冻结收集集合核对。20个补丁、100个压缩验收文件完成字节/摘要关联，公开内容无敏感标记。该复核未新调用模型或重跑可信验收。

首次宏P-A-r1验收失败保留：字面路径 `~/.ansible/galaxy_token` 为0字节，原0600、Git重建0644。修复只恢复同路径、同类型、同内容、同可执行位的原权限，在独立重建目录执行。sidecar绑定原补丁和完整清单；删除文件或改内容会被拒绝。冻结修复Agent源码不受影响。

## 已完成检查

- 全套pytest：1582 passed，43.49秒。
- 新验收/导出边界：7项通过；真实Git权限丢失最小复现与恢复通过。
- 新脚本及测试Ruff检查/格式检查、OpenSpec本变更严格校验、scoped diff检查通过。
- 新测试mypy通过。一次使用`--no-site-packages`的本地尝试因隐藏pytest/项目导入而失败，改用正常环境和`MYPYPATH=src`后通过；没有为通过检查修改类型规则。
- 全套GitHub既有CI验证以PR当前提交的实际检查为准；不将本地pytest代替CI，不将CI通过代替功能证据。
