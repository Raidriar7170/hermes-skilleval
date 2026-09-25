# 第一阶段退出决策

`exploration=COMPLETE`；`next_step=READY_SKILLS_ONLY_WITH_MEMORY_LIMITATION`。

原生用户技能发现与实际使用已观测，60 条源轨迹精确关联到 30 个问题，两个不同仓库的环境完成 base/reference 资格验证，两次原生修复均形成可重建、可验收候选。pyupgrade 通过，httpx 保留一个目标失败。阶段完成不要求两项都成功。

该就绪结论仅限已验证的预配置、无工具网络、四条实验用户技能场景。记忆未成熟，六个系统技能正文受当前状态隔离限制，完整在线成本未知。因此不能宣称完整原生产品、最强原生配置、成本优势或技能效用。

| 阻塞 / 限制 | 进入下一阶段的条件 |
|---|---|
| 自动记忆只有开启与合资格会话，尚无生成 | 若比较包含暖记忆，应在后续明确授权的检查中等资格满足，验证原生生成和独立使用；否则两臂统一 skills-only |
| 系统技能正文被 `/state` 隔离阻断 | 设计下一阶段前，将系统技能独立只读暴露并重新验证凭据拒绝；冻结一致的可用能力目录 |
| 在线前置准备与镜像下载成本缺口 | 新协议将计时移到任务读取/输入准备之前，并单独实测共享层/冷启动成本；不能重跑本轮填旧账 |
| 仅 3 个便利选择源仓库、2 个开发环境 | 进一步身份/时间/近重复与许可划分；当前资产只能继续作开发资料 |
| httpx 官方 tuple 用例失败 | 保留失败候选和测试事实；不能追加同题补跑或称技能未调用为原因 |
| 没有同经验对照 | 不作“原生足够”“必须训练 Router”或任何因果收益结论 |

**唯一下一步建议：**另立一个小型、同经验技能库的比较合同，先解决系统技能暴露和完整计时，再冻结两臂一致的记忆状态、客户端和权限。本轮只提供规划条件，不自动实施比较，不构建 32 条技能、不跑 48 格、不训练新模型。

## 人工审阅摘要

- 真实运行规模：4 个探针语义；首次 4 请求服务拒绝，客户端修复后 4 次探针完成；1 批技能转换；1 次记忆种子；2 次原生真实修复。三次 Linux 预检不调用模型。
- 两个候选可信验收：1 PASS / 1 FAIL；不是二者都通过。目标检查分别 1/1、1/2，保护标签分别 30/30、3/3。
- 两次真实任务均未读取技能正文，不能据此判漏召回；无 BASE/NATIVE/ASSIST 对照。
- 公开事件仅保留允许项，递归去除 reasoning 对象；第三方原始轨迹、个人记忆与认证状态均不入 Git。
- 安全边界和证据代码经一位只读 Reviewer 检查；发现并修正过滤、清理留档与预算问题，系统技能限制显式保留。
- 本地 1610 tests、OpenSpec 46/46 通过；GitHub exact-head CI 以 PR 检查为准。完成封装后停在叠加 Draft PR，不合并、不发布、不改默认。

## 真值记录

```yaml
stage: native-gap-phase1-v1
exploration: COMPLETE
runtime_identity: codex-0.155.0-alpha.16.4/gpt-6-sol/high
native_skill_discovery: VERIFIED
explicit_skill_use: OBSERVED
implicit_skill_use: OBSERVED_IN_PROBES
memory_configuration: ENABLED_VERIFIED
memory_generation: PENDING_NATIVE_ELIGIBILITY
memory_use: NOT_RUN
source_issues_inspected: 30
trajectory_rows_inspected: 60
joined_source_issues: 30
environments_qualified: 2
native_smoke_attempts: 2
native_smoke_verifiable_candidates: 2
native_smoke_functional_passes: 1
native_smoke_functional_failures: 1
full_online_cost: UNKNOWN
full_comparison: NOT_STARTED
algorithm_gap_evidence: NOT_ESTABLISHED
new_model_training: NONE
next_step: READY_SKILLS_ONLY_WITH_MEMORY_LIMITATION
```

[原生能力](capability.md) · [数据、环境、运行与实际命令](data-environment.md) · [机器记录](../../../artifacts/native-gap-phase1-v1/manifest.json)
