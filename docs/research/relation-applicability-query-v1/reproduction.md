# 实际执行记录

工作树为 `hermes-relation-applicability-query`；Python 使用现有 `/opt/anaconda3/bin/python`，`PYTHONPATH=src`。私有研究根目录为相邻 `hermes-relation-applicability-private/study-v1`，不提交模型权重、原始 app-server 会话、凭据或完整索引。编码器为已有 MiniLM 快照 `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`。Docker镜像ID为 `sha256:94df6dc8529a805f77b6410007bce1d0f9f0361dad6bf2bcde0930061ec0011b`，实际 `codex --version` 为 `codex-cli 0.154.0`。

以下准备、传输预演、开发Q/J与冻结命令已成功。正式执行代码为 `cc1fd7f`，冻结发生在开发核对后、宏/缓存新Q/J生成前；后续命令仅在实际完成后加入成功清单。

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

开发参考与正式冻结已成功执行：

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.relation_query_study build-reference \
  --phase development --output ../hermes-relation-applicability-private/study-v1
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.relation_query_study freeze \
  --output ../hermes-relation-applicability-private/study-v1 \
  --encoder /Users/raidriar/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41
```

正式冻结重新SHA-256核验编码器与四状态输入。私有原ledger保留截点前观察；公开导出只保留完整要求和权重，原ledger字节身份另记，不能声称删减导出的SHA与原件相同。关系模型实际输入仅包含请求的要求/原文；算法的原候选、权重及面板可从公开导出复算。

正式参考表与封存回放已成功：

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.relation_query_study build-reference \
  --phase check --output ../hermes-relation-applicability-private/study-v1
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.relation_query_study replay-queries \
  --output ../hermes-relation-applicability-private/study-v1
```

共192个原文配对各有Q/J判断，部分传输/格式缺失单独续接；合法语义结果没有重抽。回放在所有Q封存后启动，与最后的缓存J生成有短暂时间重叠；受限worker被实际拒绝读取J，两者不共享标签。回放20条，不调用在线模型；在线获取在全部参考模型调用结束后才开始，未与参考调用并发。

12条在线获取已成功执行并生成 `online-locked.json`：

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.relation_query_study run-acquisition \
  --output ../hermes-relation-applicability-private/study-v1
```

本次91个请求位置，没有轨迹内重复配对；跨策略/重复仍独立真实调用。宏R-r1在仍有多个待查配对时发起了单对批次（2/2/1）。虽然成本保守参照2对，仍违反Goal第16节仅允许待查不足2对时使用单对批次的限制。该轨迹完整保留，严格比较资格为false；12次尝试中11次严格合格，online_acquisition=PARTIAL，不重跑覆盖。全部轨迹正常 NO_AFFORDABLE_BATCH 结束，实际32.006–42.227秒，剩余时间不是可免费追加调用的许可。

来源核对与只读汇总已成功执行：

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.relation_query_study review-sources \
  --output ../hermes-relation-applicability-private/study-v1
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.relation_query_study summarize \
  --output ../hermes-relation-applicability-private/study-v1
```

核对106对（宏73、缓存33），均有终态，无传输缺失；保留2条拒绝和1条语义未知。来源核对使用冻结cc1fd7f；随后修复真实pending数控制的singleton启动（包括47/48额度边界），并修正report的严格资格及清理汇总。最终源码未重新运行模型研究，原freeze继续指向cc1fd7f；不能拿最终源码重绑原研究身份。当前freeze检查会拒绝直接继续采样，这是预期保护。

第一次后处理因CandidatePool字段名称错误退出，修正为candidates后汇总成功；没有启动模型或改变原始记录。面板Q/J共384个不同判断单元，实际385个传输机会（1个仅缺失续接），不能称严格384次传输。传输20批64机会、在线16批91位置、核对15批106机会各自报告，不相加称Agent运行数。金额没有账单依据。
