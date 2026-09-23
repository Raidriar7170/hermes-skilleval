# 复算与执行边界

本轮执行代码为 `579f2e44a3029f07b62a9ed29690f9251c992594`，冻结计划提交为 `126ae6d`。计划摘要为 `894ba351e433b7f8e012e6e006d09dca575d27ae4b269b0e0746281d455db61e`。后续记录导出和文档修改不代表重新执行修复 Agent。最终报告必须列出冻结源码与交付 HEAD 的差异。

这是两个已观察机制的新版本开发性比较，不是首次盲测。旧 PR53 的补丁、UNKNOWN 和功能结果保持原样。公共仓库仅保存紧凑证据；下述私有任务、原始会话、索引和验收资产不会随 PR 发布。

## 资源与入口

实际工作目录为 `/Users/raidriar/dev/hermes-skilleval-worktrees/hermes-budgeted-relation-selection`。Python 使用 `/opt/anaconda3/bin/python`，设置 `PYTHONPATH=src`。运行时身份为 Docker 镜像 `hermes-repair-knowledge-executor:v1`、Codex CLI `0.154.0`、执行和关系模型 `gpt-5.6-sol` / medium。

相对该目录：任务在 `../hermes-repair-knowledge-private/tasks`，可信覆盖在 `../hermes-evidence-linked-private/test-overlays`，新研究记录在 `../hermes-budgeted-relation-private/study-v1`。所有任务、覆盖、算法和表示资产身份均由冻结计划验证；缺资源不是下载替代数据或重抽研究格的许可。

## 已执行与正在执行

`prepare`、`freeze`、两条新 `run --phase prefix` 和 `run --phase compose` 已完成。`compose-anytime`、`complete-reference` 和固定表 `replay` 的独立入口已在开发目录实际执行，开发证据与正式研究分开。

原 P 命令已正常结束，12/12 原始尾程完成执行，功能尚未评分；下面是执行记录，不是要求再次启动：

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.budgeted_context_study run \
  --phase P \
  --plan configs/budgeted-relation-selection-v1/plan.json \
  --tasks ../hermes-repair-knowledge-private/tasks \
  --skills configs/conditional-applicability-v1/skills \
  --output ../hermes-budgeted-relation-private/study-v1
```

私有接续进程在原 P 全部终止后完成 D 和 C：C实际8条尾程、4个D格不可用。它首次在验收重建阶段停止，记录为 STOPPED_EVALUATE；该记录保留，不代表仍有研究进程。后续验收专用接续命令已正常结束，原始修复样本没有重跑。

## 仅记录复算：已实际执行

以下命令不启动模型、修复尾程或可信验收。正式验收完成后，report、记录 replay 和 export_results 均已成功执行，保留24个计划格。

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.budgeted_context_study report \
  --output ../hermes-budgeted-relation-private/study-v1

PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.budgeted_context_study replay \
  --output ../hermes-budgeted-relation-private/study-v1
```

两个状态均已实际成功使用该状态的 `ledger.json`、`pool.json` 和锁定 D 的 `relations.json` 执行下列隐藏表回放，各生成 8 行、模型调用 0、修复执行 0：

```sh
PYTHONPATH=src /opt/anaconda3/bin/python -m hermes_skilleval.intervention.budgeted_context_study replay \
  --ledger "$selection_dir/ledger.json" \
  --pool "$selection_dir/pool.json" \
  --table "$selection_dir/D/relations.json" \
  --output "$selection_dir/offline-replay.json"
```

`selection_dir` 必须指向新研究的确切 `selection/<instance_id>`。回放仅按请求揭示同一封存关系表，在 8/16/32/48 个请求处比较 A 与 S；它不代表在线延迟，也不把 D 的未知关系补成零。D 完全不可用时，回放保留 `NOT_RUN`，仍导出 P/C 结果。

```sh
PYTHONPATH=src /opt/anaconda3/bin/python scripts/budgeted_relation_selection/export_results.py \
  --study ../hermes-budgeted-relation-private/study-v1 \
  --plan configs/budgeted-relation-selection-v1/plan.json \
  --output artifacts/budgeted-relation-selection-v1
```

导出器验证计划身份与执行记录绑定，以及原补丁与验收捕获摘要一致。它保留全部 24 个计划尾程格、原始补丁、必要 JUnit/收集清单、未运行和中断辅助请求，不导出完整源码副本、会话或凭据。计划自身摘要和字节摘要只是身份依据，不替代干净 base 重建和独立 JUnit 核对。

P 表将原始功能结果与严格预算有效性分别列出；无法证明同预算的格保留功能事实，但不进入同预算收益主张。C 表准备费用单列。局部加载、编码器、候选检索与 MMR 的耗时只能给出实测合计，细分值不可重造。缓存 token、推理 token 是用量子集，不与总量重复相加。

## 验收重建修复：实际成功命令

首次验收遇到原候选空文件权限 0600 与 Git 补丁重建 0644 不一致。独立核对原 source 与 capture snapshot 完整一致后，在新重建目录补充绑定原补丁/清单摘要的权限 sidecar；原失败树未更改，内容或可执行位差异会被拒绝。仅宏 P-A-r1 使用此验收版本，其余19个候选使用原冻结验收。

```sh
PYTHONPATH=src /opt/anaconda3/bin/python scripts/budgeted_relation_selection/continue_acceptance.py \
  --plan configs/budgeted-relation-selection-v1/plan.json \
  --tasks ../hermes-repair-knowledge-private/tasks \
  --skills configs/conditional-applicability-v1/skills \
  --study ../hermes-budgeted-relation-private/study-v1 \
  --overlays ../hermes-evidence-linked-private/test-overlays
```

从原补丁复算时，带 sidecar 的候选必须在干净 base 应用补丁后，按 sidecar 恢复原权限，再验证完整清单；不能删掉该文件后称补丁完整。最终真实执行是22次，不因验收重建修复增加任何 Agent 样本。
