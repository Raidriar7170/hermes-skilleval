# 原生同经验库小型对照协议

状态：方法和材料已冻结，正式结果尚未产生；结果不能预填。完整授权与验收标准以 [Phase 2 Goal](../../goals/Hermes_Native_Gap_Phase2_Same_Library_Pilot_Codex_Goal.md) 为准。

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

最终冻结身份、运行顺序、实际成功命令、原始功能表与最终决策将根据保存记录补齐。当前没有训练、默认策略变化、合并或发布。

预演均为一次完整原生会话：第一格 29.86 秒读取系统正文/引用、catalog 和用户正文；第二格 39.29 秒接收三项可选导航，完成 README 工作，未见技能正文读取。正文是否经原生隐式机制进入不可见初始上下文仍为 UNKNOWN。冻结前补充两臂共用的仓库名/语言明示头；检索查询定义未变。镜像未预装 rg，两个预演自行使用 find 回退；这是预配置环境限制。

经验库实际为 12 条、12 个独立源问题，两个仓库各 6 条；来自继承的 30 问题池，未增加来源问题。正文 o200k token 数为 441–638，四条略超 600 的写作目标，保留来源条件和限制，没有为长度裁去关键事实。初始转换恰为 4 批，全部完成；两项事实修补来自独立来源核对，不来自目标成绩。

正式运行前已冻结 38 项仓库输入及 121 项私有资产身份，见 configs 中 freeze.json。固定种子生成的 8 个任务/重复块中，7 块 ASSIST 在先、1 块 NATIVE 在先；保留该冻结顺序，不因不平衡重选种子。顺序与服务端缓存可能影响成本，必须作为限制解释。
