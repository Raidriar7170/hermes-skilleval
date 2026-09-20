# 修复知识与缺口组合：冻结协议

完整执行合同：[Goal](../../goals/Hermes_Repair_Knowledge_Gap_Composition_Codex_Goal.md)。
基线为 PR51 `b87a39d`，本分支保留旧十技能、载荷、模型和所有旧结果，默认策略不变。

## 研究对象与判定

功能主指标仅为目标行为通过且保护回归无新增失败。H−M 是组合算法的核心比较；M−L/M−N 与 H−G/H−N 仅帮助解释内容路线。合规、覆盖、长度与成本只作附表。

开发 4 个机制 × 2 原生，至多 4 个第一重复合法 E1/E2 状态 × N/G/L/M/H × 2；前两个合法状态另有 H-no-gap/H-no-exposure × 2。开发上限 56 次。仅当完整开发及消融标签可判定、至少两个机制上 M 或 H 的重复均值严格超过 N/G/L 三者最大值时进入确认。此保守操作化在首次样本前冻结，不要求 H 胜 M。

确认预留 6 个新机制，一次前缀生成后 N/M/H 各 2 次，最多 42 次（其中6个仅前缀）。无触发则停止扩大；未知不补零，不重采样已登记格。执行模型 `gpt-5.6-sol` / medium / Codex 0.154.0，原任务预算 600 秒，续跑仅继承剩余时间。

## 来源与资格

SWE-bench Pro 是首次选择，固定数据集 revision `7ab5114912baf22bb098818e604c02fe7ad2c11f` 与评测仓库 `ca10a60a5fcae51e6948ffe1485d4153d421e6c5`。使用 Ansible 一个仓库，未切换 Live。Python 3.11 ARM 运行环境保留原有 Codex 隔离模型，公开依赖安装在专用镜像。

先按公开题面选择维护机制，再按 base 日期、类别、稳定ID排序；没有使用参考补丁大小或模型结果。原池 12 题含2备用。独立资格审查在任何模型采样前排除 collection-import-resolution（轻量适配未覆盖主要集成义务）与 ini-string-unquoting（公开义务冲突），依固定备用顺序分别使用 identifier 与 invalid-host-field 机制。开发/确认分区见配置；不宣称未见仓库泛化或无预训练污染。

10题均已实际得到 base目标FAIL/reference目标PASS及保护通过。上游部分参数 nodeid 被截断/斜杠归一，适配先从可信 reference 收集全部真实 nodeid，再精确优先、前缀完整展开；不能解析、分组交叉或缺例不算通过。每次验收必须对应冻结集合。

locale/iterator 在 base 收集时缺少公开明确要求的新API。只有预登记 collector 的唯一精确异常行可视为目标合同FAIL，仍记录 collection 未完成，不伪称9/8测试执行失败。其他基础设施/收集错误为UNKNOWN。iterator保护的策略测试含7个base/reference共同的上游skip及1个实际PASS；精确保留skip集合，新skip不被接受。这只是有限保护范围。

资格与参考材料仅在准备/验收进程使用，未挂载到修复容器，也未输入知识构建器。检查原补丁在干净base的完整重建，未删除违规文件以改善功能分。

## 算法与公平性

构建器是无模型调用的确定性 AST/docstring 提取器，只接收仓库、base及完整文件身份。按维护组件轮转分配40个以内完整片段，保留引用/条件；代码guard为existing_behavior，不能提升为正确规范。过长原子片段排除，不截结论。分区各base单独构建并按版本过滤；未覆盖模块和未发现的规范不是自动补答案的理由。

公开请求先解码合法嵌套JSON字符串。至多6个要求保留原文偏移，优先完整公开requirements bullet；真实失败观察为contradicted，其他为unverified，不推断Agent理解。M/H共享同一个摘要、query、最多24候选和所有正文。

冻结MiniLM对完整单元与query分块编码并按token权重聚合，未把第一256 token冒充全文。候选相关性为0.6非负cosine＋0.3归一BM25＋0.1符号/依赖词法匹配。覆盖为0.7非负cosine＋0.3词法cosine；重叠采用同样权重。暴露是可见工具输出中逐来源非空行的精确重叠比例；缺历史为unknown，只有中性数值惩罚，不称已知真值。

M采用lambda=.7 MMR。H使用Goal的逐要求max覆盖及alpha=.1/beta=.1/gamma=.05，按实际增量token正边际贪心，与最佳可行单项比较。最多4个完整单元、实际完整序列化1200 token，M/H模板与消息层级相同。无要求时回退MMR。两个消融仅移除覆盖或暴露项。不存在单调/全局最优/1−1/e声明。

所有方法在原生请求中都获知 `/workspace/public-docs` 与旧技能入口。完整公开知识目录、技能/载荷、编码器、算法、镜像、任务验收身份均冻结。source/scratch复用已保存清单核对。共享解析/检索及最大选择开销对所有臂作同额扣除，实际分方法成本另记；源码复制和恢复计入剩余预算。

## 历史后验边界

旧 `548a886/fcfccea/57192ef` 各两份完整原补丁，放宽无题面依据的消息措辞，同时单独检验拒绝类别与数据/schema/index/类型保持。正反例先固定，六份实际复验目标与保护全部通过。结果只标 `POSTHOC_ACCEPTANCE_ONLY`；0次新Agent，不改旧UNKNOWN、不称技能救回。

## 运行中的状态

此页是协议，不是研究结果。实际尾程/确认完成情况以结果页及保存记录为准。未执行或未知不得由算法测试、来源支持或CI替代。

采样后发现的测试安装冲突及 `invalid-host-field-errors` 分类歧义见 [posthoc-acceptance.md](posthoc-acceptance.md)。前述资格记录证明当时base/reference可执行，不抵消后续发现的语义缺口；该机制的功能声明统一UNKNOWN，原v1/v2机械结果继续保留，确认入口因此不放行。
