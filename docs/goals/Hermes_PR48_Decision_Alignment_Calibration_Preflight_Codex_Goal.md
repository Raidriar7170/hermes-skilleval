# Hermes Goal：决策目标对齐＋校准资格预检

> 激活本文即开始实施，内部阶段连续推进，不只输出计划，也不等待下一份 Goal。
> 主线：**复用已有权重与预测，对齐监督目标、开发选模和实际排序；把校准的结构性资格检查前移到昂贵计算之前。**
> 本轮不是新一轮全栈研究：不重训 LoRA，不训练 Gate，不扩技能库、仓库或 Agent 矩阵。
> 范围内持续授权，不逐阶段申请批准，不设置固定工程尝试次数；实际权限、费用边界、数据隔离与正常资源保护仍然有效。

---

## 0. 目标与交付定义

本轮要让 Hermes 清楚回答两个问题：

1. **这份模型为什么被选中，它被允许用什么分数决定技能顺序？**
2. **在还没训练／评分前，这批校准任务是否有可能满足规定的资格与覆盖要求？**

完成后的最小使用体验：

```text
给定任务、技能目录、现有模型候选和决策目标
    → 校验目标与受监督输出是否匹配
    → 无权重预检上下文、输入和校准结构
    → 不具备必要条件时，提前给出逐任务原因，不启动重模型
    → 具备必要条件时，允许按冻结目标选择模型和执行必要评分
    → 分开输出：建议排序、支持资格、未验证范围
```

必须交付可运行代码、现有数据上的可重算诊断、两个失资格 cal 机制组的根因说明，以及可安装的预检入口。不能只修改报告、修改状态名称或新增几个断言就结束。

本轮不要求阈值一定出现，也不承诺修复率提升。**工程对齐完成、校准结构可行、支持阈值验证成立、实际补丁效用，是四个不同结论。**

## 1. 已知依据与尚待调查的部分

### 1.1 固定起点

编制本文时读取了 PR #48 和当前实现，身份为：

```text
repository: Raidriar7170/hermes-skilleval
branch: codex/hermes-repo-aware-cost-routing
pull_request: 48
reviewed_head: db5c9d0c8ad06ed58b13ac33e9581cd7842e5b5b
inherited_base: e7535896137b7e58fb55de52cc34e94b1afd5ff4
pr_state_at_read: open / draft / not merged
```

开始时重新核对远程与本地；上述 SHA 用于定位，不要求 reset 到旧版本。存在用户修改或新提交时保留它们，识别已有同类修复，不覆盖不相关工作。

### 1.2 来源支持的事实

- 当前 pointwise 研究有两个 LoRA 候选、每个三个 epoch：`lambda_spec=0` 仅直接监督适用性，`lambda_spec=1` 同时直接监督适用性和条件特异性。[R1][R4]
- 原协议按 model-dev 适用性 log-loss 选中 `lambda_spec=0 / epoch 3`，而默认优先级使用 `p_app × p_specific`。这是公开设计，不是数据篡改。[R1][R3]
- 两个输出来自共享 causal 模型的不同 instruction，不是两份独立随机分类头。无辅助候选的特异性输出可能保留底座能力，但没有本轮直接特异性监督。[R1]
- 旧 cal 只有两个上下文合格机制组，操作点规则要求至少三个被接受机制组，阈值为 null。[R1][R5]
- 当前 `calibrate()` 在获得模型分数之后才汇总资格，并输出 `INSUFFICIENT_ELIGIBLE_GROUPS`；因此本可更早发现的结构性阻塞没有前移。[R3]
- 旧 check 四组已被模型评估与人工阅读；本轮可以做后验分析，但不是新的独立确认。[R1]

### 1.3 不得预先假定的结论

上一轮审阅没有完整定位两个失资格组的全部原因。不要预设它们都是预算错误、都能够修复，或只需把 `partial` 改为 `usable`。

不能因为 joint 在旧 check 上某项指标更好，就宣布 joint 是新的独立最优模型；不能因为新模型 AUC 较高，就宣布概率可靠或任务修复有效。

后文的模块、接口和选择规则是本轮新增设计，不是声称旧仓库已经具备它们。

## 2. 执行授权与范围边界

允许读取项目、已有合法公开任务源码、旧训练产物和必要官方文档；在隔离工作区修改本轮代码／测试／配置／文档；安装用户态依赖；使用已有本地模型进行必要的非训练推理；拟合低维校准器；本地提交、正常推送同分支并更新 Draft PR #48。

不重复申请阶段、安装、读取、评分、修补、测试或推送批准。不设置固定 retry/review 次数，不把一次普通失败当成必须重新建立 Goal 的理由。连续失败应改变排查方法，不能机械重试。

严格不做：

- 不修改六个旧 LoRA checkpoint、原 rank adapter、旧 Gate 或已冻结研究记录；不重新训练神经模型。
- 不新增付费服务、API充值、GPU实例；不将旧连接配置当作公司资源的持续授权。
- 不修改全局 Codex 配置、技能目录或 hooks，不绕过操作系统／客户端权限。
- 不修改用户原任务仓库，不清理无关进程或文件。
- 不增加新仓库、新技能、新标签体系、动态 K、RL、多 Agent 或新的通用评测平台。
- 不启动新的修复 Agent 实验；本轮 `runtime_effectiveness=NOT_RUN` 是预期范围。
- 不 force push、不合并、不设 auto-merge、不 ready、不发布模型／包、不向第三方上游提交改动。

文档不能授予客户端尚未授予的权限。遇到不可解决的外部资源问题，交付可做部分和具体证据，不索要或输出 token，不反复申请同一授权。

## 3. 先冻结本轮的小范围协议

读取 `AGENTS.md`、上一轮审阅、当前 usage 与相关源文件后，写一份短协议并立即实施。

协议明确：

- 旧数据：24个任务、10项技能、240行弱标签，目录与旧分区不改。
- 旧六个 checkpoint：候选集合固定，模型参数不变；不临时搜索其他底座。
- 本轮目标：`applicability` 与 `task_specific` 分别定义，不自动混成一项分数。
- 分析性质：`RETROSPECTIVE_DIAGNOSTIC`，尤其旧 check 不升级为独立验证。
- 新输出放入 `objective-alignment-v1`，引用旧文件而不复制整套旧产物。
- 执行资源：默认先做 records-only 与 no-forward 预检；只有输入或候选分数确有缺口，才进行必要推理。

不要为了完成这份小范围协议，另造审批系统、工作流数据库或完整性平台。

## 4. 工作顺序

| 阶段 | 主要工作 | 必须留下的实质结果 |
|---|---|---|
| A0 | 复现原模型选择和优先级 | 旧语义可重算，新语义未覆盖旧表 |
| A1 | 建立明确的决策目标 | 模型候选、开发准则、排序、过滤彼此一致 |
| A2 | 校准资格前置检查 | 无模型分数也能识别旧 cal 的必要条件不足 |
| A3 | 跟踪失资格原因并局部修复 | 两个实际机制组的文件／片段／规则证据 |
| A4 | 开发选模与后验对比 | 同一目录上的适用性、任务特定、固定与原 rank 表 |
| A5 | 安装、调用链与回归 | 预检接入真实 CLI；失败发生在模型构造之前 |
| A6 | GitHub交付 | 同 HEAD CI、紧凑证据、使用入口和一页结论 |

A2 的初步结果应尽早产生，不等待 A4 的新排序结果。普通根因修复后继续，不停在“已经发现两个问题”。

## 5. A0：复现旧语义，不先改结果

优先读取：

```text
artifacts/conditional-applicability-v1/model-freeze.json
artifacts/conditional-applicability-v1/training-*-dev-*.json
artifacts/conditional-applicability-v1/check-predictions.jsonl
artifacts/conditional-applicability-v1/calibration.json
artifacts/conditional-applicability-v1/tasks.json
artifacts/conditional-applicability-v1/labels.jsonl
configs/conditional-applicability-v1/protocol.json
src/hermes_skilleval/repo_routing/applicability_cli.py
src/hermes_skilleval/repo_routing/applicability_eval.py
src/hermes_skilleval/repo_routing/pointwise_support.py
```

按 `row_id`、任务、模型身份显式连接，不依赖文件恰好同序，不把别名当成独立模型。核对所有候选的监督轴、开发预测、输入版本和 epoch，复算原选模结论。

逐任务输出旧乘积顺序、`p_app` 顺序及原 rank 顺序。给出至少一个实际完整候选列表，例如旧 csv-diff #39；不要只选择发生有利变化的两行。

记录层必须区分：保存分数的算术重算、重新 tokenization、新模型 forward。没有 forward 的记录不得叫新推理或重载验证。

缺少某个旧 checkpoint 的 check 分数时保留缺失；不为了凑表无条件补跑全部 check。开发选择所需预测缺失，才允许按固定候选补充必要评分。

## 6. A1：用两个明确目标替代隐式乘积

### 6.1 目标 A：适用性建议 `decision_target=applicability`

用途：尽量优先提供具体适用的技能，不声明已经选出最有任务特异性或最有修复收益的组合。

- 监督对象：已知 `APPLICABLE / NOT_APPLICABLE / CONFLICT`；UNKNOWN仍不当负例。
- 模型选择：固定候选中，按 model-dev 已知标签的机制组宏平均适用性 log-loss 最小；相同到预定数值容差时，依次用适用性 Brier、候选ID和epoch作确定性 tie-break。
- 排序：只按该候选的适用性 logit 或其单调 sigmoid 排序，K=2。
- 过滤：如要称为“受支持选择”，单独使用与候选、输入和资格规则绑定的适用性校准阈值。
- 不读取特异性分数决定顺序；在线 `applicability` 请求不应多做一次特异性 forward。

joint 候选可以参加适用性选模，但不能由于名称为 joint 就自动优先。新模型没有超过便宜基线时，仍照实报告。

### 6.2 目标 J：任务特定优先级 `decision_target=task_specific`

用途：在有限两个位置中优先建议适用且针对当前任务的技能。这是文本标签目标，不是修复收益目标。

新主路径只允许有直接适用性与特异性监督、且相应监督分母非零的候选。旧无辅助模型的特异性输出只可保留在明确标记的 legacy／消融诊断，不作为新的默认可靠信号。

保留原乘积作为一个待检验的明确定义：

```text
q_specific = sigmoid(z_app) * sigmoid(z_specific_given_applicable)
```

为了对齐“用什么分数选”与“为什么选这个模型”，本轮对已有 joint 候选采用以下开发选择约定，不引入新训练头：

1. 从原两轴标签派生事件标签：已知不适用→0；适用且通用→0；适用且任务特定→1。
2. 适用性未知，或适用但特异性未知→该事件未知，不填0。
3. 用与实际排序相同的原始 `q_specific`，计算 model-dev 机制组宏平均联合事件 log-loss。
4. 该 loss 最小的 joint 候选作为本轮目标一致的开发候选；平局依次看更低已知不适用@2、更高特定P@2、候选ID与epoch。
5. 若开发集没有足够已知任务特定正例／负例，返回选择依据不足，不让另一目标的赢家冒名顶替。

这是本轮对旧开发数据的重新分析约定，不是重写上一轮预注册协议。不得将根据旧数据设计的新规则称为完全未经观察的实验。

`q_specific` 在本轮只叫 priority score。两轴并未都可靠校准时，不将其称为联合成功概率。可以用适用性校准做资格过滤，但**不能悄悄把排序从原始 q 改为校准后 p_app 乘原始 p_specific**；后者可能改变顺序，需要另命名的开发变体，默认不做。

### 6.3 不自动选一个“总冠军”

本轮输出两个目标各自的开发候选和取舍，不把 Brier、AUC、特定P@2拼成未定义总分。

默认运行策略继续为 native。显式适用性建议采用 A；显式任务特定建议采用 J。不能因旧 check 的某一列更好而互换用途，也不能将“任务特定”视为必然优于通用调试流程。

### 6.4 原 rank＋过滤另作一条对照

保留原 rank 的顺序，由适用性支持阈值过滤其候选，这条路径仍叫 `rank_plus_support`，不能同新 q 排序混为 C2。

原 rank 的1024-token输入与新支持模型的8192-token输入不相同。比较时披露这一差异，不把分数不同全部归因于新决策规则。

## 7. 决策合同：小而明确，不是新框架

使用一个轻量配置对象即可，字段至少包括：

```json
{
  "schema": "decision-alignment-v1",
  "decision_target": "applicability",
  "candidate_id": "FROM_DEV_ONLY",
  "epoch": null,
  "required_supervised_axes": ["applicability"],
  "selection_metric": "group_macro_applicability_log_loss",
  "ranking_formula": "sigmoid_applicability",
  "k": 2,
  "support_mode": "advisory",
  "input_identity": "BOUND_AT_EXECUTION",
  "calibration_ref": null,
  "analysis_scope": "RETROSPECTIVE_DIAGNOSTIC"
}
```

上面是新增配置示例，不能把占位值作为有效配置运行。

验证要求：

- 目标、候选监督轴、排序公式、校准轴匹配；不支持的组合在评分前拒绝。
- `advisory` 可以返回排序，但 `accepted` 不得因此为true；不自动调用 Agent。
- `supported` 必须通过共同资格函数和已绑定阈值；无阈值不得偷偷退化成固定Top-2后标supported。
- 模型／输入变化后校准身份失效；旧Gate绑定不变，新分支不可冒用旧反馈。
- JSON声明不等于执行：把公式ID、读取的输出轴、实际模型身份写进每次结果。

## 8. A2：两层资格预检，先于昂贵计算

### 8.1 第一层：结构预检，不访问标签或模型分数

输入只含公开请求、源码快照／片段、技能内容、环境事实、模型输入规格、协议与机制ID。机制ID用于分组计数，不能作为预测特征。

逐任务／逐候选检查：

- 来源版本、必需文件和声明片段是否可获得；是否有跨目录、符号链接或非授权输入。
- 上下文状态及明确原因，关键与非关键缺失分别列出。
- 请求、指令、技能证据与必要上下文是否能按当前输入规格呈现。
- 明确冲突、已知环境与模型依赖需求是否满足；未获取的事实保持UNKNOWN。
- 分组是否重叠、记录是否完整、同一任务多行是否被误当多个组。

只做目录与配置检查时不构造模型、不读取多GB权重来算摘要、不运行训练脚本。

精确token预算可以使用已有绑定的token记录，或本地tokenizer-only路径。tokenizer缺失时明确 `TOKENIZATION_UNCHECKED`，不调用LLM猜长度；字符串长度只能作为估计，不能认证token完整性。

### 8.2 第二层：校准可行性预检，允许读取cal标签，但不读取概率

在选模已冻结后，由可信校准控制器读取cal标签及结构资格，计算已知正负数量、机制覆盖和规则的必要条件。标签不传给模型或在线runtime。

必要条件至少包括：

```text
有资格且已知标签的机制组数 >= min_accepted_groups
有资格且已知的候选行数 >= min_accepted_rows
有资格已知行的最大可覆盖权重 >= min_known_coverage
每个实际要拟合的轴具备 min_axis_groups 与 min_each_class
数据分区与模型／输入身份可匹配
```

注意：`min_accepted_groups` 的旧语义是被接受的已知标签机制组，不得暗改为“至少三个正例机制组”。UNKNOWN不能用来凑已知组、已知行或class数量。

A路径只要求适用性轴；缺少特异性校准标签不应无条件阻断A。J路径若未校准特异性，只能报告原始priority，不能声称该轴概率已校准。

结构预检结果最多说明 `NECESSARY_CONDITIONS_MET`，不是 `OPERATING_POINT_VALIDATED`。即使上面全部满足，真实分数仍可能找不到达到精度要求的阈值。

如果输出额外的“乐观上界”，必须注明它忽略了分数次序，是必要条件分析，不能当作真实阈值存在证明。

## 9. 先用旧cal明确复现不可行性

旧cal的四个任务可从冻结splits定位：

```text
sqlite-utils-issue-211
sqlite-utils-issue-236
csvkit-issue-1148
csv-diff-issue-31
```

以实际文件核实ID与分区，不根据上列名称推测哪个任务失败。

交付一张完整表：每个任务的原状态、关键缺失、受影响候选数、token资格、环境条件、已知标签数、可贡献的机制数及来源引用。

第一次预检必须能够在**零scorer调用**下说明：旧cal最多只有两个上下文合格组，不可能满足至少三个被接受组。该结果是对旧配置的可重现诊断，不依赖读取已经算过的cal预测来做决定。

必须进一步分解其他约束：例如适用性映射能否拟合、特异性映射为何不足。不要把多个前提缺失全部归到一个模糊的“模型不行”。

## 10. A3：沿真实数据追踪失资格根因

对于实际两个失资格组，沿以下链条追踪：

```text
公开请求中的文件／符号／条件
    → 源码快照版本与文件实际内容
    → extract_fragments 的扫描／命中／裁剪
    → critical / missing / partial 的原因
    → 结构化token分配与实际可见片段
    → 资格函数的最终判断
```

输出“问题在哪里、为什么触发、是否真正阻止判断、怎么最小修复”。检查旧存档可支持的范围；本地原快照找不到时明确无法认证，不拿当前最新版源码代替。

允许的局部修复例子仅是调查方向，不是已确认问题：

- 程序把方法调用、选项或普通标识符错误地当作必须存在的函数定义。
- 关键函数在大文件中存在，但固定前缀／片段预算未提取到必要窗口。
- 非关键邻近文件缺失被错误升级成全局阻塞。
- 元数据表明片段可用，实际token却没保留相关条件。

修复必须是面向输入结构的通用规则，不能按 `task_id` 放行。不得删除预算、把所有partial都改成usable，或因为“增加一组刚好就过门槛”而改变判定。

新增回归同时包含：应被修复的输入、真实关键缺失仍拒绝、超预算明确报告、路径逃逸／未授权输入仍拒绝。语义确实不明的任务继续保留不合格。

## 11. 上下文可用性与建议风险分开，但本轮不偷换策略

文本上可讨论“这份技能可能有帮助”，不等于环境已经足够支持自动执行。可提供以下分开的结果：

- 文本排序建议：在有限公开信息上给出排序，标明缺失和不确定。
- 支持资格：是否满足当前预先声明的输入与校准条件。
- 执行资格：是否满足仓库安装、允许命令和文件权限等要求。

不要为了获得非空supported集合，把“低风险建议”重新定义成原来的严格支持结论。本轮保持旧严格规则作兼容对照，建议路径可用，但不能以建议路径取代支持验证。

若认为保守定义本身不适合当前产品，写清后续协议设计建议。本轮不因观察到旧结果而临时修改0.90精度、三个组或其他门槛。

## 12. 预检必须接入真实调用链

优先扩展现有 `hermes-applicability`，不只写一个没人调用的脚本。以下为建议的新子命令职责，当前尚未实现：

```text
hermes-applicability decision-replay   # 已保存分数的目标一致性重算
hermes-applicability select-for-goal   # 仅model-dev选候选并写决策合同
hermes-applicability preflight        # 结构＋可选cal标签预检，无forward
```

名称可按当前CLI风格微调，最终usage必须给出实际验证过的命令；不得在交付中保留不存在的参数。

新协议的 train／score／calibrate入口在重模型构造之前调用相应预检；records-only历史重算入口继续按原语义读取，不强迫旧数据通过新标准。

按调用目的区分阻塞范围：开发分数诊断／advisory只检查其输入和资源，不因“尚无校准阈值”被错误禁止；用于建立受支持操作点的cal评分才要求整个校准必要条件满足。训练入口若以后被调用，选模冻结前只执行结构与fit数据合法性检查，不借资格检查提前读取cal/check标签。本轮不运行训练。

预检报告应同时包含 `requested_operation`、该操作适用的检查与阻塞原因。不能用一条全局FAIL把本来仍可开展的存档分析和目标对齐工作全部停掉。

预检与runtime采用同一份资格判定函数。当前离线资格检查和runtime的 `environment_known` 等条件可能位于不同路径，应核对实际行为，消除同输入被两套谓词判出相反结果的情况，不预设已经存在具体错误。

纯轻量路径不要求Torch/Transformers/PEFT。精确tokenizer-only能力单列为可选资源；即使需要tokenizer，也不能构造语言模型或联网自动下载权重。

预检失败时进程返回明确的非零码和机器可读原因，同时保留诊断文件；“成功生成失败报告”和“具备实验资格”不能共用一个误导的成功状态。

## 13. A4：有限的目标一致性分析，不重新铺十几臂实验

对同一批候选与已保存预测，至少给出：

| 路径 | 模型选择依据 | 排序依据 | 是否认证支持 |
|---|---|---|---|
| 旧legacy乘积 | 原model-dev适用性loss | 原选中模型两轴乘积 | 保留历史语义 |
| A：app-only | model-dev适用性loss | p_app | 另有有效阈值才可 |
| J：joint-specific | joint候选的model-dev联合事件loss | 同一q_specific | 另有有效阈值才可 |
| 固定技能 | 原fit/dev固定组合 | 不读当前任务 | 不伪造概率 |
| cheap_text / skill_prior / skill_only | 原fit/dev冻结模型 | 与对应目标一致 | 仅在自身校准成立时 |
| 原rank / rank＋支持 | 原冻结rank | 保留原顺序 | 过滤结果单列 |

便宜基线也应使用对应目标的分数；不得把只按适用性选过的旧文本超参数，悄悄当作任务特定目标已优化的强对照。先明确“旧冻结基线”，必要的新开发选择仅基于fit/model-dev并另命名；不按check重新拟合。

每条路径分开报告：适用性Brier/log-loss/AUC、联合事件指标、特定P@2/R@2、已知不适用@2、UNKNOWN@2、选满K的比例、实际候选ID。

不使用一个综合数字宣布全局赢家。A路径选了通用但适用的技能，是该目标的可能正确行为；不因此标算法失败。J路径选择更特定技能但引入更多不适用项时，必须同时展示风险。

新开发选择得到的checkpoint如果没有旧check分数，只标缺失或在必要的有限推理中补列“后验评分”，不能根据已有check哪一个表现好来选checkpoint。

## 14. 指标与监督数据必须保持同义

联合事件标签只是现有标签的确定性派生，不是新增模型标注。非适用项为联合事件0，不代表能把它的条件特异性轴填0；两个统计问题分开。

UNKNOWN继续遮罩，任务没有特定正例时仍进入P@2分母，R@2为未定义并报告覆盖。按机制组宏平均，不用行数放大独立样本量。

固定Top-2、缺额集合和回退N分开。回退暴露全目录不能叫严格K=2；支持筛选无接受时，precision为null，不能填1。

正确保留训练阶段冻结的全局／技能先验。检查集自身prevalence只能标为事后常量参考，不作为已部署对手。

四组check的小样本区间只用于描述。bootstrap退化为零宽区间，不证明等价、非劣或安全；没有新Agent运行，不输出修复成功率或在线降本结论。

## 15. 重新输入／评分／校准时的身份规则

默认使用原始存档完成分析，不重写旧记录。若A3改变了上下文或token输入：

1. 同一旧checkpoint的参数未变，但新输入产生的是新scorer版本；新的上下文、模板与参数单独记录。
2. 原分数只用于原输入；不能把旧logits配上修复后的 `usable` 标记以省掉重算。
3. 文本标签是否仍适用需检查：原文和已知条件没变，可保留旧弱标签但记录输入变更；新增事实改变适用解释时，标需重审，不默默改标签。
4. 旧calibrator只能配原输入／模型身份；新输入必须在预检必要条件成立后，另存必要评分与校准结果。
5. 旧check已看过，修复后重评分仍是后验诊断。即使出现阈值，也不能当作新的独立操作点验证。

必须先冻结新规则，再运行允许的新评分；若前置资格仍不足，不继续大量评分。没有本地旧checkpoint时，交付存档分析和资源缺口，不偷偷重训一个替代物。

## 16. 是否需要新cal/check数据？本轮默认不需要

本轮交付是可工作的决策合同与预检能力，不以建立新独立泛化结果为前提。

因此不扩充新仓库／技能／标签，不为凑三个组把check移入cal，不把同一任务换措辞当新机制，不用一个新有利任务直接补足旧失败协议。

若既有两个问题都是真实信息不足，无法按原公共输入修好：预检应准确阻断，给出准备下一份数据的明确要求，但继续完成A1、A4、A5的软件工作。

后续独立验证才需要在新规则下、模型分数未知时选定新校准／检查来源。只提交一个简短后续说明，不自动开始它，也不要求用户现在提供人工授权或补标签。

## 17. 必须通过的回归与反例

### 决策一致性

- 在 A 模式任意扰动存档 p_specific，不改变排序；实际单轴推理不调用特异性分支。
- `lambda_spec=0` 用于新的 task_specific 主策略时，在模型构造前拒绝；显式legacy诊断仍能重算旧结果。
- J 选模使用与J排序同一q；调换候选记录顺序不改变选择。
- cal/check标签或分数改变，不影响只接受model-dev输入的选模函数。
- 不把未定义的特异性标签当general，不以模型名称推断监督充分性。

### 资格预检

- 两个合格组、规则需三个：零forward、零重模型构造，明确返回不可满足。
- 行数足够但机制数不足，不能通过；同族改写不增加组数。
- 结构满足但已知类别／映射轴不足，分开报告；A不因不使用的特异性轴不足被误阻断。
- 结构满足仍可能无阈值；预检不能返回“90%精度已保证”。
- 关键事实缺失保留拒绝；非关键缺失处理有证据，不做全局强制usable。
- 模型分数变动不影响结构预检结果；预检不访问参考patch或隐藏测试。
- 本地tokenizer缺失／token覆盖未知不能显示全部已验证。

### 一致性与兼容

- 预检与runtime使用同输入时，共享资格字段一致；在线路径不得读取标签／quote_refs。
- 上下文、模板或模型身份改变，旧预测／校准拒绝绑定。
- 历史records命令仍按旧协议重算，不因源码新增而覆盖或偷偷迁移旧结果。
- 在没有重ML依赖的新环境里运行records与结构预检；用构造器spy验证失败分支零重调用。

测试数不是成绩目标；覆盖这些行为即可，不为凑数量拆碎测试。

## 18. 建议文件组织与可复用边界

沿当前结构最小修改，可以新增一至两个职责明确模块，不要求逐项照搬文件名：

```text
src/hermes_skilleval/repo_routing/decision_contract.py
src/hermes_skilleval/repo_routing/calibration_preflight.py
现有 applicability_cli.py / applicability_eval.py / pointwise_support.py 的最小接入
现有 context.py / reranker.py 的必要输入缺陷修复
configs/decision-alignment-v1/protocol.json
artifacts/decision-alignment-v1/
docs/repo-aware-routing/decision-alignment-v1/
tests/test_decision_alignment.py
tests/test_calibration_preflight.py
```

现有`hermes-applicability`已是安装入口，应扩展它而非另造一套运行平台。[R6]

若旧freeze将整个实现文件绑定为历史源码，优先用薄分发包装接入新子命令，旧子命令仍委托旧模块；尽量不改旧已绑定文件。不为加一个命令就复制整个历史runtime，也不把更新全部旧哈希作为兼容方案。

历史源码哈希与当时实验的意义继续保留。新代码可调用现有数学函数，但历史重算若绑定旧源码，应使用已有冻结还原机制或只读兼容路径；不靠删除身份检查让记录通过。

## 19. 输出保持紧凑

建议只生成下列几类新结果：

- `decision-contracts.json`：两个目标、监督轴、开发选择、排序公式和冻结身份。
- `dev-selection.json`：六个旧候选的同目标开发比较，不含check驱动决策。
- `ranking-replay.json`：完整候选与逐任务排序、各轴指标、旧check后验标记。
- `calibration-preflight.json`：四个cal组的必要条件、零调用证据与根因。
- `context-repair.json`：确有修复时的输入前后差异；无修复时写明理由。
- `validation.json`：实际测试、安装、有限新推理与未运行范围。

不复制大份旧`tasks.json`、每条相同技能正文和全部token ID。引用旧路径／摘要；代表性失败保存必要可见片段和token计数即可。模型权重和私密trace不进Git。

文档至少包含：一页结果、真实使用命令、两个资格问题的原因、一个模型选模／排序错位案例、一个不应放行的反例，以及未证明的能力。

## 20. GitHub交付

继续 `codex/hermes-repo-aware-cost-routing` 和 Draft PR #48。先确认实际状态；若所有者已改变分支基线或合并，不重写历史，使用独立增量分支并清楚说明。

将本文件保存到：

```text
docs/goals/Hermes_PR48_Decision_Alignment_Calibration_Preflight_Codex_Goal.md
```

审阅入口建议：

```text
docs/repo-aware-routing/decision-alignment-v1/review-index.md
```

PR正文新段落置于旧研究之前，明确本轮是目标一致性与预检改造，旧原始实验状态保持不变。

完成相关测试、历史records、干净wheel与命令运行后，推送必要代码和紧凑证据。读取新HEAD对应的CI，而不是引用旧绿灯；公开可直接读的结果与重算命令，不以截图或ZIP代替GitHub交付。

GitHub写权限失败时，可使用本机既有合法git/gh连接；不得索要密钥、扩大账号权限或上传别处。失败时准确记录发布待完成，不声称已经推送或评论。

## 21. 完成与停止条件

### 本轮工程完成至少需要

- 原错位可从保存预测重现，两个新目标的输入、监督、选模和排序合同可运行。
- 旧cal的结构性不足在零scorer调用下可复现，并定位两个失资格机制组的具体原因或原资产缺失边界。
- 真正可修复的输入问题已作局部修复；不能修复的仍明确拒绝，不能停在泛泛建议。
- A与J开发候选选择、便宜基线和原rank诊断均能重算；旧check只作后验分析。
- 预检接入实际安装CLI，在昂贵路径之前生效；共用资格函数有回归。
- 历史结果未改写，新版本CI与GitHub交付可检查。

分别报告，避免用一个COMPLETE覆盖所有结果：

```text
engineering: COMPLETE | PARTIAL
objective_alignment: IMPLEMENTED_AND_TESTED | PARTIAL
calibration_preflight: NECESSARY_CONDITIONS_MET | BLOCKED | UNVERIFIED
supported_operating_point: NOT_ESTABLISHED | RETROSPECTIVE_ONLY
runtime_effectiveness: NOT_RUN
publication: PUSHED_DRAFT_PR | PENDING
```

预检得到BLOCKED可以是本轮检测工具的正确结果；但两个实际原因没有调查、决策合同没有接入时，不能只凭报告BLOCKED称工程完成。

如修复后旧数据能够产生阈值，只标 `RETROSPECTIVE_ONLY`，不默认晋升，不启动新的Agent矩阵。结束时给出“继续用哪个用途明确的建议入口、还有哪些资格／证据需要未来补充”，不要自动再开训练阶段。

## 22. 与算法含金量有关的最终走读

用两页以内讲清一个实际例子：

1. 旧模型为什么因适用性指标被选中，却被拿去做双轴排序。
2. 目标A与目标J分别如何选择候选和产生不同建议，各自不承诺什么。
3. 为什么两个合格校准组不能满足三个组的规则，如何在花费模型计算前知道。
4. 局部上下文修复解决了什么真实缺失，哪些情况仍应保留未知。

这份走读应引用真实配置、分数与输入，不写成虚构的修复率提升。用户是否已掌握这些内容保持 `NOT_ASSESSED`，不能由Codex替用户宣称熟练。

## 23. 依据与来源

[R1] 本对话文件：`Hermes_PR48_Pointwise_Learning_Review.md`，重点为第4、6、7节。若本地未找到，使用下列固定源码和结果核对，不杜撰审阅内容。

[R2] PR #48，编制时HEAD为 `db5c9d0c8ad06ed58b13ac33e9581cd7842e5b5b`：
https://github.com/Raidriar7170/hermes-skilleval/pull/48

[R3] 当前模型选择、评分与校准调用链：
https://github.com/Raidriar7170/hermes-skilleval/blob/db5c9d0c8ad06ed58b13ac33e9581cd7842e5b5b/src/hermes_skilleval/repo_routing/applicability_cli.py

[R4] 原pointwise协议与监督配置：
https://github.com/Raidriar7170/hermes-skilleval/blob/db5c9d0c8ad06ed58b13ac33e9581cd7842e5b5b/configs/conditional-applicability-v1/protocol.json
https://github.com/Raidriar7170/hermes-skilleval/blob/db5c9d0c8ad06ed58b13ac33e9581cd7842e5b5b/src/hermes_skilleval/repo_routing/pointwise_support.py

[R5] 结果、校准与分区：
https://github.com/Raidriar7170/hermes-skilleval/blob/db5c9d0c8ad06ed58b13ac33e9581cd7842e5b5b/docs/repo-aware-routing/applicability-learning-v1/results.md
https://github.com/Raidriar7170/hermes-skilleval/blob/db5c9d0c8ad06ed58b13ac33e9581cd7842e5b5b/artifacts/conditional-applicability-v1/calibration.json
https://github.com/Raidriar7170/hermes-skilleval/blob/db5c9d0c8ad06ed58b13ac33e9581cd7842e5b5b/configs/conditional-applicability-v1/splits.json

[R6] 已有安装入口：
https://github.com/Raidriar7170/hermes-skilleval/blob/db5c9d0c8ad06ed58b13ac33e9581cd7842e5b5b/pyproject.toml

以上支持“旧实现做了什么”。新的选择准则、preflight接口及本轮范围是本文提出的开发要求，不是上游既有结论。编制本文只读取了审阅材料与相关源文件，没有重新训练、运行完整测试或推送新代码。

## 24. 可直接粘贴的启动提示

```text
读取并执行 Hermes_PR48_Decision_Alignment_Calibration_Preflight_Codex_Goal.md，
作为本轮完整Goal，保存到docs/goals/同名文件。

继续codex/hermes-repo-aware-cost-routing与Draft PR #48，
核对实际HEAD，保留用户改动和旧研究记录，不回退main、不改PR #47。
直接实施，不只输出方案；本次持续授权范围内读取、开发、隔离安装、
必要非训练推理、校准、测试、修复及GitHub交付。
不逐阶段申请批准，不设置固定工程尝试次数。

本轮只做决策目标对齐与校准资格预检：
复用现有六个checkpoint和预测，将适用性与任务特定选择分开；
目标、直接监督、model-dev选模和实际排序必须一致。
无辅助特异性乘积保留为旧诊断，不冒充新的可靠主策略。

在重模型构造前核对上下文、token资格、已知标签和机制组必要条件，
用零forward预检复现旧cal两组无法满足三组门槛，
定位实际失资格原因，仅修复有依据的通用输入缺陷。
不降低标准、不将partial强改usable、不通过task_id放行。

旧check只用于后验诊断，不据它换checkpoint或校准阈值。
修复输入后不要混用旧logits和旧calibrator；新身份、新结果另存。
不重训LoRA或Gate，不增加仓库、技能、标签或Agent矩阵。
无独立有效操作点就保留未建立，不强迫非空，也不重复fallback smoke。

交付可安装CLI、实际回归、逐任务资格表、目标对照和紧凑证据，
推送同分支，核对同HEAD CI，更新Draft PR。
不force、不合并、不发布、不改全局配置、不新增付费资源。
完成后报告工程、资格和证据范围，停止自动扩张。
```
