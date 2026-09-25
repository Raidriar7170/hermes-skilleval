# 原生能力探查

本轮仅验证接线与运行可行性，`algorithm_gap_evidence=NOT_ESTABLISHED`。完整合同见 [Goal](../../goals/Hermes_Native_Gap_Phase1_Recon_Codex_Goal.md)。

| 原生能力 | 本地证据 | 边界 |
|---|---|---|
| 客户端与模型 | 0.155.0-alpha.16.4，gpt-6-sol / high；公开 App Server，ChatGPT 认证 | 0.154.0 的四次请求被服务拒绝，保留 v1；模型目录可见不能证明可调用 |
| 用户技能发现 | `skills/list` 返回隔离 HOME 下三项合成技能；真实运行返回四项样件 | HOME 与 CODEX_HOME 分离；没有复制日常技能或记忆 |
| 显式 P1 | 报告出现只在正文中的 FIELD_LEDGER_V1，CSV 结果正确 | 无单独正文文件读取事件；显式上下文加载与模型主动读取分开 |
| 隐式 P2 / P3 | 可见对应 SKILL.md 的 cat，分别完成 CSV 与测试入口任务 | 仅两个探针；不代表普遍路由准确率 |
| 非匹配 P4 | 回答 437，无工具或技能正文读取 | 单例，不估算误调用率 |
| 项目说明 | fixture AGENTS.md 的文件名要求体现在报告；P3 可见读取 | 真实任务保留 base 的项目文件，没有注入 Hermes Goal |
| 记忆配置 | features.memories=true；generate/use=true；持久化 thread memory_mode=enabled、source=vscode | 一次种子会话，非 ephemeral，来源是历史案例而非本轮本人经历 |
| 记忆生成 / 使用 | PENDING_NATIVE_ELIGIBILITY / NOT_RUN | 默认空闲 6 小时、剩余额度门槛 25%；原生空目录骨架不算生成 |
| 子任务 | 未额外关闭原生 agent feature | 本轮未直接测试，不宣称可用性已验证 |

完整初始提示不可见，因此 `progressive_loading_observable=PARTIAL_INITIAL_CONTEXT_NOT_EXPOSED`。P1 的标记证明正文信息被使用，不能伪造一个不存在的文件读取事件。

记忆依据同版本源码的 [默认条件](https://github.com/openai/codex/blob/rust-v0.155.0-alpha.16.4/codex-rs/config/src/types.rs) 与 [允许会话来源](https://github.com/openai/codex/blob/rust-v0.155.0-alpha.16.4/codex-rs/rollout/src/lib.rs)，并读取独立状态库的来源/开关字段核对。观察到 `No raw memories yet`，没有生成案例摘要。未修改阈值、时间戳或内部记忆文件，未做使用检查，未留下后台轮询。支持、开启、生成和使用是四件不同的事。

[官方技能说明](https://learn.chatgpt.com/docs/build-skills)、[官方记忆说明](https://learn.chatgpt.com/docs/customization/memories)、[官方非交互入口说明](https://learn.chatgpt.com/docs/non-interactive-mode) 用于定义能力；本轮结论来自实际事件，不来自文档或模型自述。

## 隔离与版本修复

原生修复使用 Linux ARM64 的同版本官方客户端，任务镜像为 amd64，在 Apple Silicon Docker 上仿真。amd64 客户端的 seccomp 预检失败记录保留；不把它算作 Agent 修复失败。完整 npm 运行资源包含 bubblewrap，未更新全局客户端。正常单轮执行没有四工具段落、CONTINUE/TASK_COMPLETE 或研究 JSON 输出要求。

每题从 image 的 base 导出干净树，只重建该 commit/tree 和浅层 HEAD，未来 Git 对象、issue.md 和镜像额外文件不进入工作区。工具只能写 `/testbed` 与 scratch；`/state` 认证 canary 被拒绝，镜像额外路径和网络不可见。原生服务可调用现有账户模型，工具不能访问凭据。三次非模型预检均保留。

能力限制必须一并理解：容器无日常插件；web/tool 网络禁用；六项内置系统技能虽然被列举，其 `/state/skills` 正文随状态目录被拒绝读取。四项实验用户技能可读。该限制在首题启动后的只读审阅中被确认，两题保持同一配置，不中途修改或重跑。这是带明确限制的 `NATIVE_SKILLS_ONLY` 场景，不是完整桌面原生产品或最强暖记忆基线。

## 记录入口

- [v1/v2 探针事件](../../../artifacts/native-gap-phase1-v1/probes/)
- [实际 runtime 与镜像身份](../../../artifacts/native-gap-phase1-v1/runtime.json)
- [记忆状态](../../../artifacts/native-gap-phase1-v1/memory.json)
- [隔离预检](../../../artifacts/native-gap-phase1-v1/preflight/)
- [四项技能样件](../../../configs/native-gap-phase1-v1/skills/) 与 [转换记录](../../../artifacts/native-gap-phase1-v1/skill-conversion.json)
