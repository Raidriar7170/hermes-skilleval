# 数据、环境与两次原生运行

本轮已完成实际数据抽查、两个环境资格验证和两个各一次的原生修复。功能结果为一项通过、一项失败；两项候选都能重建和可信验收。这不是方法比较。

## 数据关联表

| 项目 | 本轮观察与分母 |
|---|---|
| 轨迹源 | `nebius/SWE-rebench-openhands-trajectories` @ `35455389ab51bf5e2306bfd436ef72d0f98bf882` |
| 原版任务源 | `nebius/SWE-rebench` @ `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`；没有与 V2 混接 |
| 元数据扫描 | 67,074 条轨迹身份行 + 21,336 条 test split 任务身份行 |
| 详细检查 | 30 个独立源问题、每题 2 条，共 60 条轨迹；3 个 Python 仓库 |
| 解析 | 60/60 OK；都有实际工具动作、工具观察与候选 patch |
| 任务精确 join | 30/30 源问题 MATCHED |
| 镜像字段可定位 | 30/30 源问题有映射；不等于这些镜像都拉取或验证过 |
| 多候选 / 混合结果 | 29/30 问题的两个 patch 哈希不同；3/30 的原作者 resolved 标签不同 |
| 原作者标签 | 25/60 为 1，35/60 为 0；不是本地复验率 |
| 许可 | 数据卡 CC-BY-4.0；每行保留原仓库 license_name |

选择先于结果读取。明确选择 pyupgrade、httpx、sqlglot 三个 Python 维护仓库，按 `sha256("20260925:" + identity)` 排序；前两个仓库先预留各两个有镜像映射的候选，再各取 10 个来源问题，每问题按轨迹 ID 同序取最多 2 条。不按 resolved、patch 或技能正例挑选。仓库选择本身有便利偏置，且样本集中在三仓库；不能外推全库 join 率或适用性标签规模。

四个候选与 30 来源身份不重叠。候选公开问题与源问题做文本近似比对，最高比值约 0.181；样件实际来源三个问题另作人工主题核对。该检查不是语义去重证明，所有资产永久标为开发探查，不能以后重新称未见测试。

三个完整链条见 [结构抽查](../../../artifacts/native-gap-phase1-v1/source-chain-examples.json)：公开问题、实际工具参数/输出、候选 patch 哈希及原作者标签分开保存。完整公开原始行只保留本机；转换输入排除了 assistant 推理正文和 think/finish 工具内容，没有执行历史 shell 命令。

## 传输与扩展性

轨迹 Parquet 总文件大小约 2.08 GB，但未整体下载。HTTP Range 仅投影身份列，实际取得 2,704,340 bytes；两片任务元数据取得 1,837,432 bytes。34 个登记任务的详细资料按 Parquet 行组读取，实际传输 30,886,478 bytes：这是含额外行的物理块成本，不是假称仅传输 34 行；仅登记行写出供检查。

60 条详细轨迹经 datasets-server 逐行读取，每次验证 `x-revision` 和 trajectory_id，共 18,287,898 response bytes。首次 47 成功、1 次 502、12 次 429；降为顺序低速后补齐 13 条，旧错误保留。此前 filter 接口一次 500 亦保留。错误响应体字节与失败 filter 总时间未计量，因此这些字节不是完整网络费用。元数据列扫描分别约 22.37 / 27.37 / 30.38 秒；任务详细块读取约 32.11 / 50.92 秒。

两个官方镜像及一个本地安装修正版的 digest、平台和存储尺寸见 [runtime](../../../artifacts/native-gap-phase1-v1/runtime.json)。Docker 下载共享层复用及总墙钟未完整计量，**镜像实际网络下载字节和总时间 UNKNOWN**；不能用镜像存储尺寸或轨迹体积代替冷启动成本。同版本 Linux x64/ARM64 客户端包下载量另列。

扩展路径成立：身份列投影 → 冻结问题/轨迹清单 → revision 验证逐行获取 → 作者镜像/安装配置 → base/reference 验证。已观察障碍包括接口限流、粗粒度 Parquet 块、部分镜像需补安装、架构与权限兼容。任务 created_at 可用不代表轨迹生成时间完备，未完成全库时间划分或语义去重，许可仍需逐仓库检查。数据卡作者报告 67,074 条轨迹和约 7,500 个镜像，均不等于已就绪独立环境数。[轨迹数据卡](https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories/tree/35455389ab51bf5e2306bfd436ef72d0f98bf882)、[任务数据卡](https://huggingface.co/datasets/nebius/SWE-rebench/tree/89cdfbab4ab1bd8f5a658bb212d1b63624f4f881)

## 环境与 smoke 表

| 任务 | base / reference 官方文件测试 | 原生候选可信验收 | 技能与 Agent 自测 |
|---|---|---|---|
| `asottile__pyupgrade-330` | base 1 fail + 32 pass；reference 33 pass | **PASS**：33 pass；作者目标 1/1、保护标签 30/30 通过 | 未见技能正文读取；Agent 报告相关 87 tests 通过，完整套件的 12 failures 也在 base 复现 |
| `encode__httpx-386` | 初次缺 editable 安装，base/reference 均导入失败；离线安装后 base 2 fail + 3 pass、reference 5 pass | **FAIL**：4 pass + 1 fail；目标 1/2、保护 3/3 通过 | 未见技能正文读取；Agent 报告自测 86 tests 通过，完整套件的 socket 测试受沙箱限制 |

Agent 自测与独立验收不混为一谈。httpx 候选没有处理官方 tuple 值用例 `test_queryparams[source2]`，把 tuple 字符串化，得到 `"('123', '456')"` 而非 `'456'`。不追加修复，不把一次失败变成算法缺口。

可信检查从原镜像的准确 base 重新应用候选，恢复官方测试涉及的文件，再应用官方 test_patch。候选自己的目标测试不能替代冻结测试。pyupgrade 的作者解析器将含空格的参数化 nodeid 截断，30 个保护标签是原协议标签数；完整 JUnit 另列 33 个用例。初版全 nodeid 核对中的 UNKNOWN 保存在本机，改用作者原解析函数重读同一日志后全部匹配，未重跑 Agent 或测试。

两个资格环境的 HEAD 分别为 `162e74ef019982b8c744276103f1efdbac8459d0`、`31730e709597baaa7b2364fee041dfa985169789`。安装与检查沿用 [作者 harness](https://github.com/SWE-rebench/SWE-bench-fork/tree/e4907b7a90eafaa1f0a6428fd04fe31cdd8b4284) 的 install_config、目标测试文件选择和 pytest parser。httpx 只补 `pip install --no-deps --no-build-isolation -e /testbed`，未改测试合同。备用 pyupgrade-133、httpx-3412 未运行。

两题各一个新线程、一次完整原生 turn；均正常完成，未超时、未人工续写。实测区间 142.274 秒 / 310.653 秒，分别总 token 318,379 / 519,531；缓存输入 266,112 / 484,864 是输入子集，不能再次相加。金额无账单，留空。**完整在线成本 UNKNOWN**：调用方任务 JSON 读取、输入字段投影及冻结哈希发生在计时器前；已测区间覆盖随后工作区/state 准备、客户端、工具、输出、清理和补丁捕获。不用新运行补填旧账。

[环境记录](../../../artifacts/native-gap-phase1-v1/environment-results.json) · [候选可信验收](../../../artifacts/native-gap-phase1-v1/candidate-verification.json) · [补丁与公开事件摘录](../../../artifacts/native-gap-phase1-v1/smoke/) · [数据统计](../../../artifacts/native-gap-phase1-v1/data-summary.json)

## 实际执行命令与复现边界

本机数据/状态根为 `/tmp/hermes-native-gap-phase1-private`，不入 Git；仓库脚本默认读取它，可用 `NATIVE_GAP_PRIVATE` 指定路径。原始数据、镜像、私有状态未随 PR 分发，不能称克隆仓库即可一键复现。

| 命令/入口 | 性质 |
|---|---|
| `codex --version`、`codex login status`、`codex app-server generate-json-schema --out …` | 本机只读能力检查，无模型生成 |
| `python3 scripts/native_gap_phase1.py probe-skills --private …/probes-v1 --output …/probe-results-v1` | 4 次被服务拒绝的 v1 请求 |
| 同命令加 `--binary /Applications/ChatGPT.app/Contents/Resources/codex`，独立 v2 目录 | 4 次实际合成探针，model=gpt-6-sol、effort=high |
| 私有 venv 的 `python scan.py` / `task_details.py` / `trajectory_details.py` | HTTP 元数据/登记行获取，不调用模型；对应版本已保存在 support 目录 |
| `python3 scripts/native_gap_phase1_support/select_roster.py` | 固定身份选择；已有清单仅校验，不覆盖 |
| `python3 …/qualify.py`、`python3 …/qualify_v2.py` | 6 次 base/reference 资格测试容器调用，v2 仅修 httpx 安装 |
| `python3 …/convert.py` | 一批源到技能转换，300 秒预算，292.87 秒完成 |
| `run_session(..., memory=True)` | 一次持久化记忆种子会话，约 15.46 秒；没有使用检查 |
| `native_smoke(..., preflight=True)` | 三次非模型 Linux 隔离预检；v3 成功 |
| `python3 scripts/native_gap_phase1_support/run_smokes.py` | 两次原生修复；拒绝重复已存在的 attempt 目录 |
| `python3 scripts/native_gap_phase1_support/verify_candidates.py` | 两次可信候选重建/官方测试，旧记录不覆盖 |
| `PYTHONPATH="$PWD/src" /opt/anaconda3/bin/python -m pytest -q` | 1610 pass；首次缺 PYTHONPATH 的 5 fail / 1605 pass 也记录 |
| `openspec validate --all --strict` | 46/46 pass，不代表模型能力或收益 |

具体 Docker 命令、配置及必要安装参数保存在对应 JSON。网页检索、临时协议获取和失败下载也属于一次性准备；其完整总时间没有计量。
