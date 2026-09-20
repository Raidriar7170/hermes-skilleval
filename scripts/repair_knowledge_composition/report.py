"""Generate function-first tables from exported records, never from surrogate scores."""

import argparse
import json
from pathlib import Path

from hermes_skilleval.intervention.repair_content_report import counts


def read(path):
    return json.loads(path.read_text())


def cell(value):
    return f"{value['pass']}/{value['planned']} (未知 {value['unknown']})"


def generate(evidence, plan, output):
    pilot = read(evidence / "pilot-summary.json")
    lock = read(evidence / "pilot-lock.json")
    native = read(evidence / "native-results.json")["rows"]
    lines = [
        "# 修复知识与缺口组合：实际功能结果",
        "",
        "功能成功仅指目标行为通过且保护回归无新增失败。表中未知不记作失败；覆盖、策略与成本不参与此判定。",
        "",
        "## 开发功能主表",
        "",
        "| 机制 | 原生探测 | N续跑 | G提醒 | L旧技能 | M同库MMR | H组合 | H−M |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for state in pilot["states"]:
        arms = state["arms"]
        values = [
            state["mechanism"],
            cell(counts([r for r in native if r["task_id"] == state["task_id"]])),
            *[cell(arms[a]) for a in ["N", "G", "L", "M", "H"]],
            str(state["contrasts"].get("H-M")),
        ]
        lines.append("| " + " | ".join(values) + " |")
    lines += [
        "",
        f"按机制等权 H−M：`{pilot['mechanism_mean_H_minus_M']}`。小样本条件比较不构成部署收益或因果普遍性证明。",
        f"冻结内容路线改善信号机制：`{pilot['content_route_signal_mechanisms']}`。确认规则结果：`{pilot['confirmation_decision']}`。",
        "",
        "## 消融与实际选择（诊断附表）",
        "",
        "| 机制 | H | H-no-gap | H-no-exposure |",
        "|---|---|---|---|",
    ]
    for state in pilot["states"]:
        arms = state["arms"]
        if "H-no-gap" in arms:
            lines.append(
                "| "
                + " | ".join(
                    [
                        state["mechanism"],
                        *[cell(arms[a]) for a in ["H", "H-no-gap", "H-no-exposure"]],
                    ]
                )
                + " |"
            )
    lines += [
        "",
        "以下分解是选择函数值，不是修复增益；完整单元与来源见证据目录。",
        "",
        "| 机制/方法 | 候选索引 | token | 覆盖 | 相关性奖励 | 冗余惩罚 | 暴露惩罚 | 总分 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for state in lock["states"]:
        for method, entry in state["packs"].items():
            pack = entry["pack"]
            scores = pack["scores"]
            lines.append(
                "| "
                + " | ".join(
                    [
                        state["mechanism"] + "/" + method,
                        str(pack["indices"]),
                        str(pack["tokens"]),
                        *[
                            f"{scores[k]:.6f}"
                            for k in [
                                "coverage",
                                "relevance",
                                "redundancy_penalty",
                                "exposure_penalty",
                                "total",
                            ]
                        ],
                    ]
                )
                + " |"
            )
    lines += ["", "## 确认与范围", ""]
    if (evidence / "confirm-summary.json").exists():
        confirm = read(evidence / "confirm-summary.json")
        lines += ["| 新机制 | N | M | H | H−M |", "|---|---|---|---|---|"]
        for state in confirm["states"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        state["mechanism"],
                        *[cell(state["arms"][a]) for a in ["N", "M", "H"]],
                        str(state["contrasts"].get("H-M")),
                    ]
                )
                + " |"
            )
    else:
        lines.append(
            "新机制确认未执行；以上冻结继续规则决定是否触发，不增加重复以追分。"
        )
    observed = {s["task_id"] for s in lock["states"]}
    missing = [
        t["mechanism"]
        for t in plan["tasks"]
        if t["split"] == "dev" and t["instance_id"] not in observed
    ]
    lines += [
        "",
        f"没有合法固定续跑状态的开发机制：`{missing}`。",
        "仅 Ansible 单仓库、4 个开发机制、每格2重复；没有未见仓库泛化证据，也不能排除预训练污染。iterator 保护范围含1个实际PASS与7个既有skip，不等于全仓保护。",
        "",
        "旧六份原补丁只作 `POSTHOC_ACCEPTANCE_ONLY`，目标与保护均通过；不改写历史UNKNOWN，不称技能救回。",
        "",
        "## 工程与复算",
        "",
        "入口见 [reproduction.md](reproduction.md)。公共证据中的 replay 只重算原补丁身份、JUnit、冻结选择与功能表，不代表第二次Agent运行。",
        "默认策略 `UNCHANGED`；新 gain/wait 训练 `NOT_IN_SCOPE`。成本、策略与来源支持均为附表。",
    ]
    output.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    generate(args.evidence, read(args.plan), args.output)
