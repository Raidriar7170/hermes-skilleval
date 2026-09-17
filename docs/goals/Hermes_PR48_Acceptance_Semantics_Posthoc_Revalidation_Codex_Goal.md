# Hermes Goal：验收语义复核与原补丁的后验复验

> 激活本文后直接实施，内部阶段连续推进，不等待下一份 Goal。
> **本轮只回答：上一轮的判分是否忠实反映公开需求，以及同一批原始补丁在用途明确的新检查下实际满足了哪些行为。**
> 不调用新的修复 Agent，不生成或修改候选补丁，不重新推荐技能、不训练、不校准。
> 范围内持续授权，不逐阶段申请批准，不设置固定工程排障或审阅次数；隔离、权限、费用与证据边界仍有效。

---

## 0. 一页执行合同

执行链：

```text
保存上一轮原始32格结果与补丁身份
    → 核对原始需求、实际发给Agent的题面、对应版本接口与旧检查
    → 按来源确定新检查的义务、歧义及新增覆盖范围
    → 用基线、参考和独立正反例验证新检查
    → 冻结新检查与夹具
    → 干净重建两项受影响任务的全部16份原补丁
    → 对每份运行原检查及同一套后验行为检查
    → 分别报告原判分、当前行为、检查局限与结果变化
    → 仓库外安装、零模型重算、同HEAD CI、同一Draft PR交付
```

核心规模：

- 上轮全部 **32个运行记录**：核对名单、原补丁和原JUnit，不重跑Agent。
- `csvkit-issue-1225`：N/F2/T2/J2各两份，共 **8份原补丁**，对称复验。
- `sqlite-utils-issue-368`：N/F2/T2/J2各两份，共 **8份原补丁**，对称复验。
- `sqlite-utils-issue-344`与`sqlite-utils-issue-400`的另16份：默认只核对原记录与资产，不扩大本轮语义重验范围。
- 新修复Agent调用、路由模型forward、模型训练、校准拟合均为 **0**。

16份是需要真实重建和复验的原候选数量，不是16个新任务，也不是16次新修复。测试用例、候选CLI子进程和环境检查的次数另行计量。

**不能只改报告措辞、把glob放宽或运行几个mock，就宣布原补丁复验完成。**必须实际执行可取得的原候选；缺资产或环境时如实交付部分结果。

## 1. 起点、已有依据与本轮新增设计

编制时读取的定位：

```text
repository: Raidriar7170/hermes-skilleval
branch: codex/hermes-repo-aware-cost-routing
pull_request: 48
reviewed_head: 49a7dfeb9efc8dcce112c829d4d7136c5bd281a3
state_at_read: open / draft / unmerged
original_study: advisory-utility-replay-v1
new_appendix: acceptance-semantics-v1
```

上述SHA用于定位，不要求reset。开始时核对真实HEAD、工作树、其他会话修改及`AGENTS.md`；已存在同类工作就检查并续做，不覆盖或重建用户成果。

来源支持的事实：[S1–S5]

1. 上轮完成四任务、四种技能提供方式、各两次的32次实际修复；固定检查通过数为N 5/8，其余各6/8。
2. csvkit目标只要求退出码0并出现`stdin_*.csv`，没有验证导出的完整单元格内容；局部反例中空的匹配文件也能通过。
3. N-r2的停止后诊断显示退出0并生成`-_0.csv`；这不能直接证明内容完整正确。
4. #368标题指向包入口，正文示例指向CLI子模块；旧检查只检验包入口。此前只抽查了部分实际补丁，不假定全部候选新检查结果一致。
5. 原生、固定、文本和J2之间的效果仍为`INCONCLUSIVE`；仅凭旧检查的一个差异不能宣称修复收益。

**本轮新增的是检查语义表、修订后的行为探针与对全部受影响原候选的后验复验。**下面的新增夹具、结果字段和入口不是声称当前仓库已经实现。

## 2. 原始表与新表：不覆盖历史，也不阻止纠错

明确区分：

| 层次 | 本轮处理 |
|---|---|
| 原始运行、补丁、技能、用量、旧JUnit | 保持原字节和原结果 |
| 原判分在公开需求下的解释 | 可以补充勘误、歧义和覆盖限制 |
| 新行为检查得到的结果 | 新目录、新检查版本、新执行证据 |
| 算法收益结论 | 只能描述后验敏感性，不能升级为独立提升 |

允许同一候选出现“旧前缀检查失败、新内容检查通过”，也允许“旧检查通过、新内容检查失败”。这叫**同一补丁在不同验收定义下的行为对照**，不是把旧FAIL偷偷替换成PASS。

本轮所有新结果标为`POSTHOC_REVALIDATION_OF_FROZEN_PATCHES`。原题、补丁和主要结果都已被观察，不能说新检查是在不知道候选表现时预注册的。下面的冻结只阻止继续针对候选调检查，不消除已经存在的后验性。

不得预先要求“证明N其实正确”“所有方法最终相同”或“消除J的优势”。任何来源支持的结果都应保留。

## 3. 持续授权、允许操作与禁止事项

允许：读取本项目及已有合法本地资产；取得必要公开源码与对应版本资料；在本项目隔离目录准备环境和夹具；新增小型验收/复验适配；运行既有补丁、确定性检查、回归、安装和重算；正常提交、推送本分支、更新同一Draft PR。

不重复申请计划、阶段、安装、普通修复、测试或推送批准。实际系统仍要求的权限不得绕过。工程排障不设固定尝试次数，但应有依据，不机械无限重试。

禁止：

- 新修复Agent、额外采样、补丁润色、重生成原失败候选、重新推荐技能、A/J/Gate/文本模型训练或校准。
- 为修好候选而修改其源码、补丁、依赖声明、已生成测试，或抽取“有用部分”重新拼接。
- 改写旧`runs.json`、旧原始检查、JUnit、预测、标签、推荐、旧统计及其冻结身份。
- 通过更换任务、挑一个臂、只复验失败候选或只保留最好重复来获得结果。
- 使用LLM裁判或新弱标签代替可执行语义检查；开发会话可以分析来源，但不得冒称人工或第三方盲审。
- 新购GPU/API额度、访问公司旧服务、改全局代理/Codex配置/权限、全局清理Docker、向第三方上游提交修改。
- force push、merge、ready、自动归档、发布权重/包或更改产品默认策略。

本Goal授权的“实际执行”仅指**原候选程序与控制器检查**，不是重新调用代码Agent。无需加载任何路由模型权重。

## 4. 工作阶段

| 阶段 | 实质工作 | 验收依据 |
|---|---|---|
| S0 | 读取旧32格证据，锁定受影响16份补丁 | 完整名单和不可变输入身份 |
| S1 | 公开需求、真实题面与旧检查逐项对照 | 可追溯的验收语义表 |
| S2 | 实现来源支持的新检查和独立正反例 | 检查能拒绝错误内容，也不误拒合理命名 |
| S3 | 恢复原环境，核对基线/参考，冻结新检查 | 实际执行资格与检查版本 |
| S4 | 干净重建16份原候选，对称运行新旧检查 | 每份原patch对应的真实输出和JUnit |
| S5 | 分层结果、后验转移表、安装/CI/PR交付 | 原表不变，新结果可独立重算 |

S1先于新候选结果。S2可以使用来源、原基线、参考、独立合成程序验证检查，但不能边看某个臂失败边定制让它过的规则。

S3可行就直接进行S4，不以“无新校准阈值”“不能证明涨分”为停止理由。不存在旧90%适用性门槛这一前置条件。

## 5. 资产定位与16份候选锁定

优先读取：

```text
artifacts/advisory-utility-replay-v1/runs.json
artifacts/advisory-utility-replay-v1/protocol.json
artifacts/advisory-utility-replay-v1/qualification.json
artifacts/advisory-utility-replay-v1/evidence-index.json
artifacts/advisory-utility-replay-v1/patches/
artifacts/advisory-utility-replay-v1/checks/
artifacts/advisory-utility-replay-v1/checks-source/
artifacts/advisory-utility-replay-v1/environment.json
artifacts/advisory-utility-replay-v1/task-limitations.json
```

建立一次紧凑manifest，记录：run_id、task_id、arm、repeat、原patch路径和SHA-256、base与源码清单身份、旧检查/夹具身份、原目标/回归结果、候选重建清单的可得性。

要求：

- 两个任务分别具有N/F2/T2/J2×r1/r2的全部8格；不能遗漏任一已存在候选。
- 先核对全部32格，确认另16格仅保留旧结果且不冒称已重验。
- 从原记录读取实际base和环境，不用当前main、较新的已修复版本或参考版本替代。
- 旧候选raw archive仅用于来源核对/缺失恢复，不直接信任当前目录仍等于执行结束时源码。
- 缺失文件按原引用恢复；恢复不到就标`MISSING_ARTIFACT`，不请Agent补做、不凭摘要重建一份相似补丁。
- run_id可在执行工作区中使用不含臂名的别名，但须保留映射；这降低人为差异，不宣称消除了已经看过结果的偏差。

## 6. 语义复核：首先核对Agent实际看到的需求

为每项拟新增断言记录：

| 字段 | 含义 |
|---|---|
| obligation_id | 稳定的行为义务标识 |
| public_source | 原问题/对应版本文档或接口约定 |
| source_location | 标题、正文、文件路径与版本/行范围 |
| visible_to_original_agent | YES / NO / UNKNOWN；基于实际题面记录 |
| interpretation | 明确要求、接口约定、冲突解释或新增诊断覆盖 |
| executable_check | 实际测试及预期行为 |
| limitation | 不足以说明什么 |

必须读取当时保存的公开请求和共享prompt，不能只看当前GitHub标题就认定Agent看过标题。原事件/题面缺失时写UNKNOWN，不补造可见性。

资料使用顺序：实际题面 → 对应原始公开问题 → 运行base版本的文档、help与接口 → 当时参考实现。参考实现可以演示一种实现，不自动把内部命名和编码细节变成用户义务。

后续提交、当前最新版文档、其他工具的命名习惯仅作背景，不能无说明地回填旧版本合同。无法从来源确认的要求保持`UNSPECIFIED`或`AMBIGUOUS`；不由控制器替用户强行定夺。

把“纠正过窄前缀要求”和“新增内容覆盖”分别列出，不能把新覆盖失败全部叫作原裁判已确定的误判。

## 7. csvkit #1225：从文件名前缀转向真实转换行为

先从固定版本的参数定义/help核对：`in2csv -f xlsx --write-sheets -`各参数、标准输入与所选工作表的语义。尤其不能仅凭字符`-`的习惯用法猜测它是位置参数还是选项值。

保留原命令调用形状、输入方式和原数据夹具。新核心检查至少观察：

1. 候选命令真实启动、退出码与stderr；不能用候选返回的“成功”JSON代替进程结果。
2. 在新的空工作目录中，按该命令公开语义生成预期的工作表文件。
3. 实际CSV可解析，表头、数据行、列数和单元格值与输入夹具确定的内容一致。
4. 不缺失要求导出的工作表，不拿第一张表的重复副本冒充其他表，不接受空文件代替非空表。
5. 对原文件路径输入执行同样有内容依据的基本回归，避免只修stdin却破坏原功能。

**禁止继续用`stdin_`前缀作为没有公开来源的硬性条件；也禁止简单改成`glob('*.csv')`后只检查文件存在。**

文件命名若确有对应版本公开约定，按那一条约定核对。没有约定时，名称用于定位/报告，不作为实现偏好。目录边界、合法文件类型与不得越界写入仍然独立生效。

## 8. CSV夹具、期望值与等价输出

仅准备两个有界层次，不扩大成通用Excel兼容性测试库：

- **原夹具层**：恢复旧`dummy.xlsx`或实际同身份文件，明确其工作表、非空行列及期望内容。旧字节恢复不到时，该层为UNKNOWN，不生成另一个同名文件冒充。
- **新增覆盖层**：一个确定生成的小型多工作表XLSX，默认两张有区别的非空表；使用该版本明确支持的简单字符串值与稳定内容，避免公式、日期、合并单元格等无关语义。它是后验测试夹具，不是新任务。

夹具生成输入、工作表顺序、单元格矩阵、生成器版本与文件身份在跑候选前固定。期望值来自夹具定义和接口约定，不从某个候选或参考的输出倒推。

CSV使用解析后的行/列比较，不用字节级换行差异误判；不得为提高通过率把所有字段strip、忽略数据行顺序、强制类型转换或把重复行变成集合。允许的规范化必须有明确依据并事先写入规则。

若文件名未规定、工作表与输出文件不能按名称一一对应，可使用**完整CSV内容的多重集匹配**，保留相同表/重复行的数量；新增夹具优先让两表内容可区分。不得只比较文件总数或所有CSV合并后的内容。

stdout若存在独立的默认工作表输出约定，也应单列检查；只有来源支持才列为必须满足，不假定所有导出模式具有同一stdout行为。

解析后的期望矩阵由可信控制程序持有，输出文件必须来自本次新工作目录中的普通文件，不允许追随符号链接读取其他目录。原输出文件不被复用，避免残留的CSV替当前候选通过。

## 9. #368：包入口、子模块入口与原命令入口分开

来源中的两种表述不合并成一个事后挑选的“正确答案”：

| 维度 | 需观察的行为 | 解释 |
|---|---|---|
| package_entry | `python -m sqlite_utils ...` | 标题指向的包入口 |
| submodule_entry | `python -m sqlite_utils.cli ...` | 正文示例指向的子模块入口 |
| console_entry | `sqlite-utils ...` | 原有命令行入口与保留行为 |

每个入口至少执行`--help`，再对该版本已支持的一个确定、只读的小操作作行为核对，例如对控制器建立的已知数据库列出表。具体命令与预期值须先从该版本文档/help确认，再冻结；不能为难候选增加新功能义务。

新功能性探针属于对“可作为替代入口”的覆盖检查，与原来仅测试help的范围并列披露。只打印`Usage:`、但不能执行原有操作的合成程序，不应被新功能维度判为通过。

输出必须分列：包help/功能、子模块help/功能、原命令help/功能。可以汇总每个入口自身的结果；**不要求两个入口同时成功作为唯一主成功率，也不取二者较好的结果替换旧分数。**

若实际题面仅包含正文而不含标题，报告这项可见性限制；如果两者都包含，就保留需求歧义。后验检查测得行为，不替原用户补充澄清。

## 10. 调用器必须真实调用对应入口

旧检查包装器的通用else分支调用的是`runpy.run_module('sqlite_utils', ...)`。不能仅把传入参数写成`sqlite_utils.cli`，却沿用该分支，导致三张表实际在调用同一个包入口。[S3]

新增一个小而明确的可信调用适配，或扩展新检查内的白名单调度：

- 包模式明确指向`sqlite_utils`，子模块模式明确指向`sqlite_utils.cli`。
- 原命令入口按固定版本entry point调用。
- 参数、工作目录、stdin、退出码、实际入口与导入来源可核对。
- 候选源码来源必须是本次重建目录，而非系统安装的另一个修复版本。
- 字符串`-m`、模块名和sys.argv不能被错误剥离或重复拼接。

允许使用已有受控导入器/固定runpy包装以绑定候选源码，但须用合成包证明三条路径相互独立。命令数组由程序生成，不执行issue、补丁或技能提供的任意shell文本。

## 11. 在原候选之外验证新检查

新检查先用原base、已有参考以及独立正反例验证，再冻结后跑16份候选。

必须覆盖的边界：

| 场景 | 新检查应如何处理 |
|---|---|
| 内容正确、使用不同但允许的文件名 | 内容维度通过，不因固定前缀拒绝 |
| 空的`stdin_0.csv`、退出0 | 非空工作表内容检查失败 |
| 文件存在但单元格错误/缺行/缺列 | 对应内容维度失败 |
| 漏掉一张表或复制第一张表充数 | 多表完整性失败 |
| 文件名匹配但非零退出/超时 | 不判成功，保留真实原因 |
| 无输出或输出符号链接 | 缺输出或边界异常，不算有效转换 |
| 仅实现cli.py主入口的合成包 | 子模块可通过，包入口失败 |
| 仅实现包__main__.py的合成包 | 包入口可通过，子模块按实际行为单列 |
| help只有伪造`Usage:` | help观察与功能探针分开，不能冒充完整可用入口 |
| 原命令回归失败 | 单独明确报告，不能被新入口通过掩盖 |

合成程序/受控响应只用于验证裁判，它们不是新Agent候选，也不计入16份真实复验。至少有真实XLSX转换与真实Python入口调用，不能只有mock。

参考只证明来源支持的维度：#368参考可能只实现一种入口，**不能为了让参考全绿而删除另一种维度**。如果参考与来源支持的CSV行为不一致，调查并披露，不能默认参考输出就是标准答案。

## 12. 冻结新检查，减少后验选择空间

在首次读取新的候选复验输出前固定：

- 两个语义合同、断言来源、已知歧义与实际题面可见性。
- 原夹具和新增夹具、期望内容与允许的规范化。
- 入口调用方式、源码导入验证、候选清单与复验顺序。
- 环境、检查版本、结果状态、汇总口径。

控制器已知道旧胜负，所以不要声称臂标签遮蔽就形成了盲测。实现中不允许`if arm == 'N'`、特定run_id、候选patch hash触发不同测试规则。

建议以稳定的别名顺序运行；不同候选的区别只能来自它们的原始代码，不来自测试选择和预期值。

若执行后发现新检查本身有机械错误，可按公开依据修正，记录新版本、旧错误及变更理由，对该维度的全部8份候选重验；不只重跑失败项。仍属后验修订，不升级独立性。不得重复调整直到所有候选或某个方法达到理想结果。

## 13. 恢复环境与干净重建

复用上轮已恢复的固定执行/验收镜像及依赖资产。本轮不再为镜像管理新建系统；发现引用问题时只核对并恢复本研究命名空间的相同合法资产，不改latest、不全局prune。

每份候选必须：

1. 校验原base身份和原patch字节。
2. 从该base复制到新的独立目录；运行`git apply --check`后应用**同一完整补丁**。
3. 有原结束时源码清单时，比对重建源码；缺清单时说明只能证明base+patch重建，不能编造“与原工作区逐文件一致”。
4. 保留原patch所有新增/修改/删除，不删除不方便的测试文件，不偷偷修源码。
5. 在相同版本依赖下验证实际导入路径和命令入口；参考版本不得混入候选目录。

旧已成功生成的目录可能有测试缓存与上次输出，因此不能直接复用它作为本轮干净候选。原文件/目录只读保留。

候选中的缓存排除只遵循原捕获规则，不引入新的“忽略文件”清单来使hash吻合。原文件策略违规、patch无法应用或来源不明时，记录具体状态，不将其归为新内容测试失败。

## 14. 执行隔离与裁判可信边界

没有新Agent并不意味着原代码可在宿主无约束执行。原候选也可能启动子进程、修改输出或影响测试。

继续采用现有受限环境：候选运行无自由网络、无凭据、无Docker socket、无用户主目录；固定源码与可信检查不可写，仅提供必要临时目录。模型传输通道本轮不需要启用。

尽量让可信检查在控制进程中解析候选进程的退出码及输出文件，候选不负责计算自己的最终PASS、不提供期望矩阵、不写最终判分记录。保护测试源码和预期数据；不能将候选JSON中的`passed=true`直接当结论。

复用现有隔离与导入控制，不为本轮新造安全平台。对16份原patch做有针对性的只读检查，确认未改变裁判/报告路径；代码审阅不冒充对任意恶意候选的安全证明。

候选超时、磁盘异常或清理未确认时，停止相应执行、记录并排障。临时诊断文件不能进入原源码目录或Git历史。

## 15. 真实复验矩阵

对每份受影响候选都执行：

- 原目标与原基本回归的**原样复现**，写入新目录，和保存的旧JUnit对照。
- 本轮冻结的语义行为检查。
- 对应新增诊断夹具/功能探针，单列新覆盖。

共16份原候选，但每份包含多项测试。不可将测试用例数、两个入口或多张工作表当作新增独立任务。

原样复现因环境/运行波动与存档不一致时，标记`LEGACY_REPRODUCTION_MISMATCH`并调查；旧存档不改写。不能在失去可比性时仍把所有变化归为验收语义调整。

原base与可信参考执行同样的来源适用检查，作为检查正确性的控制证据；不计为N/F/T/J新增运行。

另16份未受影响候选默认仅使用旧记录做一致性核对。报告中清楚写“32份旧记录已核对、16份候选已重新执行”，而非“32份补丁全部重验”。

## 16. 结果状态与归因

建议每个run保存下列信息，可适配既有类型，不建设复杂新状态机：

```text
run_id / task_id / original_arm / original_repeat
original_patch_sha256 / base_identity / rebuilt_source_identity
legacy_recorded_target / legacy_recorded_regression
legacy_replayed_target / legacy_replayed_regression
reviewed_check_version / fixture_identities / environment_identity
per_obligation: PASS | FAIL | UNKNOWN | NOT_APPLICABLE
csv_original_fixture_content / csv_multisheet_content / csv_file_input_regression
package_entry / submodule_entry / console_entry
reason / stdout_stderr_refs / output_content_refs / junit_refs
analysis_scope: POSTHOC_REVALIDATION_OF_FROZEN_PATCHES
new_repair_agent_calls: 0
```

PASS仅指具体维度。缺资产、未执行、无法导入、环境未知和超时应保留不同原因；UNKNOWN不是功能FAIL，NOT_APPLICABLE不是跳过失败的借口。

不得沿用旧的`FUNCTIONAL_FAILURE`直接代表“真实需求已确认未满足”。同时也不得因识别了旧裁判局限，未经执行就把对应候选判成新PASS。

## 17. 后验汇总：先维度，再解释，不做漂亮总分

输出三张紧凑表：

**表一：原始32格摘要。**从原记录重算，仍是原定义，不覆盖；注明其中两任务的解释限制。

**表二：16份候选的行为对照。**原判分、原检查复现、新内容/入口维度、基本回归、原因并列。包含原成功和原失败的全部候选。

**表三：验收定义敏感性。**按两个任务分别统计原FAIL→新维度PASS、原PASS→新维度FAIL、未变和未知；两个重复仍归属于同一个任务，不能当独立机制。

对#368不生成一个择优的“已纠正成功率”：包入口和子模块入口都要保留，原CLI回归另列。需要情景汇总时同时展示“按标题解释”和“按正文解释”，明确歧义，不能只报对某方法有利的解释。

csvkit可按事先冻结的核心转换义务汇总`PASS_ON_REVIEWED_SCOPE`，但新增多表覆盖与原夹具结果仍可分解。不同覆盖范围不得直接揉成覆盖四个任务的所谓新总体修复率。

可以说明原来的表面优势是否对验收定义敏感；不写“证明方法等价”“已证伪所有路由方法”或“现在成功率达到100%”。本轮没有新的独立效果实验。

## 18. 成本与证据应当收紧

新记录只需：环境准备/恢复、候选重建、旧检查复现、新行为检查和汇总的实际时间及调用次数。

不要重算或归因旧Agent的token账单，不把本轮验收CPU时间混入旧Agent时延。没有新Agent不等于成本为零，控制器开发与容器执行单独说明。

公开：语义依据、夹具生成源与小型期望表、新检查源码、16份结果/必要输出、版本绑定与重算入口。原patch、原XML、模型、技能通过已有路径引用，不重复拷贝整库、镜像层或完整私密trace。

来源摘要用于一致性，不是行为正确性的证明。测试数和扫描字节数不作为主要成果。

## 19. 最小实现与可用入口

优先复用`advisory_capture.reconstruct`、已有验收容器、`advisory_records`的读取逻辑。只新增一个小型后验复验适配及对应测试，不修改旧冻结函数来迁就新语义。[S5]

建议职责（以下为待实现设计，不是当前已存在命令）：

```text
hermes-maintain acceptance-review inventory    # 锁定旧32格和受影响16份
hermes-maintain acceptance-review validate     # 语义合同、夹具、正反例与环境
hermes-maintain acceptance-review revalidate   # 重建并执行原候选；不调用Agent
hermes-maintain acceptance-review summarize    # 新旧维度表
hermes-maintain acceptance-review records      # 仅重算新记录；不跑候选/模型
```

命令名可按仓库结构调整，最终usage必须是实际跑过的参数，不能只复制示例。所有资产路径显式传入，不依赖个人主目录、当前工作目录或硬编码私有路径。

`records`不加载Torch/Transformers/PEFT、不连模型服务、不启动Docker；`revalidate`启动的是候选程序与检查进程，不得间接走`run_agent`、`recommend`或旧advisory-study run。

从仓库外的干净wheel环境完成轻量重算，并至少通过已安装入口复验一份事先按稳定顺序确定的原候选。安装验证不再额外调用修复模型。

## 20. 回归与恢复语义

除第11节的语义反例，覆盖：

- 原patch一个字节被改、错base、漏格/重复格、错夹具/检查版本会被拒绝或明确标为错配。
- 相同候选内容不因N/F/T/J标签改变行为判定；可以用同内容别名的构造测试确认，不计为真实重复。
- CSV名称变化不掩盖内容错误；内容相同也不忽略越界路径、符号链接或缺表。
- 包与子模块调用确实不同，不能只改变显示字段而仍执行同一个runpy分支。
- 空/缺JUnit、测试收集失败、候选导入错误不能被当成零失败PASS。
- 原数据目录保持只读语义；执行恢复不覆盖已完成结果和原补丁。
- 新模型/Agent入口被测试替换成抛异常哨兵后，复验和records仍不调用它们。
- 原32格及更早120/40行records在继承的兼容入口保持一致，不刷新旧来源hash冒充兼容。

没有必要为达到测试数量扩展无关功能。报告轻量/可选依赖环境的真实通过与跳过，不把跳过算通过。

## 21. 允许排障，但不循环追分

安装、镜像引用或检查启动失败可在相同配方下恢复并继续；记录失败尝试，不能归为模型失败。

同一原patch可因检查器的有依据修正而重新运行，但必须标为新的后验检查版本，所有受影响候选对称处理。功能FAIL本身不是重试理由，不反复运行直到取到PASS。

若环境无法恢复、原fixture/base缺失或重建清单矛盾，继续能做的语义分析和其他候选，明确未完成分母。禁止只把公开patch读一遍就声称真实复验已完成。

冻结后意外发现其他任务的新语义问题，记录为范围外限制，不自动扩张到所有历史评测。完成本轮后停止，不派生新训练、采样或“更难任务”Goal。

## 22. 目录、GitHub与交付

建议新目录：

```text
configs/acceptance-semantics-v1/
artifacts/acceptance-semantics-v1/
docs/repo-aware-routing/acceptance-semantics-v1/
```

保存本文件：

```text
docs/goals/Hermes_PR48_Acceptance_Semantics_Posthoc_Revalidation_Codex_Goal.md
```

审阅入口：

```text
docs/repo-aware-routing/acceptance-semantics-v1/review-index.md
```

继续同分支、同Draft PR #48；若用户已合并或改变基线，保护历史，按现状交付清楚的增量，不reset、不force恢复旧状态。

PR顶部新增后验附录说明；旧研究正文和文件保留。必要旧入口仅添加到新附录的导航或勘误指针，不重写原数据或原表。

完成相关测试、可运行全套测试、历史records与仓库外安装后正常推送；查看精确最终HEAD的CI。未完成或CI阻塞时准确说明，不拿旧HEAD绿灯代替。

本轮允许范围内提交/推送，不授予合并、ready、发布或上游提交。写入失败可使用本机已有合法git/gh授权，不索取密钥；仍失败则标`PENDING`。

## 23. 完成标准与最终状态

实质完成需要：

1. 两任务公开依据与原题面可见性已核对；无来源要求与需求歧义不被静默消除。
2. 新检查包含内容/入口语义和正反例，不只是放宽文件名前缀。
3. 16份原候选逐份保持patch不变、干净重建并实际复验；缺失和失败完整保留。
4. 原32格结果未覆盖；新表按维度说明定义变化与实际行为变化。
5. 可安装入口与records可运行，旧记录兼容，GitHub与同HEAD CI可审查。

建议输出：

```text
engineering: COMPLETE | PARTIAL
semantic_review: COMPLETED_WITH_STATED_AMBIGUITIES | PARTIAL
original_patch_integrity: VERIFIED | PARTIAL | MISMATCH
candidate_revalidation: COMPLETED_16_OF_16 | PARTIAL | NOT_RUN
legacy_results: PRESERVED
analysis_scope: POSTHOC_REVALIDATION_OF_FROZEN_PATCHES
new_repair_agent_calls: 0
new_routing_model_forwards: 0
training_and_calibration_runs: 0
utility_claim: NO_NEW_INDEPENDENT_GAIN_CLAIM
support_certification: NOT_CLAIMED
deployment_recommendation: KEEP_NATIVE
publication: PUSHED_DRAFT_PR | PENDING
```

`COMPLETED_16_OF_16`表示16份均有实际复验与结果，不表示16份通过。需求歧义可以在工程完成时继续存在；不要为了消除状态中的限制编造一个唯一成功定义。

最终中文复盘解释两个实际例子：一个CSV候选为什么在旧前缀与新内容定义下相同或不同；一个入口候选满足了哪条公开表述、没有满足哪条。不能用“全部成功”替代具体行为。

## 24. 来源与本次编制边界

[S1] 本对话提供的`Hermes_PR48_Advisory_Utility_Replay_Review.md`，尤其第3、4、6节；这是定向审阅及局部检查，不是16份候选完整复验。

[S2] 编制时PR及原实验说明：
https://github.com/Raidriar7170/hermes-skilleval/pull/48
https://github.com/Raidriar7170/hermes-skilleval/blob/49a7dfeb9efc8dcce112c829d4d7136c5bd281a3/docs/repo-aware-routing/advisory-utility-replay-v1/method.md
https://github.com/Raidriar7170/hermes-skilleval/blob/49a7dfeb9efc8dcce112c829d4d7136c5bd281a3/docs/repo-aware-routing/advisory-utility-replay-v1/results.md

[S3] 原检查：
https://github.com/Raidriar7170/hermes-skilleval/blob/49a7dfeb9efc8dcce112c829d4d7136c5bd281a3/artifacts/advisory-utility-replay-v1/checks-source/csvkit-issue-1225.py.txt
https://github.com/Raidriar7170/hermes-skilleval/blob/49a7dfeb9efc8dcce112c829d4d7136c5bd281a3/artifacts/advisory-utility-replay-v1/checks-source/sqlite-utils-issue-368.py.txt

[S4] 原公开问题，启动时结合实际题面与对应版本资料读取，不靠标题替正文或反过来：
https://github.com/wireservice/csvkit/issues/1225
https://github.com/simonw/sqlite-utils/issues/368

[S5] 当前恢复/安装与重建实现：
https://github.com/Raidriar7170/hermes-skilleval/blob/49a7dfeb9efc8dcce112c829d4d7136c5bd281a3/docs/repo-aware-routing/advisory-utility-replay-v1/usage.md
https://github.com/Raidriar7170/hermes-skilleval/blob/49a7dfeb9efc8dcce112c829d4d7136c5bd281a3/src/hermes_skilleval/repo_routing/advisory_capture.py

本文的语义矩阵、新夹具、统一复验与分层报告是下一轮开发要求，不是已测结论。编制本文只读取了已有审阅、PR和必要源码，没有运行原候选、修改仓库、推送文件或进行模型调用。

## 25. 可直接粘贴的启动提示

```text
读取并执行 Hermes_PR48_Acceptance_Semantics_Posthoc_Revalidation_Codex_Goal.md，
作为本轮完整Goal，保存到docs/goals/同名文件。

继续codex/hermes-repo-aware-cost-routing和Draft PR #48，
核对实际HEAD，保护用户修改、旧32格、全部原patch与旧检查。
直接实施，内部阶段连续推进；范围内持续授权，
不逐阶段申请批准，不设置固定工程尝试次数。

本轮只做验收语义复核和原补丁后验复验。
核对原公开来源、实际发给Agent的题面和版本接口，
先冻结来源支持的检查，不根据臂名或期望胜负改判。

csvkit #1225：对全部8份原补丁核对实际工作表内容、
完整性及文件输入回归，不只放宽stdin_前缀，也不接受空文件。
sqlite-utils #368：对全部8份原补丁分别测包入口、
CLI子模块入口与原命令入口；保留标题/正文歧义，不取最好解释。

从固定base应用原patch，复验旧检查并执行统一新检查。
公开正反例仅验证裁判，不冒充真实候选复验。
原表原字节保留，新表明确POSTHOC，不写新的独立修复收益。
另16份未受影响候选默认仅核对旧记录，不冒称全部32份已重验。

不调用新修复Agent、不重新推荐、不训练或校准，
不修改候选，不重复直到通过，不增加任务或平台。
可行环境就完成16份实际复验，不能只交mock或报告。
缺资产/环境如实保留未知与分母，不用重生成候选补齐。

完成干净安装、零模型重算、历史兼容与最终HEAD CI，
正常推送同分支并更新Draft PR。
不force、不合并、不ready、不发布、不改全局配置、不新增付费资源。
交付原判分/新行为对照、实际输出、未验证范围、PR和完整HEAD后停止。
```
