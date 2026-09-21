# 可执行入口与边界

以下命令从仓库根执行，Python需要已有开发依赖；索引/检索另需冻结MiniLM、torch/transformers/tiktoken。真实执行需要已授权的同一模型、Docker镜像、任务公开/隔离验收资产及现有凭据。缺失资源应报阻断，不能用mock代替。记录分析命令不调用修复Agent。私有任务/完整索引/完整会话不发布到GitHub。

本地执行时使用 `/opt/anaconda3/bin/python`，通过命令级 `PYTHONPATH=src` 加载工作树，没有修改全局环境。用户可将下面 `python` 替换为已验证解释器。示例中的 `TASK_ROOT`、`LEGACY_PRIVATE`、`STUDY_PRIVATE`、`ENCODER_ROOT`、`TRUSTED_OVERLAYS` 是本次资源位置，不是自动下载入口。

```bash
export PYTHONPATH="$PWD/src"
python -m hermes_skilleval.intervention.linked_context_study --help
python -m pytest -q
OPENSPEC_TELEMETRY=0 openspec validate evidence-linked-local-retrieval-v1 --strict

python scripts/evidence_linked_local_retrieval/development_v2.py \
  --private "$STUDY_PRIVATE" --legacy "$LEGACY_PRIVATE" \
  --encoder "$ENCODER_ROOT" --iteration development-v5 --phase prepare
python scripts/evidence_linked_local_retrieval/query_ablation.py \
  --private "$STUDY_PRIVATE" --encoder "$ENCODER_ROOT" --iteration development-v5
```

开发提议已有保存结果不可重采样；`relations` phase只对新增输入运行一次，既有结果需使用其原版本输入。`compose` phase仅从已有完整关系矩阵组合，不调用模型。固定对照通过 `full / old40 / no-expansion / legacy-query` 的四组文件重放。

```bash
python scripts/evidence_linked_local_retrieval/development_v2.py \
  --private "$STUDY_PRIVATE" --legacy "$LEGACY_PRIVATE" \
  --encoder "$ENCODER_ROOT" --iteration development-v5 --phase compose
python scripts/evidence_linked_local_retrieval/export_development.py \
  --root "$STUDY_PRIVATE/development-v5" \
  --output artifacts/evidence-linked-local-retrieval-v1/development
```

真实研究只在完成资格/来源核对后执行，冻结文件已存在时不能再次freeze。`index`不覆盖已准备版本。所有运行需保持冻结算法、任务、overlay、公共索引及模型身份。原检查点和已开始格不可替换；任何中断需明确记录停止证据，不能以目录存在当完成。

```bash
python scripts/evidence_linked_local_retrieval/prepare.py index \
  --tasks "$TASK_ROOT" --legacy-knowledge "$LEGACY_PRIVATE/knowledge" \
  --output "$STUDY_PRIVATE/study-v3" --encoder "$ENCODER_ROOT"
python scripts/evidence_linked_local_retrieval/prepare.py freeze \
  --tasks "$TASK_ROOT" --legacy-knowledge "$LEGACY_PRIVATE/knowledge" \
  --output "$STUDY_PRIVATE/study-v3" --encoder "$ENCODER_ROOT" \
  --overlays "$TRUSTED_OVERLAYS"

python -m hermes_skilleval.intervention.linked_context_study run --phase prefix \
  --plan configs/evidence-linked-local-retrieval-v1/plan.json \
  --tasks "$TASK_ROOT" --skills configs/conditional-applicability-v1/skills \
  --output "$STUDY_PRIVATE/study-v3"
python -m hermes_skilleval.intervention.linked_context_study run --phase compose \
  --plan configs/evidence-linked-local-retrieval-v1/plan.json \
  --tasks "$TASK_ROOT" --skills configs/conditional-applicability-v1/skills \
  --encoder "$ENCODER_ROOT" --output "$STUDY_PRIVATE/study-v3"
```

随后独立审阅新预测并绑定selection-lock SHA-256；审阅不可改包。尾程结束后才运行隐藏验收：

```bash
python -m hermes_skilleval.intervention.linked_context_study run --phase tails \
  --plan configs/evidence-linked-local-retrieval-v1/plan.json \
  --tasks "$TASK_ROOT" --skills configs/conditional-applicability-v1/skills \
  --output "$STUDY_PRIVATE/study-v3"
python -m hermes_skilleval.intervention.linked_context_study evaluate \
  --plan configs/evidence-linked-local-retrieval-v1/plan.json \
  --tasks "$TASK_ROOT" --skills configs/conditional-applicability-v1/skills \
  --overlays "$TRUSTED_OVERLAYS" --output "$STUDY_PRIVATE/study-v3"
python scripts/evidence_linked_local_retrieval/summarize.py \
  --study "$STUDY_PRIVATE/study-v3" \
  --plan configs/evidence-linked-local-retrieval-v1/plan.json \
  --output artifacts/evidence-linked-local-retrieval-v1/functional-summary.json
```

`report/replay --ledger <rows.json> --output <report.json>`只重算已保存逐格标签，不启动Agent或验收；输入为行列表，各行提供integrity/target/protected。`index/analyze/retrieve/inspect/compose`提供同一组件的单项入口，参数见`--help`；`inspect`会调用关系模型，不能与只读记录重放混淆。

公开源码引用属于精确版本Ansible一方代码/文档/既有公开测试，保留来源路径、revision、行号和项目许可证义务（Ansible GPL-3.0-or-later及各文件许可头）。完整第三方仓库、模型权重与私有会话未包含在本交付中。有限摘录不代表各新行为已经正确。

## 本次冻结后续行记录

首次宏任务关系输出322/336对，被原严格校验拒绝；原输出/成本保留，没有重采样。原协调器未持久化失败前整个阶段的耗时，因此不能编造共同剩余预算。窄运行器修复将该状态全部8计划格记UNKNOWN_PREPROCESS_FAILURE，不发补标签、不启动替代H。另一项原名单继续。

实际尾程和验收代码保存在提交 `32129083060129f9fd0b4740039f46c6614dcbda`，对应 `configs/evidence-linked-local-retrieval-v1/plan-runtime-repair-v2.json`。最终HEAD包含后续文本范围修复，因此不能对最终HEAD宣称上述冻结计划仍匹配。实际后续compose、tails、evaluate、summarize命令的`--plan`均使用此路径；上述初始plan保留为历史冻结证据，当前代码对其身份检查会拒绝。两份原前缀不重生成。`artifacts/evidence-linked-local-retrieval-v1/runtime-repair.diff.gz`保留唯一协调器变化，可检查原/新源码身份。受影响验证称PARTIAL_REPAIRED_AFTER_FREEZE，不能称完整首次冻结验证。


## 历史执行代码与最终代码分开

实际尾程/验收使用 `32129083060129f9fd0b4740039f46c6614dcbda` 的代码及runtime-repair-v2计划。需要检查既有实验时，在该提交的独立只读checkout加载已保存记录；不要在最终修复代码上绕过冻结检查，也不要重新启动已有研究格。首次plan对应的唯一运行器差异可由公开runtime-repair.diff.gz反向核对。上面的prefix/compose初始命令是历史执行记录，不是在当前HEAD重新运行的指令。

最终HEAD的 `index` / `retrieve` 可用于内容准入修复后的离线工作；本轮在六个base已实际重建并执行固定检索，结果位于公开index-scope-repair目录。该结果没有新的关系推断或功能尾程。

实际成功的冻结后尾程和验收入口（已执行记录，非新增采样授权）：

```bash
python -m hermes_skilleval.intervention.linked_context_study run --phase tails \
  --plan configs/evidence-linked-local-retrieval-v1/plan-runtime-repair-v2.json \
  --tasks "$TASK_ROOT" --skills configs/conditional-applicability-v1/skills \
  --output "$STUDY_PRIVATE/study-v3"
python -m hermes_skilleval.intervention.linked_context_study evaluate \
  --plan configs/evidence-linked-local-retrieval-v1/plan-runtime-repair-v2.json \
  --tasks "$TASK_ROOT" --skills configs/conditional-applicability-v1/skills \
  --overlays "$TRUSTED_OVERLAYS" --output "$STUDY_PRIVATE/study-v3"
```

公开标签可在最终HEAD安全重算，不调用Agent、模型或隐藏验收：

```bash
python -c 'import json; from pathlib import Path; p=Path("artifacts/evidence-linked-local-retrieval-v1/functional-results.json"); Path("/tmp/evidence-linked-rows.json").write_text(json.dumps(json.loads(p.read_text())["rows"]))'
python -m hermes_skilleval.intervention.linked_context_study replay \
  --ledger /tmp/evidence-linked-rows.json --output /tmp/evidence-linked-replay.json
```


本轮已保存的本地资源别名（私有数据不随PR分发）：`LEGACY_PRIVATE=../hermes-repair-knowledge-private`，`TASK_ROOT=$LEGACY_PRIVATE/tasks`，`STUDY_PRIVATE=../hermes-evidence-linked-private`，`TRUSTED_OVERLAYS=$STUDY_PRIVATE/test-overlays`。编码器为MiniLM固定快照`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`，不自动下载其他模型。

公开补丁使用gzip无损封装。先运行`gzip -dc <candidate.patch.gz> > /tmp/candidate.patch`即可取得原始字节；解压SHA-256必须匹配compressed-evidence.json及对应result.json中的patch_sha256，随后才可应用到精确base。修复.diff.gz同理。
