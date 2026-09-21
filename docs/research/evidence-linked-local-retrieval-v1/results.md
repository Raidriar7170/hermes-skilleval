# 结果：部分执行，无已建立功能收益

实际执行2个公开前缀和8条cache尾程；宏任务8条未启动格原样保留UNKNOWN。实验代码为`32129083060129f9fd0b4740039f46c6614dcbda`，运行计划为runtime-repair-v2。全部实际尾程结束后统一验收，原候选完整捕获并重建；每条cache候选执行1个可信目标用例、30个保护用例，均无失败/错误/跳过。文件策略另外记录，均通过。

| 机制 | 臂 | 目标 P/F/U | 保护 P/F/U | 功能 P/F/U | 计划 |
|---|---|---:|---:|---:|---:|
| documentation-macro-boundaries | N | 0/0/2 | 0/0/2 | 0/0/2 | 2 |
| documentation-macro-boundaries | M-local | 0/0/2 | 0/0/2 | 0/0/2 | 2 |
| documentation-macro-boundaries | H-sim | 0/0/2 | 0/0/2 | 0/0/2 | 2 |
| documentation-macro-boundaries | H-link | 0/0/2 | 0/0/2 | 0/0/2 | 2 |
| variable-file-cache | N | 2/0/0 | 2/0/0 | 2/0/0 | 2 |
| variable-file-cache | M-local | 2/0/0 | 2/0/0 | 2/0/0 | 2 |
| variable-file-cache | H-sim | 2/0/0 | 2/0/0 | 2/0/0 | 2 |
| variable-file-cache | H-link | 2/0/0 | 2/0/0 | 2/0/0 | 2 |

cache这一个可判定机制中，四臂均2/2通过，H-link−M-local、H-link−H-sim、M-local−N均为0。该任务没有功能区分力，不证明策略总体等价。保留宏任务的完整计划分母、先按机制均值再等权平均，各臂通过率区间均为[0.5,1.0]，三个差值区间均为[-0.5,0.5]。因此完整计划的两个主要收益标记为UNKNOWN；没有观察到可支持晋升的收益。

## 方法缺失与版本边界

宏任务的322/336关系矩阵不完整，原输出和失败成本保留，未补标签/换候选/重抽模型。无法恢复完整预处理计时，故四臂对称保留8格UNKNOWN。cache仍按原名单、同一检查点、原固定包和预算执行。验证状态为PARTIAL_REPAIRED_AFTER_FREEZE，不能声称完整首次冻结验证。

运行中、功能标签打开前另发现后缀白名单漏收合法文本。修复补丁先在隔离工作树完成并冻结，验收后才应用当前代码；六base离线范围与检索核对已通过。**本次功能表只属于原后缀受限索引，最终全文本索引没有新功能验证。** 没有按功能胜负调整权重、提示、包或任务。

## 成本与限制

cache前缀约78.86秒，共同预处理实际213.287秒，各臂初始可用尾程预算307.859秒；N同样承担该费用，这是实验公平约定，不是线上原生延迟。宏前缀约41.35秒，其失败阶段总计时未知；已知观察关联20.392秒、关系调用248.384秒保留，不编造完整总数。

已捕获开发/传输helper调用29次，新状态观察/关系helper4次；另有10次实际研究执行。来源审阅和协调模型调用未包含，总API调用/账单未知。逐格charged时间、控制器开销、注入观察与tokens见costs.json；不能把包含共同收费的tail_seconds再当纯Agent增量相加。

独立来源核对是有限模型辅助评价，human_reviewer_count=0；公开题面/base可能已见，只有一个机制可完整判定，两次重复共享前缀。既有保护集合不证明全部仓库行为正确，少量来源锚点不证明完整召回率。

## 证据入口

- [一页算法复盘](retrospective.zh-CN.md)、[离线结果](offline-results.md)、[运行与重放](reproduction.md)。
- 仓库`artifacts/evidence-linked-local-retrieval-v1/functional-results.json`：16格原标签、检查计数/身份及8份完整原补丁。
- 同目录`functional-summary.json`：机制等权与完整计划上下界；`terminal.json`：分项状态；`costs.json`：真实已记录成本。
- `new-states/`：冻结候选、关系、实际注入包及独立匿名核对；`index-scope-repair/`：预标签补丁身份、离线范围和实际候选。

不重跑/重判旧56格，默认UNCHANGED，无新训练、合并、ready或发布。

独立证据复核PASS：重新读取约447 MB、167,904文件条目，核对全部8原候选身份/模式/符号链接、overlay边界以及JUnit/collection；独立重算上述16格和差值。详见公开independent-acceptance-review.json。这是记录与来源完整性复核，没有重复Agent或可信测试。
