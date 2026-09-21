# 开发状态的有限来源核对

核对者为独立只读模型上下文 `source_anchors`，在生成新方法包前，仅依据完整公开题面、检查点前事件和合法 base 独立搜索。未读取选择分数、方法包、reference、evaluation 或旧功能胜负。此为模型辅助有限核对，human_reviewer_count=0；不是完整 gold，也不是完全独立基础模型验证。完整逐要求回复保留在本任务上下文；下列紧凑锚点将用于候选命中与关系分歧检查。

| 状态 | 合法 base 路径与行 | 关系与适用边界 |
|---|---|---|
| empty-keyed-group-naming | lib/ansible/plugins/doc_fragments/constructed.py:45–49 | CONTRACT_SUPPORT：prefix 默认空串、separator 默认下划线、leading_separator 条件。没有新增 trailing_separator/default_value 的规范支持。 |
| 同上 | lib/ansible/plugins/inventory/__init__.py:414–442 | IMPLEMENTATION_CONTEXT：string/list/mapping 分支、空容器与 strict；426–431 的外层 prefix/leading_separator/sanitization 是解释 bare name 的必要上下文。不能把代码现状当成新行为正确性。 |
| 同上 | test/units/plugins/inventory/test_constructed.py:59–81 | VERIFICATION_PATTERN：非空 string/mapping、自定义分隔符的既有断言；未覆盖新增空值替代。 |
| invalid-host-field-errors | lib/ansible/playbook/play.py:105–112 | IMPLEMENTATION_CONTEXT：当前 load 修改 name 并检查 hosts；不支持新精确异常文本或 nonmutation 要求。 |
| 同上 | lib/ansible/playbook/base.py:291–294 | PRECONDITION：validator 调用签名，不证明原始字段存在性保护。 |
| 同上 | test/units/playbook/test_play.py:34–36 | VERIFICATION_PATTERN：缺失 hosts 的空 Play，与显式 None 不等价。 |
| 同上 | lib/ansible/module_utils/common/collections.py:86–97 | PRECONDITION：is_sequence 默认排除 text/bytes；公开接口提到的 collection_loader 路径与 base 不一致，保留 UNRESOLVED。 |
| iterator-state-enum-compatibility | lib/ansible/executor/play_iterator.py:129–142 | IMPLEMENTATION_CONTEXT：旧整数与位掩码取值，不证明新增枚举或 warning 重定向。 |
| 同上 | lib/ansible/executor/play_iterator.py:58–74 | IMPLEMENTATION_CONTEXT：旧 str 已提供可读状态名，公开概述的 opaque numeric 描述不能照单当真。 |
| 同上 | test/units/executor/test_play_iterator.py:442–448 | VERIFICATION_PATTERN：实例旧常量与 failed-state 插入任务行为的有限回归。 |
| 同上 | lib/ansible/plugins/strategy/__init__.py:568 | IMPLEMENTATION_CONTEXT：旧常量消费者，未证明新枚举。 |
| mapping-subtype-combination | lib/ansible/utils/vars.py:86–92 | IMPLEMENTATION_CONTEXT：replace 分支验证 MutableMapping 后 a|b；不证明 VarsWithSources 支持 union。 |
| 同上 | test/units/utils/test_vars.py:62–90 | VERIFICATION_PATTERN：dict/defaultdict 右优先；不覆盖 VarsWithSources。 |
| 同上 | lib/ansible/vars/manager.py:750–753 | IMPLEMENTATION_CONTEXT：data/sources 构造，不证明新增运算或类型保持。 |
| 同上 | test/units/utils/test_vars.py:74–79 | VERIFICATION_PATTERN：combine_vars 拒绝非 mapping 的 AnsibleError，不能挪用为直接 union 的 TypeError。 |

同词对照：`test/units/playbook/test_base.py:350` 中 default_value 只是 FieldAttribute 测试字符串；`test/units/playbook/test_task.py:93–96` 是 Task 而非 Play，且名称断言被注释；`test/units/parsing/yaml/test_dumper.py:94–95` 对 VarsWithSources 做 YAML dump，不能支持 union。

核对指出的解析问题：运行器环境说明和“No new interfaces”不应功能加权；Type/Name/Path/Description 应组成完整接口声明；概述与详细要求、接口与行为描述可能重复，父要求归一尚需检查。以上在开发阶段修正，不冒充冻结验证结果。来源提到的 leading_separator 是原有实现/文档前提，不能自动新增成题面义务。

旧 invalid-host-field-errors 仅用于公开状态与检索诊断，本轮未重裁旧16条UNKNOWN或15条保护失败。
