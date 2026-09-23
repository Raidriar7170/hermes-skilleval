# 执行已结束，最终交付核对中

本轮唯一合同是 [完整 Goal](../../goals/Hermes_Budgeted_Anytime_Relation_Selection_Codex_Goal.md)。基线为 PR53 `d1ed9cefeb39be856057392c2abd962350dc91a9`，新分支 `codex/hermes-budgeted-relation-selection`，叠加 Draft [PR54](https://github.com/Raidriar7170/hermes-skilleval/pull/54)。不合并、不转 ready、不发布、不晋升默认。

执行代码 `579f2e44a3029f07b62a9ed29690f9251c992594`；冻结提交 `126ae6d`；计划摘要 `894ba351e433b7f8e012e6e006d09dca575d27ae4b269b0e0746281d455db61e`。后续新增仅为验收重建、导出、测试和说明，冻结研究源码保持不变。

两条新公共前缀均只执行一次。P 的12条尾程全部完成；C的8条M/A尾程全部完成，4个D格记录 NOT_RUN_UNAVAILABLE。总计22次真实研究执行，不是26次已运行。两个A均返回与M逐字节相同的MMR包，保留全部准备成本。两个D均为PARTIAL，无正关系支持。两个正式A/S隐藏表回放已实际完成，各8行、零模型调用、零修复执行。

原接续进程正常完成D/C，首次EVALUATE在宏P-A-r1的空文件权限重建差异处停止。原source与snapshot完整一致；Git不能表达0600权限，重建为0644。失败树保留，独立目录用绑定补丁和清单摘要的sidecar恢复原权限，通过完整inventory比较后运行相同可信覆盖。仅此格使用修复验收版本，不修改原候选、不删不利文件、不重跑Agent。验收接续会话82017已正常退出。

正式report、记录replay、隐藏表replay、紧凑export均已实际成功。保存的功能结果为20 PASS、0 FAIL、4 UNKNOWN；20个实际尾程预算均有效。P的A−M/A−N与C的A−M观察差均为0；D缺失不支持A−D结论。功能收益与关系获取效率均NOT_ESTABLISHED，默认UNCHANGED。完整分母、成本边界和三张表见[结果](results.md)。

最终新增权限重建/导出针对性测试7项通过，全套1582项通过（43.49秒）；Ruff与本变更OpenSpec严格校验通过。冻结HEAD的CI已通过；独立证据复核已完成（20个原补丁、80目标/370保护用例及预算）；最终HEAD的CI、完整SHA-256闭合和推送收尾仍在进行，不能提前称Goal完成。

本轮未覆盖旧UNKNOWN、旧功能结果或旧索引；开发真实辅助调用、预演失败、旧322/336行导入和不同传输版本均保留于开发证据。正式运行前统一将batch从8调整为2，之后未因功能结果调参。局部准备费用仅有合计，细分不可补造。
