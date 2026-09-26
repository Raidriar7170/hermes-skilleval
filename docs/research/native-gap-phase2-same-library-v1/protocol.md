# 原生同经验库小型对照协议

状态：冻结的 16 格正式修复与独立验收均已完成，实际结果见 [results.md](results.md)。完整授权与验收标准以 [Phase 2 Goal](../../goals/Hermes_Native_Gap_Phase2_Same_Library_Pilot_Codex_Goal.md) 为准。

四个新任务、NATIVE / ASSIST 两臂、每臂每题两次，共 16 格。两臂共享完整历史经验库、catalog、系统技能、原始题面和工具权限，记忆使用与生成均关闭。ASSIST 仅追加固定 MiniLM/MMR 选出的至多三条原名称、原描述、原路径；不强制激活、不展开正文。

先登记身份，再提取来源技能；正式运行前冻结全部方法与材料。全部修复调用结束后才开放隐藏成绩。候选在干净 base 上重建，恢复作者测试并使用作者解析器；原标签数与完整 JUnit 分开，UNKNOWN 不填零。公开数据不代表预训练无污染，静态跨问题迁移不冒称严格时序回放。

## 当前实施边界

独立分支继承 `42b0bfd8122e6deb3d8785588a21751664b1073a`。原始资料与运行状态放在本机 `/tmp/hermes-native-gap-phase2-private`；复用 `/tmp/hermes-native-gap-phase1-private` 的固定数据和 Linux 官方客户端，只读保留 Phase 1。完整轨迹、参考答案、认证和私有状态不入 Git。

父监督器使用 Python 3.11 以上的跨进程一致单调时钟，先建 t0/绝对截止，再读取描述符、检查绑定及派发准备。正式总预算 900 秒、结束预留 15 秒；所有真实超额原样报告。隔离的前置 Git 元数据用于宿主候选捕获，避免执行被测 Agent 可修改的 Git 配置；确认容器停止后原子保存并计算补丁身份。

系统技能访问采用根目录默认拒读与 `/state/skills` 精确只读规则。没有放开整个状态目录。三次非模型检查记录首次显式拒读冲突、第二次 masked-path 检查假设错误及修正后通过。文件可读不代表依赖网络的系统技能工作流已被测试。

MiniLM 使用既有 `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` snapshot，元数据编码与查询使用已有 CompleteEncoder 完整分块聚合。权重和 tokenizer 身份见 artifacts 中 encoder-identity；长输入测试保留全部 1050 tokens、分为 5 块，不将 tokenizer 的长度告警误当作模型实际输入超长。

## 当前实际命令

- `/opt/anaconda3/bin/python scripts/native_gap_phase2_support/prepare_split.py`：元数据身份登记，无模型。
- `NATIVE_GAP_PRIVATE=/tmp/hermes-native-gap-phase2-private /tmp/hermes-native-gap-phase1-private/venv/bin/python scripts/native_gap_phase1_support/task_details.py`：按登记身份读取 Parquet 行组，取得 6 条详细候选；物理传输不是仅 6 行的体积。
- `/opt/anaconda3/bin/python scripts/native_gap_phase2_support/screen_targets.py`：可信侧精确身份及改动指纹筛查，不输出解法。它不证明没有语义近重复。
- `/opt/anaconda3/bin/python scripts/native_gap_phase2_support/qualify.py <task IDs>`：作者 base/reference 资格检查；安装错误保留，HTTPX 2523 另有 pythonpath 修正版。
- `/opt/anaconda3/bin/python scripts/native_gap_phase2.py run --descriptor <private JSON> --root <new attempt> --seconds <budget>`：父监督器；描述符区分非模型 canary、来源转换、无害模型预演及正式修复，不能合并计数。
- `/opt/anaconda3/bin/python -m pytest -q tests/test_native_gap_phase2.py`：构造测试，无模型；不代替真实格。

冻结身份与运行顺序见 plan.json / freeze.json，完整逐格原始结果与唯一决策已交付。没有训练、默认策略变化、合并或发布。

预演均为一次完整原生会话：第一格 29.86 秒读取系统正文/引用、catalog 和用户正文；第二格 39.29 秒接收三项可选导航，完成 README 工作，未见技能正文读取。正文是否经原生隐式机制进入不可见初始上下文仍为 UNKNOWN。冻结前补充两臂共用的仓库名/语言明示头；检索查询定义未变。镜像未预装 rg，两个预演自行使用 find 回退；这是预配置环境限制。

经验库实际为 12 条、12 个独立源问题，两个仓库各 6 条；来自继承的 30 问题池，未增加来源问题。正文 o200k token 数为 441–638，四条略超 600 的写作目标，保留来源条件和限制，没有为长度裁去关键事实。初始转换恰为 4 批，全部完成；两项事实修补来自独立来源核对，不来自目标成绩。

正式运行前已冻结 38 项仓库输入及 121 项私有资产身份，见 configs 中 freeze.json。固定种子生成的 8 个任务/重复块中，7 块 ASSIST 在先、1 块 NATIVE 在先；保留该冻结顺序，不因不平衡重选种子。顺序与服务端缓存可能影响成本，必须作为限制解释。

执行提交为 `697427ca7859e9ab9f8c9205a0230ffd7a954677`。正式入口实际启动命令为 `PYTHONPATH="$PWD/src" /opt/anaconda3/bin/python scripts/native_gap_phase2_support/run_pilot.py`，需要上述本机私有资产；它调用模型，顺序执行冻结 16 格，不运行隐藏验收。每格父监督器记录和原候选位于私有目录的 `runs/<id>/`。

冻结执行版本的首次 CI 因测试模块动态导入缺少非空类型检查而失败（mypy 三条错误）。后续只给测试入口增加 `SPEC/loader` 非空断言；本地同版 mypy、9 项测试和 Ruff 通过。此交付修补不改变任何冻结输入或正式运行行为，研究执行版本仍为上述提交。

## 已保存的准备成本

| 类别 | 实际记录 | 边界 |
|---|---:|---|
| 6 个候选任务数据 | 16,006,613 bytes / 79 HTTP 请求 / 30.34 秒 | 按 Parquet 行组取得，非仅六行逻辑大小 |
| 镜像拉取／构建 | 14 条记录合计 85.62 秒 | 包含失败，实际网络传输字节 UNKNOWN，storage size 不当下载量 |
| base/reference 资格 | 5 组记录合计 22.63 秒 | 包含 HTTPX 2523 初次失败及路径适配版 |
| 4 批经验转换 | 860.96 秒 | 独立于正式修复；3,128,087 输入、2,813,184 缓存输入、40,048 输出、3,168,135 total tokens |
| 技能元数据离线编码 | 2.904 秒 | 固定 MiniLM；各 ASSIST 查询初始化与编码仍由对应在线格支付 |
| 两次无害预演 | 29.86 / 39.29 秒 | 非正式修复；三次权限 canary 不调用模型 |

缓存输入是输入子集，不再次相加。以上不是完整项目工时或历史冷启动总账；来源核对、编排和 CI 的模型额度没有并入被测 Agent 用量，金额无账单留空。正式逐格成本已从父监督器原记录导出至 usage-costs.json，包含全部成功与失败格。

## 最终执行与记录重读

- `PYTHONPATH="$PWD/src" /opt/anaconda3/bin/python scripts/native_gap_phase2_support/run_pilot.py`：实际执行 16 次模型修复；不应为复核结果再次采样。队列终态齐备后才运行以下验收。
- `/opt/anaconda3/bin/python scripts/native_gap_phase2_support/accept.py`：已在 16 个独立干净 base 重建原候选并运行作者测试，不调用模型。需要本机冻结私有任务、镜像和 author parser；存在结果时保留已有记录。
- `/opt/anaconda3/bin/python scripts/native_gap_phase2_support/export.py results`：只从已保存记录导出公开结果、原补丁、JUnit 与累计 token 末值，不发模型请求、不重新检索。
- `PYTHONPATH="$PWD/src" /opt/anaconda3/bin/python -m pytest -q`：最终本地完整检查为 1619 passed，1 个继承的 tarfile 弃用告警。首次未设置 PYTHONPATH 的调用有 5 项子进程 ModuleNotFoundError（其余 1614 passed），按环境修正后通过，没有修改业务代码。
- `ruff check scripts/native_gap_phase2.py scripts/native_gap_phase2_support tests/test_native_gap_phase2.py`、相同范围的 `ruff format --check`、`mypy --follow-imports=skip tests/test_native_gap_phase2.py`：均通过。

仅有公开仓库 checkout 时，可直接阅读三份文档及公开 runs/checks/results，也可重新计算表格；完整重新验收依赖上述私有原始资产和本机镜像，不宣称无需资源即可一键复现。公开事件对长工具输出保留前后摘录、原长度与 SHA；完整原候选和 JUnit 不截断。

执行模型为 `gpt-6-sol / high`，Linux 官方客户端 `0.155.0-alpha.16.4`；宿主 Python 3.12.2，Docker daemon 为 arm64，任务镜像为 amd64 仿真。镜像身份用不可变 image ID 绑定。运行器没有额外禁用原生子任务功能；本轮未专门验证子任务工作流，不将配置保留称为能力已实测。正式有效配置确认 memories=false 且 use/generate 均 false。系统资源可读与依赖外网的系统技能工作流可执行分别限定。

[Draft PR #58](https://github.com/Raidriar7170/hermes-skilleval/pull/58) 叠加于未合并的 #57。测试入口修补提交 `07705d4a413453ad9b5b5bfc0ccb8899e9e204d2` 的 [CI](https://github.com/Raidriar7170/hermes-skilleval/actions/runs/36218694350) 为 1616 passed / 3 skipped、OpenSpec 47/47、静态检查无新增；最终交付 HEAD 的状态以 PR 和最终回复为准。软件门禁不授权合并。
