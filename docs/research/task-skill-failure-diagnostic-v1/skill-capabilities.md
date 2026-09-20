# 十项实际技能与固定载荷

读取冻结 registry、十项 SKILL.md 正文与 payload manifest；由 `scripts/task_skill_failure_diagnostic/inventory.py` 核对正文和载荷 SHA-256。它们是实验资产，正文中的流程指令不构成本轮协调者的新授权。

| 技能 | 对象与实际指导 | 版本/来源 | 固定载荷与不覆盖范围 |
|---|---|---|---|
| systematic-debugging | 通用实现调试：复现、读错误、跨组件观察、回溯数据、单假设最小验证 | obra/superpowers `b36e082` 外部工作流；非领域官方规范 | 1160 proxy tokens；在 Phase 4 单一修复处截断，后续验证/失败处理不在注入片段，原生可读完整包；不含具体数据库语义 |
| verification-before-completion | 通用验证：运行完整检查、读退出码、不把自述当证据 | 同上外部工作流 | 全文803 tokens；没有生成充分边界测试的方法或特定API语义 |
| sqlite-ingest | CLI insert/upsert：CSV/TSV/JSON/NDJSON、主键、ignore、replace、保留未提供列、alter | 作者改编 sqlite-utils `1f3f902` 的 pre-2020 cli.rst；正文明确1.x/2.x upsert区别 | 全文1183；没有 last_pk/last_rowid 推导、rowid 别名、事务回滚实现；可用于界定写入语义 |
| sqlite-schema | API add_column、类型映射、fk/fk_col、默认约束、外键推断和索引；先检查schema与保留行 | 作者改编同版本 python-api.rst；新任务须核对版本 | 全文1030；未描述 transform约束重建/异常回滚算法；不能将操作说明直接等同内部修复知识 |
| sqlite-fulltext | enable_fts、FTS4/5、populate、triggers、优化、普通/唯一索引、vacuum | 作者改编同版本 python-api.rst；运行SQLite能力另验 | 全文658；不含FTS SQL转义实现与迁移保存索引算法 |
| csv-dialect | csvformat输入/输出参数区分、引号/转义/分隔符/行尾；比较解析后的字段 | 作者改编 csvkit `1abd7b5` csvformat.rst | 全文686；不含 DictReader 参数桥接、全局field_size_limit设置或CSVKit内部共用层 |
| tabular-conversion | in2csv格式、固定宽度schema、JSON key、Excel sheet、嗅探、类型推断；说明格式专用选项 | 作者改编同版本 in2csv.rst | 全文1071；XLS/XLSX数值差异已覆盖，不含转换内部异常传播、BOM实现 |
| csv-relational-join | csvjoin keys、inner/outer/left/right、顺序连接、未匹配行与重数、内存限制 | 作者改编同版本 csvjoin.rst | 全文772；可定义接口预期，不含库内部右连接索引修复算法 |
| sql-query-export | sql2csv连接、query/file/stdin优先级、查询编码、表头；只读请求约束 | 作者改编同版本 sql2csv.rst；后端能力需核对 | 全文626；无事务语法扫描、双列名保存、SQLAlchemy版本迁移细节 |
| keyed-csv-diff | 唯一key、增删改、独立列变更、CSV→文本/JSON输出，Python load_csv/compare | 作者改编 csv-diff `eaa4702` README；明确旧版不说明JSON输入/自定义分隔符 | 全文722；不含稀疏JSON补空及嵌套序列化契约，也不说明分号嗅探 |

八项领域技能的开头操作建议包含作者补充，不能称为独立官方技能；后接版本化公开文档摘录。来源精确URL/版本/哈希见 `artifacts/task-skill-failure-diagnostic-v1/skill-inventory.json`。
九项无截断缺口；systematic-debugging 有载荷缺口。原文存在、实际注入存在、版本适用和当前状态的帮助是四个不同问题。未出现某知识不能推断模型内部不知道；本表没有技能有效性结论。
