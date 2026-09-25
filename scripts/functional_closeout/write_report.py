"""Write the three-table closeout from saved records only."""

import argparse
from pathlib import Path

from hermes_skilleval.intervention.functional_closeout import STUDY
from hermes_skilleval.intervention.linked_context_study import read


def fmt(value):
    return (
        "UNKNOWN"
        if value is None
        else f"{value:.2f}"
        if isinstance(value, float)
        else str(value)
    )


def write(repo, private):
    plan = read(repo / "configs" / STUDY / "plan.json")
    report = read(private / "report.json")
    terminal = report["terminal"]
    names = {t["instance_id"]: t["mechanism"] for t in plan["tasks"]}
    out = repo / "docs/research" / STUDY
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "# N/MMR/R 真实功能对照与阶段收束",
        "",
        "本轮完成4个前缀、24条真实尾程及8条独立R获取。原始功能结果为N 6/8、M 8/8、R 8/8通过；R相对M没有功能差异。四个机制均为探索性复用，共享公开前缀的重复不构成24个独立问题。",
        "",
        "**关键限制：**共同候选准备之前的checkpoint验证漏计且没有可恢复的原始测量。初版前缀/获取完整保留，尾程启动前已修复后续准备计时；全部M/R预算合法性仍为UNKNOWN_PREPARATION_COST，不能把原始功能差异称为严格600秒自付成本下的增益。未通过重抽任务、重跑R或补造旧耗时弥补缺口。",
        "",
        f"实际状态：`integration={terminal['integration']}`，`functional_comparison={terminal['functional_comparison']}`；对M增益 `{terminal['functional_gain_over_M']}`，对N增益 `{terminal['functional_gain_over_N']}`。",
        "",
        "## 表一：功能主表",
        "",
        "| 机制 | 臂 | PASS | FAIL | UNKNOWN | 计划 | 预算有效/协议偏差 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in report["functional_table"]:
        group_costs = [
            c
            for c in report["cost_table"]
            if c["task_id"] == row["task_id"] and c["arm"] == row["arm"]
        ]
        valid = sum(
            c["budget_status"] == "VALID" and c["protocol_deviation"] is None
            for c in group_costs
        )
        deviations = sorted(
            {c["protocol_deviation"] or c["budget_status"] for c in group_costs}
        )
        lines.append(
            f"| {row['mechanism']} | {row['arm']} | {row['PASS']} | {row['FAIL']} | {row['UNKNOWN']} | {row['planned']} | {valid}/{row['planned']}; {', '.join(deviations)} |"
        )
    for name, contrast in report["contrasts"].items():
        lines += [
            "",
            f"{name}：任务等权原始均值差 {fmt(contrast['task_mean_difference'])}；胜/负/平/未知 {contrast['task_counts']}；未知下界/上界 {contrast['missing_bounds']}。预算协议支持增益声明：{contrast['protocol_valid_for_gain_claim']}。",
        ]
    lines += [
        "",
        "标签来自完整原候选在干净base上的可信目标与保护检查。文件policy、预算与注入状态不改写功能标签。4个机制只支持原始计数，不报告总体显著性或因果唯一性。",
        "",
        "## 表二：实际干预与费用",
        "",
        "| 机制/臂/重复 | 前缀秒 | 共同准备秒 | R获取秒 | 已计准备秒 | 尾程可用秒 | 实际含准备秒 | 单元/tokens | 同MMR | 注入观察 | 后备原因 | 预算状态 |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---|",
    ]
    for row in report["cost_table"]:
        lines.append(
            f"| {names[row['task_id']]}/{row['arm']}/{row['repeat']} | {fmt(row['prefix_seconds'])} | {fmt(row['common_preparation_seconds'])} | {fmt(row['R_acquisition_seconds']) if row['arm'] == 'R' else 'N/A'} | {fmt(row['preparation_seconds'])} | {fmt(row['tail_budget_seconds'])} | {fmt(row['actual_including_preparation_seconds'])} | {row['units']}/{row['tokens']} | {fmt(row['same_as_mmr']) if row['arm'] == 'R' else 'N/A'} | {fmt(row['injection_observed']) if row['arm'] != 'N' else 'N/A'} | {row['fallback_reason'] or '—'} | {row['budget_status']} |"
        )
    lines += [
        "",
        "N/A表示该臂不适用，并非缺失测量；“实际含准备秒”不含单列的公共前缀。准备费包含共同检索/MMR、R自己的编码/配对特征/关系获取和尾程公共准备；共享物理计算按同一实测费记入各对应重复。原共同checkpoint验证未知费用没有填零，表中数值仅为已计组件。R后备保留全部费用。离线索引另列于asset-summary.json；服务等待属于方法费，金额无账单依据。",
        "",
        "## 表三：知识—行为案例",
        "",
        "| 机制 | M/R原文与角色 | 后续可观察改动 | 验收原始结果 |",
        "|---|---|---|---|",
    ]
    for task in plan["tasks"]:
        cases = [
            r
            for r in report["knowledge_behavior_table"]
            if r["task_id"] == task["instance_id"] and r["arm"] in {"M", "R"}
        ]
        requirements = {
            "python-identifier-validation": "统一Python标识符判断及关键字/类型边界",
            "filter-attribute-forwarding": "min/max传递attribute等参数，并保留旧环境后备行为",
            "variable-file-cache": "恢复变量文件缓存，避免重复读取与解密",
            "invalid-host-field-errors": "对非法hosts输入给出合适错误，并保留拒绝后的输入状态",
        }
        for case in cases:
            roles = sorted({u.get("claim_role", "unknown") for u in case["units"]})
            paths = case["observed_behavior"]["changed_files"] or []
            sources = sorted(
                {
                    span["path_or_public_url"]
                    for u in case["units"]
                    for span in u.get("source_spans", [])
                }
            )
            visibility = sorted(
                {
                    u["visibility"]
                    for u in case["observed_behavior"]["source_visibility"]
                }
            )
            lines.append(
                f"| {task['mechanism']}/{case['arm']}{case['repeat']}：{requirements[task['mechanism']]} | {', '.join(roles)}；{'; '.join(sources)}；{', '.join(visibility)}；原文及包引用见[逐格证据](../../../artifacts/{STUDY}/knowledge-behavior.json) | {'; '.join(paths[:6]) or '没有已确认文件变化'} | {case['functional']} |"
            )
    lines += [
        "",
        "knowledge-behavior.json保留逐格载荷引用、前缀精确原文可见性、后续已完成命令和完整改动路径。路径或内容在输入中出现只证明可观察暴露；不能推断模型内部采用过程，也不能声称知识是变化的唯一原因。没有G臂，亦不能拆分特定知识与额外注意力的全部贡献。",
        "",
        "hosts案例中，N1/N2都通过20项目标检查，但同一保护项`test_play_empty_hosts[]`失败：补丁只拒绝None或空序列，遗漏空字符串。M1/M2和R1/R2保留空字符串拒绝，50项检查均通过。M包包含旧Play.load的空值守卫与post_validate；R1另含公开测试注释`test that play errors if len(hosts) == 0`，R2则没有该测试片段。这些资料在记录的前缀中未观察到，之后实际进入输入。它们与补丁差异构成可观察案例，但不能证明片段导致修复，更不能解释为R胜过MMR。完整原补丁见functional/invalid-host-field-errors。",
        "",
        "filter案例的两条R都后备到MMR，同包四格全通过且保留36.56/42.15秒来源获取费用。variable-file-cache中R包不同于MMR，R/M/N仍全部通过。这分别说明后备可交付和选择确实改变内容，均不构成R的功能优势；也没有R相对M的救回或退化案例可编写。四个公共前缀在固定边界均未标记任务已完成。",
        "",
        "## 简化架构",
        "",
        "```mermaid",
        "flowchart LR",
        "P[公开需求与可观察前缀] --> N[原生继续]",
        "P --> C[局部候选与MMR]",
        "C --> M[原文知识包]",
        "C --> R[R逐要求关系查询]",
        "R --> S[既有集合选择或MMR后备]",
        "S --> A[同前缀真实续跑]",
        "M --> A",
        "N --> V[完整补丁重建与可信验收]",
        "A --> V",
        "```",
        "",
        "| 主架构保留 | 历史实验保留 | 未证实模块 |",
        "|---|---|---|",
        "| 公开状态、局部检索、原文包、隔离续跑、完整重建及目标/保护验收 | LoRA静态路由、gain/wait、V、稠密关系等旧代码及记录 | R相对MMR/原生的严格自付成本功能收益；单独排序系数因果贡献 |",
        "",
        "默认策略保持UNCHANGED；没有建立替代MMR/原生的证据。保留R作为已接通的研究管线，不自动上线、不删除历史、不开启下一轮实验。",
        "",
        "## 90秒说明",
        "",
        f"我做的是编程Agent在修复过程中如何利用外部知识的研究与评测接线。当前主干先从公开需求和Agent已看到的状态构建局部候选，再比较原生继续、MMR原文包，以及R关系查询加既有组包。三个方法从同一公开前缀分叉，保留完整候选，用隔离的目标测试和保护回归验收。本轮预登记{terminal['tasks_preregistered']}个机制，完成{terminal['public_prefixes_completed']}个前缀、启动{terminal['repair_tails_started']}条尾程及{terminal['R_acquisitions_started']}条独立R获取。原始验收N为6/8通过，M和R均为8/8；R对MMR没有功能增量。R有{terminal['R_non_MMR_payloads']}条载荷不同于MMR，{terminal['R_fallbacks']}条后备，但选择变化不等于修复收益。实验还发现候选准备前的校验耗时漏计，我保留原记录并标明预算不确定，没有重跑挑结果。因此这轮交付是可追溯的真实功能对照和阶段收束，没有建立R替代MMR或原生的证据，也没有训练或发布新默认策略。",
        "",
        "## 简历可用事实",
        "",
        f"- 实现同可观察前缀的N/MMR/R编程Agent修复对照，完成{terminal['public_prefixes_completed']}个公共前缀、启动{terminal['repair_tails_started']}条真实续跑；基于完整原补丁重建与独立目标/保护检查输出PASS/FAIL/UNKNOWN。",
        f"- 将任务局部检索、逐要求关系查询和原文知识包接入真实Codex续跑，保留{terminal['R_acquisitions_started']}条独立获取、实际载荷与成本记录；明确记录计时缺口，未宣称算法收益或生产业务成功。",
        "",
        "## 执行身份与交付边界",
        "",
        f"前缀/获取源码：`{plan['execution_commit']}`。尾程计时源码：`{plan.get('tail_execution_commit', plan['execution_commit'])}`。当前计划摘要：`{plan['plan_digest']}`。初版冻结计划和锁包摘要保持原样。",
        "",
        "本轮只交付Draft PR，不合并、不ready、不发布；验证口径见review.md；交付HEAD及其CI以本Draft PR的当前提交与检查为准。实际命令见reproduction.md。",
    ]
    (out / "recap.zh.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--private", type=Path, required=True)
    args = parser.parse_args()
    write(args.repo, args.private)
