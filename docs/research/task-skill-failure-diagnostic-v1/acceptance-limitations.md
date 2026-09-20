# 验收有效性限制

冻结目标检查仍按原样运行，原补丁、JUnit 和 `y_functional` 均不覆盖。原生探测已开始后，独立只读审阅发现三处错误文案约束超过公开题面：

| 机制 | 过度约束 | 公开义务 |
|---|---|---|
| `548a886` | `Invalid columns`、`Invalid primary key column` 精确消息前缀 | 正常非零 Click 错误，不暴露原始异常 |
| `fcfccea` | `is not STRICT, so it cannot preserve ANY column values` 正则及具体异常类型 | 对不能保持 ANY 值的既有非 STRICT lookup 安全拒绝 |
| `57192ef` | `partial or expression index` 正则 | 对不支持的复杂索引抛出 TransformError 并保留数据 |

STRICT ANY 前两次原生终端目标均为 8 过、1 败，唯一失败是已经抛出 `InvalidColumns` 后的消息正则不匹配。该失败不能证明题目功能未完成。正则异常使其后的同一测试数据保留断言未执行，因此也不补判为功能通过。

索引重命名第一轮通过；第二轮为 4 过、2 败。两个失败分别针对 expression/partial index，候选均抛出 `TransformError` 并在消息中分别说明索引类型，但测试要求固定合并短语 `partial or expression index`。这是原已登记规则识别的文案歧义，不是看到新结果后新增豁免。第二轮同样保留原始失败、解释为 UNKNOWN，未将抛异常后的未执行断言补判通过。

`acceptance_audit` 为保存的 JUnit 添加独立有效性解释：仅已知过约束断言的文案匹配失败、且没有其他独立目标或回归失败时，`interpretable_y_functional=UNKNOWN`。未抛异常、数据损失、其他独立功能断言失败仍是失败。原始 `y_functional=0` 保留；此解释不是新评分奖励，也不是补测或新 Agent 执行。

该规则在首轮分支/K 选择前锁定。现有任务不换题、不修改测试、不补重复，不把 UNKNOWN 用作真实原生失败面板，也不能把含 UNKNOWN 的池称为全部通过。如果其余任务没有可信失败，报告困难 UNKNOWN 且尾程不触发，避免只运行成功控制。

这暴露了资格流程的局限：base 红、reference 绿不足以证明检查完全实现题面合同。其余通过结果仅支持已执行检查；例如 ANY 的部分大小写/add-column 组合、混合外键的非法项拒绝未完整覆盖。后续研究应先完善行为级验收，不能在本轮看到结果后调测试追求正例。

公开复算分两层：既有入口验证原始候选/目标/回归证据；本轮入口额外从公开 JUnit 重算有效性解释、难度计数、同状态比较和机制等权聚合。历史分叉、完整源码状态和状态资格由独立收据支持，不将记录复算称为重新执行。
