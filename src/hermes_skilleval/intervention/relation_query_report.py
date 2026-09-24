"""Deterministic study export. Reads audits only after selection trajectories lock."""

from collections import Counter

from .linked_context_study import read
from .relation_store import atomic_json


def summarize(root, output):
    from .relation_query_study import DEV, CHECK, metrics, records, state, audit_status

    output.mkdir(parents=True, exist_ok=True)
    ranking, online, packages = [], [], []
    for name in DEV + CHECK:
        ledger, pool, features, panel = state(root, name)
        checks = records(root / "reference" / name / "J/store.json")
        q = records(root / "reference" / name / "Q/store.json")
        strata = {tuple(r["pair"]): r["stratum"] for r in panel}
        for method in ("S", "A0", "R", "V", "V-no-cost"):
            out = root / "replay" / name / method
            if not (out / "final.json").exists():
                continue
            final = read(out / "final.json")

            # Minimal read-only view; no queries or model calls during reporting.
            class View:
                def __init__(self, rows):
                    self.records = rows

                def summary(self):
                    return {
                        "counts": dict(
                            Counter(r["state"] for r in self.records.values())
                        )
                    }

            view = View(records(out / "store.json"))
            for k in (8, 16, 24, 32):
                requested = [tuple(p) for p in final["requested"][:k]]
                partial = View(
                    {
                        p: r if p in requested else {"state": "NOT_ANALYZED"}
                        for p, r in view.records.items()
                    }
                )
                row = {
                    "state": name,
                    "method": method,
                    "k": k,
                    **metrics(ledger, partial, requested, checks),
                }
                row["strata"] = {
                    s: metrics(
                        ledger, view, [p for p in requested if strata[p] == s], checks
                    )
                    for s in ("relevant", "near_distractor", "distribution_control")
                }
                ranking.append(row)
            atomic_json(output / "replay" / name / method / "final.json", final)
            trace = read(out / "trajectory.json")
            compact = []
            for t in trace:
                compact.append(
                    {k: v for k, v in t.items() if k != "pack"}
                    | {
                        "pack_ids": [u["unit_id"] for u in t["pack"]["units"]],
                        "pack_tokens": t["pack"]["tokens"],
                    }
                )
            atomic_json(output / "replay" / name / method / "trajectory.json", compact)
            packages.append(
                package_row(
                    name,
                    method,
                    "replay",
                    final,
                    read(out / "mmr.json"),
                    ledger,
                    checks,
                )
            )
        # Export public identity/label material; never complete corpora, embeddings or raw sessions.
        target = output / "states" / name
        for f in ("ledger.json", "pool.json", "panel.json", "features.json"):
            value = read(root / "inputs" / name / f)
            if f == "ledger.json":
                value = {k: value[k] for k in ("requirements", "weights")}
            atomic_json(target / f, value)
        atomic_json(
            target / "reference.json",
            [
                {
                    "pair": list(p),
                    "proposal": q[p],
                    "audit": checks.get(p),
                    "classification": audit_status(q[p], checks.get(p)),
                    "stratum": strata[p],
                }
                for p in strata
            ],
        )
    for path in sorted((root / "online").glob("*/final.json")):
        f = read(path)
        name = f["state"]
        ledger, pool, _, _ = state(root, name)
        checks = records(root / "online-review" / name / "store.json")
        sampled = {
            tuple(p)
            for p in read(root / "online-review" / name / "sample.json")["pairs"]
        }
        checks = {p: r for p, r in checks.items() if p in sampled}

        class View:
            def __init__(self, rows):
                self.records = rows

            def summary(self):
                return {
                    "counts": dict(Counter(r["state"] for r in self.records.values()))
                }

        view = View(records(path.parent / "store.json"))
        requested = [tuple(p) for p in f["requested"]]
        online.append(
            {
                "run": path.parent.name,
                "state": name,
                "method": f["method"],
                "seconds": f["seconds"],
                "stop_reason": f["stop_reason"],
                "budget_overrun": f["seconds"] > 60,
                "first_positive": f["first_positive"],
                "first_non_mmr": f["first_non_mmr"],
                **metrics(ledger, view, requested, checks),
            }
        )
        packages.append(
            package_row(
                name,
                f["method"],
                path.parent.name,
                f,
                read(path.parent / "mmr.json"),
                ledger,
                checks,
            )
        )
        atomic_json(output / "online" / path.parent.name / "final.json", f)
        atomic_json(
            output / "online" / path.parent.name / "relations.json",
            [
                {
                    "pair": list(p),
                    "proposal": view.records[p],
                    "audit": checks.get(p),
                    "classification": audit_status(view.records[p], checks.get(p)),
                }
                for p in dict.fromkeys(requested)
            ],
        )
        trajectory = (
            read(path.parent / "trajectory.json")
            if (path.parent / "trajectory.json").exists()
            else []
        )
        for t in trajectory:
            t["cost"] = {
                k: v
                for k, v in t["cost"].items()
                if k not in {"thread_id", "usage_events"}
            }
        atomic_json(
            output / "online" / path.parent.name / "trajectory.json", trajectory
        )
    transport = read(root / "transport-observations.json")
    for row in transport:
        events = row.get("usage_events", [])
        row["usage"] = events[-1].get("tokenUsage", {}).get("total") if events else None
    transport = [
        {k: v for k, v in r.items() if k not in {"thread_id", "usage_events"}}
        for r in transport
    ]
    for name, rows in [
        ("pair-ranking", ranking),
        ("real-acquisition", online),
        ("transport-factors", transport),
        ("knowledge-packages", packages),
    ]:
        atomic_json(output / (name + ".json"), rows)
    statuses = {
        "study": "relation-applicability-query-v1",
        "scope": "mechanism_study_on_previously_observed_states",
        "pair_applicability": "IMPLEMENTED_AND_EXERCISED",
        "soft_priority_bound_separation": "VERIFIED",
        "reference_panel": "COMPLETE"
        if all(
            read(root / "reference" / n / r / "done.json")["status"] == "COMPLETE"
            for n in DEV + CHECK
            for r in ("Q", "J")
        )
        else "PARTIAL",
        "reference_truth_level": "MODEL_ASSISTED_SOURCE_AUDIT_NOT_HUMAN_GOLD",
        "human_reviewer_count": 0,
        "same_model_correlated_error_risk": True,
        "controlled_query_replay": "COMPLETE" if len(ranking) == 80 else "PARTIAL",
        "transport_factor_study": "COMPLETE" if len(transport) == 20 else "PARTIAL",
        "online_acquisition": "COMPLETE" if len(online) == 12 else "PARTIAL",
        "supported_relation_gain_over_R": "NOT_ESTABLISHED"
        if len(online) == 12
        else "UNKNOWN",
        "selection_effect": "DECISION_ONLY"
        if any(p["changed_from_mmr"] for p in packages)
        else "FALLBACK_ONLY",
        "functional_repair_gain": "NOT_TESTED_THIS_STAGE",
        "new_repair_agent_calls": 0,
        "new_training": "NOT_IN_SCOPE",
        "default_policy": "UNCHANGED",
        "legacy_evidence": "PRESERVED",
    }
    comparisons = []
    for state_name in CHECK:
        item = {"state": state_name}
        for method in ("A0", "R", "V"):
            group = [
                r for r in online if r["state"] == state_name and r["method"] == method
            ]
            item[method] = {
                "supported_positive_sum": sum(
                    r["audit_counts"].get("SUPPORTED_POSITIVE", 0) for r in group
                ),
                "seconds_sum": sum(r["seconds"] for r in group),
                "trajectories": len(group),
            }
        comparisons.append(item)
    atomic_json(output / "online-comparison.json", comparisons)
    # Strict descriptive flag, not significance: both states, both comparators and
    # the uniform-control replay stratum must agree before asserting this gain.
    positive = all(
        c["V"]["trajectories"] == 2
        and all(
            c["V"]["supported_positive_sum"] > c[m]["supported_positive_sum"]
            for m in ("A0", "R")
        )
        for c in comparisons
    )
    control = {
        (r["state"], r["method"]): r["strata"]["distribution_control"][
            "audit_counts"
        ].get("SUPPORTED_POSITIVE", 0)
        for r in ranking
        if r["k"] == 32
    }
    if positive and all(
        control.get((n, "V"), 0) > control.get((n, m), 0)
        for n in CHECK
        for m in ("A0", "R")
    ):
        statuses["supported_relation_gain_over_R"] = "OBSERVED_WITH_LIMITATIONS"
    atomic_json(output / "status.json", statuses)
    expenses = []
    for phase in ("transport", "reference", "online", "online-review"):
        for path in sorted((root / phase).rglob("cost.json")):
            row = read(path)
            usage = row.get("usage")
            if usage is None and row.get("usage_events"):
                usage = row["usage_events"][-1].get("tokenUsage", {}).get("total")
            expenses.append(
                {
                    "phase": phase,
                    "call": str(path.relative_to(root)),
                    **{
                        k: row.get(k)
                        for k in (
                            "size",
                            "seconds",
                            "status",
                            "setup_seconds",
                            "request_seconds",
                            "censored",
                        )
                    },
                    "usage": usage,
                }
            )
    atomic_json(
        output / "all-call-costs.json",
        {
            "calls": expenses,
            "money": None,
            "money_status": "NO_BILLING_DATA",
            "token_subsets_not_additive": True,
        },
    )
    for file in (
        "inputs.json",
        "freeze.json",
        "transport-material.json",
        "transport-order.json",
        "online-order.json",
        "old-priority-reproduction.json",
        "legacy-call-costs.json",
        "pair-content-example.json",
    ):
        atomic_json(output / file, read(root / file))
    atomic_json(
        output / "reference-costs.json",
        [
            {
                "state": n,
                "role": role,
                **read(root / "reference" / n / role / "done.json"),
            }
            for n in DEV + CHECK
            for role in ("Q", "J")
        ],
    )
    atomic_json(
        output / "transport-sequences.json",
        [
            {
                "sequence": p.parent.name,
                **{k: v for k, v in read(p).items() if k != "thread_ids"},
            }
            for p in sorted((root / "transport").glob("*/sequence.json"))
        ],
    )

    def table(headers, rows):
        return (
            "| "
            + " | ".join(headers)
            + " |\n| "
            + " | ".join(["---"] * len(headers))
            + " |\n"
            + "".join("| " + " | ".join(str(v) for v in r) + " |\n" for r in rows)
        )

    text = "# 关系适用性与获取成本研究\n\nMODEL_ASSISTED_SOURCE_AUDIT_NOT_HUMAN_GOLD；human_reviewer_count=0。同模型独立上下文仍可能共享语义错误。功能修复收益 NOT_TESTED_THIS_STAGE。\n\n## 配对排序\n\n"
    text += table(
        ["状态", "方法", "k", "支持正关系", "支持零", "争议", "未知/未抽样"],
        [
            (
                r["state"],
                r["method"],
                r["k"],
                r["audit_counts"].get("SUPPORTED_POSITIVE", 0),
                r["audit_counts"].get("CORROBORATED_ZERO", 0),
                r["audit_counts"].get("DISPUTED", 0),
                r["audit_counts"].get("REVIEW_UNKNOWN", 0)
                + r["audit_counts"].get("REVIEW_NOT_SAMPLED", 0),
            )
            for r in ranking
        ],
    )
    text += "\n三层明细见 pair-ranking.json；混合面板含 R 构造的相关层，不能解释成全域先验。面板外关系保持未知。\n\n## 真实获取\n\n"
    text += table(
        ["运行", "请求位置", "合法行", "支持正", "支持零", "秒", "停止原因"],
        [
            (
                r["run"],
                r["request_positions"],
                r["valid_rows"],
                r["audit_counts"].get("SUPPORTED_POSITIVE", 0),
                r["audit_counts"].get("CORROBORATED_ZERO", 0),
                round(r["seconds"], 3),
                r["stop_reason"],
            )
            for r in online
        ],
    )
    text += "\n## 接口因素\n\n"
    text += table(
        ["序列", "生命周期", "批量", "合法行", "完整秒", "初始化秒", "状态"],
        [
            (
                r["sequence"],
                r["lifecycle"],
                r["size"],
                r["valid_rows"],
                round(r["seconds"], 3),
                round(r["setup_seconds"], 3),
                r["status"],
            )
            for r in transport
        ],
    )
    text += "\n只报告两次测量序列的原始值；不估计可靠 p95。\n\n## 知识包\n\n"
    text += table(
        ["状态", "运行", "相对MMR变化", "直接规范", "验证模式", "实现上下文", "未知"],
        [
            (
                r["state"],
                r["run"],
                r["changed_from_mmr"],
                r["audit_types"].get("CONTRACT_SUPPORT", 0),
                r["audit_types"].get("VERIFICATION_PATTERN", 0),
                r["audit_types"].get("IMPLEMENTATION_CONTEXT", 0),
                r["unknown_pairs"],
            )
            for r in packages
        ],
    )
    (output / "results.md").write_text(text)
    print(statuses)


def package_row(name, method, run, final, mmr, ledger, checks):
    uids = {u["unit_id"] for u in final["pack"]["units"]}
    domain = [
        (r["requirement_id"], u) for r in ledger["requirements"] for u in sorted(uids)
    ]
    supported = [
        checks[p] for p in domain if checks.get(p, {}).get("state") == "VALID_POSITIVE"
    ]
    return {
        "state": name,
        "method": method,
        "run": run,
        "mmr": mmr,
        "final_pack": final["pack"],
        "changed_from_mmr": uids != {u["unit_id"] for u in mmr["units"]},
        "audit_types": dict(Counter(r["relation"] for r in supported)),
        "audited_pairs": [{"pair": p, "audit": checks.get(p)} for p in domain],
        "mmr_audit_types": dict(
            Counter(
                checks.get((r["requirement_id"], u["unit_id"]), {}).get("relation")
                for r in ledger["requirements"]
                for u in mmr["units"]
                if checks.get((r["requirement_id"], u["unit_id"]), {}).get("state")
                == "VALID_POSITIVE"
            )
        ),
        "unknown_pairs": sum(
            checks.get(p, {}).get("state") not in {"VALID_POSITIVE", "VALID_ZERO"}
            for p in domain
        ),
        "audit_scope": "blind original pair audits, no package quality or repair guarantee",
        "full_requirement_count": len(ledger["requirements"]),
    }
