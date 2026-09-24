# 实际执行记录

工作树为 `hermes-relation-applicability-query`；Python 使用现有 `/opt/anaconda3/bin/python`，`PYTHONPATH=src`。私有研究根目录为相邻 `hermes-relation-applicability-private/study-v1`，不提交模型权重、原始 app-server 会话、凭据或完整索引。编码器为已有 MiniLM 快照 `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`。Docker镜像ID为 `sha256:94df6dc8529a805f77b6410007bce1d0f9f0361dad6bf2bcde0930061ec0011b`，实际 `codex --version` 为 `codex-cli 0.154.0`。

以下前两项已成功，开发参考表仍在运行；后续命令只有实际完成后才会加入成功清单。

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.relation_query_study prepare-panel \
  --output ../hermes-relation-applicability-private/study-v1 --assets .. \
  --encoder /Users/raidriar/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.relation_query_study benchmark-transport \
  --output ../hermes-relation-applicability-private/study-v1
```

`prepare-panel` 读取原 ledger/pool 与最终准入索引，验证冻结编码器摘要、计算真实 embedding 并封存面板，不调用关系模型。`benchmark-transport` 实际调用同一关系模型，20批/64个配对输出机会，不能描述为零模型。

传输预演使用开发期首版适配。随后修复了截止前合法消息保留、部分消息解析和冷调用清理计时口径；原20批、原提示、原返回与完整秒数均保留，没有重抽语义标签。成本模型将冷调用的原完整秒数减初始化作为含清理请求耗时，未把旧较短的响应片段当完整成本。正式执行版本在开发Q/J之后另外冻结。

公开特征准备耗时按状态记录；编码器对象初始化未单独计时，标记 UNAVAILABLE，不补造阶段数值。正式60秒从公共输入加载后、选择器构造前开始，包含求解、序列化、独立进程启动、关系调用、取消与清理；公共输入和特征准备另列。不存在跨策略关系缓存。

已执行局部测试：

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m pytest -q tests/test_pair_applicability_query.py tests/test_budgeted_relations.py
openspec validate relation-applicability-query-v1 --strict
```

本机回放使用 `/usr/bin/sandbox-exec` 的文件读取拒绝规则，启动时分别尝试读取Q/J并要求 PermissionError。其他系统不能静默退回无隔离回放；需要同等只读监督器/受限worker实现。
