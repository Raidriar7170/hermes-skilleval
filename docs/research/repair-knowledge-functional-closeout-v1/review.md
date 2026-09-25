# 独立核对与交付边界

一名只读 Reviewer 检查了可信资格合同、薄适配及最终原始证据；未修改文件、调用模型或新增实验。该角色是独立模型审查，不是人工gold，也不能补齐缺失的运行计时。

冻结前已处理参数化选择器未展开、R准备缺失阻断N/M、公开挂载冻结不完整、镜像身份缺复核、收益未约束预算/注入、集成状态硬编码、多行可见性匹配等接线问题。前缀/获取后发现的共同checkpoint验证漏计无法恢复，原执行保留；仅在尾程开始前补齐后续准备计时。故integration为PARTIAL，全部M/R预算为UNKNOWN_PREPARATION_COST，两项收益为UNKNOWN。

最终独立核对确认：

- 4个公共前缀，24次真实分叉的可见历史和初始文件一致；16/16个M/R载荷出现在实际用户输入中。
- 8条R获取各自独立，8个锁文件新鲜SHA-256均与尾程前记录一致；6个包不同于MMR，2个为MMR后备。
- 费用组件相加、尾程初始化费用和绑定一致，已计组件均未超额；不将此事实升级为完整成本有效。预算/协议有效仅N的8格。
- 24个原候选的source、capture snapshot及reconstructed内容/模式/类型清单一致；四任务evaluation和overlay身份保持冻结。
- 48组selectors、收集记录和JUnit完整性一致。独立复算N=6 PASS/2 FAIL，M=8 PASS，R=8 PASS；hosts的两个N失败均为未拒绝空字符串的可信保护失败。
- 24份补丁及48组JUnit/collected压缩导出与私有原件逐字节一致。206个公开文件（解压约2.02MB）的定向凭据/本机路径扫描无命中，未包含原始会话或完整index。检查仅覆盖本次有限导出。

没有发现阻断该有限Draft交付的新问题。功能验收完整不代表完整成本协议达标；没有重采样，没有后验测试语义修正，没有训练或默认晋升。

## 软件与复算验证

- 最终本地全量：`PYTHONPATH=src /opt/anaconda3/bin/python -m pytest -q`，1606 passed，47.69秒。
- `OPENSPEC_TELEMETRY=0 openspec validate --all --strict`通过。
- 新改Python执行Ruff检查与格式检查，限定diff检查；公共证据复算脚本实际运行成功。
- 私有report/replay前后SHA-256相同，零新增模型和验收调用；public replay用压缩JUnit复算功能计数及差值。

冻结前缀/获取源码为`f8826f1fa0334d6a62bb37d26c2aea1f0578d6c8`，尾程/验收源码为`c02895d396089cd9f0377e795348f180be8505d4`。交付提交只追加必要导出、复算、文档及证据；不重标旧运行。交付HEAD取本Draft PR当前head；GitHub Validate workflow检出该精确head，运行全量pytest、OpenSpec、release/diagnostic/external-pack及与PR base对比的静态非退化检查。其最终状态以对应head的Checks为准，不能用本地测试代替。

最终完整tracked delta从`b6d9316d6edd84d1a70543f290aaf3f00f7f5b90`计算；新鲜SHA-256记录保存在私有closeout证据，最终答复报告结果。不归档或删除旧研究，不合并、不ready、不发布，交付后停止自动实验。

首轮GitHub CI `36091943800`：静态集成、OpenSpec、release、diagnostic和external-pack通过，但轻量pytest有2失败、1601通过、3跳过。两项新增隔离/后备单元测试意外依赖未安装的可选tiktoken；修复仅在测试中显式注入计数器，不修改正式方法源码或冻结结果。用`sys.modules['tiktoken']=None`运行本文件6项测试全部通过。GitHub步骤的continue-on-error展示不作为通过证据，后续以原始测试结果及汇总终态核对。

CI修复提交`f44e56633db88731e960bb62776d0cb616a69d4b`的[Validate运行36092185225](https://github.com/Raidriar7170/hermes-skilleval/actions/runs/36092185225)已通过：1603 passed、3个可选测试skipped，45项OpenSpec通过，所有既有门禁完成。`ALLOW_MERGE`只是仓库软件门禁的既有字段，不授权本研究合并或晋升。后续收束记录提交仍须由它自己的精确head检查确认。

[Draft PR #56](https://github.com/Raidriar7170/hermes-skilleval/pull/56)叠加PR #55，base仍为`codex/hermes-relation-applicability-query`。首次Git推送因本机旧代理端口不可用而失败，仅以命令级`git -c http.proxy= -c https.proxy= push`恢复，未修改全局配置。最终工作树保留全部研究记录，自动实验到此停止。
