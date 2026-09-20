# 旧 train/dev 诊断（不改旧记录）

只读取 functional-v2 native/collection 开发记录、原补丁、判分和对应私有可见检查点；未重新执行旧 Agent 或旧最终矩阵。记录身份核验与失败断言见 `artifacts/task-skill-failure-diagnostic-v1/legacy-inventory.json`，原补丁引用其 evidence_path，不复制旧证据目录。

| 案例 | 公开义务与终端断言 | 原补丁行为/当时可见信息 | 原技能覆盖与分类 |
|---|---|---|---|
| sqlite-utils-fix-60811e7 原生 | rowid别名、ignore后的身份报告、hash-id及不可解析冲突；终端 last_rowid None≠1、hash-id的1≠None、无显式pk的1≠None | 广泛搜索冲突行并推导身份；E1公开有 KeyError(rowid)，另有 black缺失（基础设施），不可混为功能难点 | 原生无额外技能；库sqlite-ingest说明ignore/upsert语义却不说明上述身份细节。代码/需求解释边界，非“模型不知道”证明 |
| csvkit-fix-8119565 E1 csv-dialect vs no-op | --maxfieldsize 与 dict读取；旧target直接调用 csv.DictReader(stream, **utility.reader_kwargs) 抛 TypeError | K新增过滤助手并改实际csvpy/csvstack路径，N全局调整reader_kwargs；K实际CLI调用可能正确。E1公开还有9项广泛测试失败及git缺失，不能全部认作目标困难 | csvformat操作技能不说明内部kwargs桥接。旧记录K=0,N=1保留；判分耦合内部属性，CLI退化解释 REVIEW_REQUIRED，未重新判分 |
| csv-diff-fix-33e0a59 E0 keyed-csv-diff vs no-op | 缺失字段补None、保持nested JSON行为；目标过，保护回归期待嵌套值为JSON字符串而K返回dict | K移除_simplify_json_row，改compare并把公开测试字符串预期改成对象；N保留序列化；E0尚无工具错误 | 技能明确旧版不覆盖JSON输入。真实输出契约变化，题面“preserve nested”也有语义歧义；来源/原公开测试支持字符串，不能认领纯知识因果 |
| csv-diff-fix-0cf7d3c E0 keyed-csv-diff vs no-op（排序控制1） | 自动识别分号，保持普通CSV/TSV | 两补丁均将Sniffer候选从逗号/tab扩展为分号；K=N=1；E0无错误 | 技能不描述分号。功能持平不证明指导被使用或有增益 |
| csv-diff-fix-33e0a59 E0 sqlite-fulltext vs no-op（排序控制2） | 同上稀疏JSON机制 | 两者补None并保留_simplify_json_row；K=N=1；E0无错误 | FTS操作与JSON缺失字段不匹配。控制与退化案例重叠，不能当额外独立机制 |

控制在读补丁前按任务ID排序选两个有功能持平的任务，并采用原记录首个持平技能对；因此第二个与退化案例同机制，保留而不换成更好看的控制。字段/成本均未进入功能标签。

`60811e7` 原生失败不是所有尾程的永恒零基线：逐E0/E1/E2 no-op结果保存在inventory的 native_recovery_controls。后续no-op通过属于原生恢复或随机执行差异，不能记为技能救回。检查点历史/源码本地可定位，但本轮只作历史诊断，未声称重演。

当前假设：至少同时存在接口知识覆盖有限、公开错误混有基础设施噪声、任务/验收语义耦合以及原生续跑恢复。下一轮新池须从公开行为定义目标，不使用参考补丁生成指导；当前记录不足以将瓶颈唯一归因于技能内容。
