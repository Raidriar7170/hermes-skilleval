# 后验裁判安装修复

56次开发Agent执行完成后，原版验收发现：候选正常改动公开测试时，直接向候选应用隐藏 `test.patch` 会发生上下文冲突，导致目标与保护均未执行、标为UNKNOWN。这不是功能失败，也不是新知识方法的效果。

按完整Goal第139行的授权，保留全部原验收目录、错误与v1结果，采用同一v2安装规则对全部56份完整原候选对称复验，标记 `POSTHOC_ACCEPTANCE_REVALIDATION`。没有新增Agent，没有修改任务、选择器、skip规则、知识库、H/M参数或载荷；不选取v1/v2中较好的分数。

v2先在独立可信base上应用原冻结测试补丁，从其完整文件清单形成覆盖层，包括明确涉及的fixture、mock、配置和脚本。安装时核对补丁SHA-256、精确路径集合、文件内容与权限；仅覆盖这些 `test/` 路径。当前补丁没有删除、重命名或链接，有限适配器不支持这类扩展。

完整原补丁仍先在干净base重建，且与v1原补丁逐字节同一。只在独立 `evaluated` 验收副本中安装可信测试文件；生产代码、未列入覆盖层的候选测试与其他候选修改全部保留。父目录symlink拒绝，叶symlink只在验收副本中替换、不跟随；记录覆盖前后身份并验证所有额外内容差异仅限明确覆盖路径。不能把验收副本称为未经修改的原候选，也不能把这种测试安装修正称作算法救回。

先以v2确认四个开发机制仍为base目标FAIL/reference目标PASS及保护通过，再复验原生8格与尾程48格。冻结计划身份与精确研究格集合必须匹配；当前结果只在所有候选复验完成后更新，v1原记录另存。功能主表采用统一v2，并同时展示v1未知边界。

入口：`scripts/repair_knowledge_composition/revalidate.py --private ../hermes-repair-knowledge-private --plan configs/repair-knowledge-composition-v1/plan.json`。这是既有候选的后验验收，不计作新的研究执行；实际测试调用单独记录。

## 公开合同分类歧义

独立复核发现 `invalid-host-field-errors` 的隐藏测试把标量 `0`、`False` 归为empty并要求“Hosts list cannot be empty”，而公开要求同时给出empty/None与非string/sequence两种消息，没有声明这两个标量的分类或优先级。修复前公开测试没有建立该分类，不能仅凭消息差异声称功能失败。

这一机制所有原生/尾程的目标合同有效性统一标UNKNOWN，再由既有 `functional_outcomes` 得到功能UNKNOWN。原始v2机械检查不删除、不改判通过；空set/dict的保护失败比标量案例有更明确依据，仍逐项保留。此处理通过 `export.py claims` 生成派生 `functional-claims.json`，不修改测试断言，不重新采样，也不覆盖v1/v2原始结果。功能主表采用该保守声明边界，原始检查表另列。确认所需完整可判定证据因此未满足。
