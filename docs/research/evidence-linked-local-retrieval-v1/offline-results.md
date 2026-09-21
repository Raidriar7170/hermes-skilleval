# 四个已观察开发状态的离线结果

这一阶段没有重跑修复Agent，也没有重判旧56格。四个状态均已被观察，不能作为冻结方法后的独立功能验证。初版输出、各开发修复版及模型无效提议保留在私有运行记录，公开目录保留旧基线与最终development-v5紧凑材料。

## 表示修复的具体事实

旧empty-keyed-group-naming六项摘要把共享库加载失败和`.git/HEAD`缺失分别赋2，总权重4/8=50%。完整账本现在保留13个题面段落/要求行，string/list/dict空值、互斥、无替代值等分支不再被前六项上限截掉；3个环境观察仍保留，但未关联为功能义务，功能权重为0。

公开事件21、27曾返回测试成功，但来源版本在复合命令及后续动作下无法充分确定，最终为historical_unresolved；环境事件2、15、25保留unknown。本轮没有将最后一次退出0解释为环境全恢复或所有功能已验证。13行包含概述/细项重叠，是保留原文的行级表示，不是13个独立、去重后的语义义务。

## development-v5 后缀受限索引与检索

| 状态 | 索引文件 | 节点 | 共同候选 | 旧40子集候选 | 无扩展与全版相同候选ID |
|---|---:|---:|---:|---:|---:|
| empty-keyed-group-naming | 3938 | 67849 | 24 | 21 | 24/24 |
| invalid-host-field-errors | 4110 | 69813 | 24 | 24 | 22/24 |
| iterator-state-enum-compatibility | 4169 | 71123 | 24 | 22 | 24/24 |
| mapping-subtype-combination | 4089 | 57793 | 24 | 24 | 24/24 |

下表对应当时的后缀白名单索引。后续在读取新功能标签前发现它遗漏了合法 `.psm1`、`.cs` 及无扩展名文本；因此不能称完整合法范围。范围修复另做离线重建，不改这些历史候选、关系和包。

索引不表示所有节点能装包：超长定义、闭包上下文不足、源类型/排除范围分别记录。Python可静态确定的调用/import边被保留，动态分派不假造确定边。没有前40项查询前上限，但检索仍是固定8/128/24预算，有遗漏。

固定该版本索引下，旧摘要query与新query的候选ID重合分别8、10、16、13/24；这仅显示query改变了召回，不能归因为功能收益。关闭一跳后四状态中三个最终候选完全不变，另一个只变2项，未建立代码图扩展的功能价值。

独立锚点核对确认constructed文档和真实命名分支进入候选，mapping的`combine_vars`实际`a | b`分支、`VarsWithSources`类也进入候选。原40库中被选中的fact-cache/debugger/config主题不再是唯一入口。另一方面，constructed separator公开测试、真实is_sequence定义、iterator整数定义/兼容测试、mapping右优先/defaultdict示例等锚点仍有未命中。锚点集不完备，不能称完整仓库召回率。

## 关系与实际选择

关系提议独立于选择器分数；另一个盲化上下文先判96个候选，再检查12个匿名包。human_reviewer_count=0，两种模型上下文也不能消除相关错误。

| 状态 | 正关系提议 | 核对支持 | 反对 | 未知 |
|---|---:|---:|---:|---:|
| empty-keyed-group-naming | 53 | 18 | 0 | 35 |
| invalid-host-field-errors | 44 | 16 | 5 | 23 |
| iterator-state-enum-compatibility | 80 | 28 | 0 | 52 |
| mapping-subtype-combination | 33 | 14 | 0 | 19 |
| 合计 | 210 | 76 | 5 | 129 |

未列明的要求—单位关系以及关系类别分歧保留UNKNOWN，未知没有从分母删除。此有限核对不能证明关系精度已充分成立，更不证明功能正确。

| 状态 | M-local tokens / 主题无关单位 | H-sim tokens / 主题无关单位 | H-link tokens / 主题无关单位 |
|---|---:|---:|---:|
| empty-keyed-group-naming | 1047 / 1 | 770 / 2 | 916 / 1 |
| invalid-host-field-errors | 1145 / 0 | 250 / 0 | 584 / 0 |
| iterator-state-enum-compatibility | 1107 / 2 | 1138 / 3 | 744 / 1 |
| mapping-subtype-combination | 1174 / 1 | 597 / 1 | 665 / 0，另1 UNKNOWN |

例如H-link的empty包包含constructed文档，也夹带不能证明精确AnsibleParserError的通用互斥helper；mapping包包含真实replace调用点，但fact-cache的`|=`缺少VarsWithSources类型可达依据。不能因选到较多对题片段就称覆盖了全部条件。各包中的旧实现、完整分支与局部截断限制均保留。

离线终态：要求保留/环境污染的具体实现问题已修复；真实后缀受限索引和同池选择已执行；来源关系质量提升`NOT_ESTABLISHED`。允许进入固定小型功能验证，不能把H未离线胜出当作停止或继续调参的理由。

## 预标签范围修复的独立离线版本

`fulltext-index-repair-v1` 删除后缀准入限制，保留 UTF-8/二进制、路径、第三方、生成物及历史版本说明排除。相同六个合法 base 分别新增663/659/663/640/725/728个文件，未移除原索引文件；文件数分别4482/4597/4773/4809/4814/4847，顺序为宏、empty、invalid、iterator、mapping、cache。每个实际重建后都运行固定检索，得到24候选；没有新关系提议、重组包或修复Agent。

独立上下文核对六份index/pool身份和18个新增psm1/cs/无扩展名来源的真实内容与跨度；新增非Python节点不产生import/call边。补丁在隐藏功能标签前冻结，sha256为`ed18a9691da1654c962b4f535c782f03d81feb4d6e1229d2a01e5d8d4e7b37c2`。完整计数、排除原因、代表来源、实际候选见`artifacts/evidence-linked-local-retrieval-v1/index-scope-repair/`。此版本的功能验证为`NOT_RUN_FOR_REPAIRED_INDEX`，不能继承旧索引尾程的成功。
