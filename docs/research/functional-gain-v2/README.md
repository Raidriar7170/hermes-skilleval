# ASI v2 功能结果与机制证据

## 功能主结论

**未建立功能修复增益，保持 `KEEP_EXISTING_DEFAULT`。** 8 个新测试任务、六臂、各两次，计划与记录均为 96 格；95 格有可信功能结果，1 格中断未知且未补采。H-full 与 N0 均为 16/16；任务均值差为 0，8 个任务族的描述性 bootstrap 95% 区间为 [0, 0]。这描述本样本的全通过天花板，不能证明总体等价或排除其他任务上的收益。

| 方法 | 计划/已记录 | 功能通过 | 功能失败 | 未知 | 全计划成功率下界–上界 |
|---|---:|---:|---:|---:|---:|
| N0-v2 | 16/16 | 16 | 0 | 0 | 100.00%–100.00% |
| S1-v2 | 16/16 | 16 | 0 | 0 | 100.00%–100.00% |
| P1-v2 | 16/16 | 16 | 0 | 0 | 100.00%–100.00% |
| H-task-fixedC-v2 | 16/16 | 15 | 0 | 1 | 93.75%–100.00% |
| H-myopic-v2 | 16/16 | 16 | 0 | 0 | 100.00%–100.00% |
| H-full-v2 | 16/16 | 16 | 0 | 0 | 100.00%–100.00% |

full 对静态、先验、myopic 的已测功能差均为 0。full 对 task-only 的完整配对范围为 7 个任务，差为 0；遗漏的第八任务不只取其已完成重复求均值，该对比为 `INCONCLUSIVE`。

逐任务单元格为「target 通过数 / regression 通过数 / functional 通过数；未知数」，每格计划两次：

| 任务 | N0-v2 | S1-v2 | P1-v2 | H-task-fixedC-v2 | H-myopic-v2 | H-full-v2 |
|---|---|---|---|---|---|---|
| sqlite-utils-fix-e6be626 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 |
| sqlite-utils-fix-c872d27 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 |
| sqlite-utils-fix-b962909 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 |
| sqlite-utils-fix-a7b29bf | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 |
| csvkit-fix-b2e54cd | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 |
| csvkit-fix-7bba1bd | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 1/1/1; U=1 | 2/2/2; U=0 | 2/2/2; U=0 |
| csvkit-fix-0867890 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 |
| csvkit-fix-4b0b397 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 | 2/2/2; U=0 |

## 同状态表示

8 个预选共同状态、64 条动作尾程均通过目标与保护回归。full 和独立训练的 task-only 共享候选、载荷、前缀和初始预算；预先锁定的立即增益动作在 6/8 个状态不同，但两次重复的预选动作功能值全部持平。动态特征进入计算，动作确实改变，功能价值未建立：`state_incremental_claim=NOT_ESTABLISHED`。该面板比较立即增益选择，不把未直接观测的 WAIT 策略结果当作动作表真值。

## 等待决策与真实续跑

4 个预选非终端状态执行 DEFER_SAME 和 WAIT_THEN_FULL，各两次，共 16 条真实向前尾程；均通过。立即注入和 NEVER 复用已登记面板采样，不重复计成新调用。两个 E1 状态满足当前正增益被更高等待值推迟：

| 状态 | 当前最大增益预测 | 等待预测 |
|---|---:|---:|
| csvkit-fix-b2e54cd | 0.00475925 | 0.09862330 |
| csvkit-fix-4b0b397 | 0.00368092 | 0.01531870 |

等待计算与决策影响已观察；全体 4 状态及敏感子集 2 状态中，两种延迟方式相对 NOW/NEVER 的功能差均为 0。`waiting_incremental_claim=NOT_ESTABLISHED`。DEFER_SAME 固定原技能，WAIT_THEN_FULL 还允许后续适应，不能将后者称为纯时机效应；强制机制探测也不代表在线 full 在所有起点实际选择等待。

## 普通提醒、先验与训练

32 个技能对提醒的同状态比较全部功能持平；技能对 no-op 也全部持平，没有证明技能特定知识优于额外普通提示。端到端先验 P1 为 16/16，与 full 相同。

训练侧 192 条尾程、191 可评价、1 未知；96 个技能差值为 92 持平、2 退化、2 未知，零救回。full/task-only 从初始化分别真实训练并独立重载；开发标签全零，零增益基线 MSE/MAE=0，full MSE=0.0177696、task-only=0.00251759，均未胜过零基线。等待目标采用任务族留出预测，不能将实际拟合解释成学会救回。详见 [训练诊断](learning-diagnostic.md)。

## 执行和数据限制

- task-only 的 csvkit-fix-7bba1bd 第 2 次执行中断，没有完整执行凭据；既有目录、部分输出与历史记录保留，无替换采样。功能、时间及模型调用凭据的缺失仍为未知。
- 全部登记执行格已处理，机制验收完整；严格报告仍为 `final_functional_evaluation=PARTIAL`、`study_execution=PARTIAL`、`method_upgrade=PARTIAL_METHOD`，不能写成无条件研究全部完成。
- 相同可观察前缀不等于克隆隐藏随机状态；任务数少，公开历史问题可能有预训练污染；没有测量广泛泛化。
- 未调整阈值、权重、候选或重复数追分；旧 v1 结果不重标、不复用为新测试。

## 次要合规与成本

文件策略与成本没有进入功能标签、增益/等待训练或主结论。六臂可交付数分别为 N0 14/16、S1 15/16、P1 14/16、task-only 13/16 加 1 未知、myopic 15/16、full 10/16。完整候选独立测量，没有删除违规文件后重验。

成本账本包含 392 次记录引用，去掉 4 次复用后为 388 个唯一执行目录：采集/原生/先导 212，在线最终 96，机制 80。输入 token 包含缓存，输出包含 reasoning，不能重复相加；报告的 token 是已收到通知的观测值，中断执行即使已开始轮次通知完整也不证明整次运行成本完整。采集 1 个目录无 token 统计，在线 1 个目录活动时间未知；训练协调器墙钟 21.498 秒。另有两次 matrix 协调器启动的共享编码器加载共 8.894 秒（含中断恢复）；其他阶段未单独留凭据的共享初始化耗时仍未知，不以零补齐。见 [共享初始化成本](../../../artifacts/functional-gain-v2/shared-setup-cost.json)。账单美元未知，不从 token/秒数推算。资格准备、安装、审阅、排障及编排会话不属于该执行账本，账本不是项目总账单。

## 工程与证据入口

本地全仓 1507 测试通过，OpenSpec 39 项严格校验通过，隔离安装与旧/v2 入口检查通过。独立审阅已复算通过；[Draft PR #50](https://github.com/Raidriar7170/hermes-skilleval/pull/50) 已发布，修正单行格式后的 [同 HEAD CI](https://github.com/Raidriar7170/hermes-skilleval/actions/runs/35491870013) 已通过。最终文档提交的 CI 与完整差异 SHA-256 收尾凭据以该 PR 正文及检查页为准。工程结果不改变三个未建立收益的结论。

- [交付状态](../../../artifacts/functional-gain-v2/delivery-status.json)、[实际命令与复算边界](reproduction.md)
- [完整机器报告](../../../artifacts/functional-gain-v2/final-report.json)、[次要成本账本](../../../artifacts/functional-gain-v2/cost-ledger.json)
- [主矩阵与原补丁](../../../artifacts/functional-gain-v2/matrix/records.json)、[共同状态动作表](../../../artifacts/functional-gain-v2/panels/records.json)、[延迟续跑](../../../artifacts/functional-gain-v2/delays/records.json)
- [结果前冻结的决策摘要](../../../artifacts/functional-gain-v2/panel-decisions.json)、[统一验收凭据](../../../artifacts/functional-gain-v2/release.json)
- [一页架构复盘](architecture-retrospective.zh.md)、[实际执行与恢复记录](execution-notes.md)
