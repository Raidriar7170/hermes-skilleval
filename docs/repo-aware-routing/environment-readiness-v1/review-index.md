# 混合正文／代码与环境资格闭环

本轮修复了真实提取链中的误放行，建立了四个固定版本的隔离环境事实，
并在必要条件满足后完成冻结 A 的 40 行评分和后验校准。
**阈值仅为 RETROSPECTIVE_ONLY；修复效果仍为 NOT_RUN。**

| 层次 | 本轮结果 |
|---|---|
| mixed_content_fix | VERIFIED：原始位置判断；真实／歧义调用保留 |
| environment_validation | VERIFIED_FOR_SCOPE：四版本安装、导入、依赖、入口、必要特性、隔离实测 |
| strict_preflight | NECESSARY_CONDITIONS_MET：4组、40行文本／token完整 |
| calibration_execution | EXECUTED：冻结 A，无新训练或模型选择 |
| supported_operating_point | RETROSPECTIVE_ONLY：旧 cal 同样本拟合／选点，无独立确认 |
| runtime_effectiveness | NOT_RUN：0次修复 Agent 调用 |

交付检查见 [validation.json](../../../artifacts/environment-readiness-v1/validation.json)；
代码 HEAD `16f55c0e2d3627080edb9d7825afd2ecb269e1a1` 已通过 [CI 35150447315](https://github.com/Raidriar7170/hermes-skilleval/actions/runs/35150447315)。最终文档提交的同 HEAD CI 以 [Draft PR #48 checks](https://github.com/Raidriar7170/hermes-skilleval/pull/48/checks) 为准。

## 1. 反例与修复

[修复前](../../../artifacts/environment-readiness-v1/mixed-content-before.json)直接在
临时 Python 源码上运行 `extract_fragments → extract_repaired`：正文和代码同时出现
`warning` 时，两种代码形式都错误删除关键 missing，并输出 usable。这不是 mock
结果，也不证明四条历史真实任务已遭误放行。旧测试把正文、代码分开，漏掉同名混合情形。

[修复后](../../../artifacts/environment-readiness-v1/mixed-content-after.json)按原始字符位置
检查每个同名调用形态；只在全部出现均属于已确认正文 span 时纠正。支持等长单／多反引号、
两类围栏、按列展开的缩进；未闭合、跨边界、复杂容器／HTML保守拒绝纠正。
可解析为 Python 表达式的括号内容，即使没有 Markdown 标记，也保留歧义。
这不是完整 CommonMark 实现，边界参考 [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/)。
原 request 不改，源码事实不增，预算、路径与 symlink 拒绝保持。
新身份为 `repo-context-prose-span-v2`；历史记录及旧实现身份不重写。

## 2. 环境事实

[要求与使用 scope](requirements.md)在新分数前固定；技能正文作为开发指导阅读，
不执行全部示例。目标仓库的安装、导入、依赖及入口仍为所有候选的必需条件。
未执行的其他工具、远程后端或可选 FTS 示例是 NOT_REQUIRED_FOR_SCOPE，不声称已安装。

| 原 cal 任务 | 固定源码版本 | 目标分发包版本 | 必需条件 |
|---|---|---|---|
| sqlite-utils-issue-211 | 0dca784dbe6b75de6e4c0da4869c0b2b9574dde4 | 3.1.1 | SATISFIED |
| sqlite-utils-issue-236 | 2c1b9f2445d0ca4ca9f30a1433b7cde8cc0f42a2 | 3.5 | SATISFIED |
| csvkit-issue-1148 | 74e6934094e0215d1a3e58f0d9e16937f1f19484 | 1.0.6 | SATISFIED |
| csv-diff-issue-31 | 33e0a5918283c02a339a1fb507fc7a9cda89a198 | 1.1 | SATISFIED |

[完整快照核对](../../../artifacts/environment-readiness-v1/source-verification.json)分别匹配
原 revision 的 git archive（51／58／177／13文件）。
[实际记录](../../../artifacts/environment-readiness-v1/environment-facts.json)包含时间、
镜像、来源、依赖清单、参数、退出状态、耗时、截断输出与逐项结论。
`pip check`仅辅助检查依赖相容性；另外检查目标分发包、版本及 `/opt/source` 导入来源。
参见 [pip 官方说明](https://pip.pypa.io/en/stable/cli/pip_check/)。

准备阶段在容器内下载公开依赖 wheel；运行阶段用固定配方离线安装、构建、探测。
容器非 root、无 host mount、无网络、只读根文件系统，仅临时目录可写。
使用前以显式本地 wheel 资产重新构建配方并匹配镜像／依赖／源码，随后重新探测。
不执行 facts 文件指定的任意镜像。Docker、固定 profile、控制程序及已取得的本地 wheel
资产是信任边界；摘要用于一致性，不认证第三方代码安全。任何布尔声明都不能代替实测。
[准备过程](../../../artifacts/environment-readiness-v1/preparation-attempts.json)保留失败原因，
包括探针参数修正、离线安装和镜像身份修正；这些不是模型失败或目标修复结果。

## 3. A 的后验结果

[预检](../../../artifacts/environment-readiness-v1/a-cal-preflight.json)与
[40行新评分](../../../artifacts/environment-readiness-v1/a-cal-preflight-scores.json)绑定相同
公共输入和环境。A 只构造适用性提示；同一准备对象用于 forward，实际 token摘要逐行核对。
39行适用性已知（10正、29负），1行 UNKNOWN；40行／4组始终保留在分母。
校准规则未改：精度0.9、至少3组、至少6已知接受行、覆盖至少0.1、未知接受为0。

[校准及完整曲线](../../../artifacts/environment-readiness-v1/a-calibration-preflight-calibration.json)
选中阈值 **0.3743495561**：接受11行、4组，其中10真／1假，0 UNKNOWN；
机制加权精度 **0.910891**，已知覆盖 **0.280556**。
Brier 0.075155 → 0.037002，log-loss 0.268343 → 0.128618，均为同 cal 后验值。
[独立进程重载](../../../artifacts/environment-readiness-v1/calibration-reload.json)重拟合并独立
重算曲线基本量、选点，结果匹配；它是软件一致性检查，不是独立泛化验证。

弱标签仍来自历史标注，未重新审核；本轮仅修正解析误报，没有改变请求、技能正文或源码事实。
旧 cal/check 已多轮观察，不声称90%真实精度、安全保证、跨仓库泛化、修复率或线上降本。
J 保持旧的双轴原始建议分数；没有建立其特异性校准。原 rank、Gate、native默认及旧研究结论不变。

## 4. 安装、成本与复盘

[使用入口](usage.md)支持 checkout 外的显式资源路径。
[干净 wheel 检查](../../../artifacts/environment-readiness-v1/installed-light-checks.json)覆盖
help、历史 records、真实事实透传、缺失事实在模型前拒绝、span修复与重型依赖导入守卫。
[固定首行复现](../../../artifacts/environment-readiness-v1/installed-first-row.json)按原 task/catalog
顺序选定 sqlite-utils-issue-211::systematic-debugging，安装入口的输入／token／logit与批量完全一致；
输出 ADVISORY、accepted=false。

[成本](../../../artifacts/environment-readiness-v1/cost.json)：40次批量forward约21.15秒，
1次安装首行复现，共41次forward、2次模型构造；校准拟合与重载各1次。
未完整记录的阶段总耗时为null，不将存活日志凑成全部在线成本；修复Agent调用为0。

主要教训是把“提取正确”“环境存在”“阈值可拟合”“独立有效”分开。此次前两项补齐，
第三项只得到后验结果，第四项没有执行。静态只读独立审阅发现的代码保护、镜像信任、超时、
输出限额及A/advisory边界问题已修复；它不替代容器实测或CI。既定范围到此停止，无训练、
新任务、旧check选点、Gate采集、merge、release或Agent矩阵。
