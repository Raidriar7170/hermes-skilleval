"""Build public knowledge and freeze a bounded plan only after source review."""

import argparse
import hashlib
import json
from pathlib import Path
import time

from hermes_skilleval.intervention.local_source_index import build_index, include_legacy
from hermes_skilleval.intervention.linked_context_study import read
from hermes_skilleval.intervention.repair_knowledge import RepairKnowledgeUnit
from hermes_skilleval.intervention.session import dump, inventory

p = argparse.ArgumentParser()
p.add_argument("action", choices=["index", "freeze"])
p.add_argument("--tasks", type=Path, required=True)
p.add_argument("--legacy-knowledge", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--overlays", type=Path)
p.add_argument("--encoder", type=Path, required=True)
a = p.parse_args()
legacy = read("configs/repair-knowledge-composition-v1/plan.json")
review = read("configs/evidence-linked-local-retrieval-v1/selection-review.json")
selected = {r["task_id"] for r in review["rows"] if r["selected"]}
rows = [r for r in legacy["tasks"] if r["instance_id"] in selected]
rows.sort(key=lambda r: r["source_order"])
if a.action == "index":
    for row in rows:
        root = a.output / "public-knowledge" / row["base_commit"]
        if root.exists():
            raise ValueError(
                "Do not overwrite a prepared index; use a versioned output"
            )
        started = time.monotonic()
        base = a.tasks / row["instance_id"] / "base"
        index = build_index(base, repository=row["repo"], revision=row["base_commit"])
        old = [
            RepairKnowledgeUnit.from_dict(u)
            for u in read(a.legacy_knowledge / row["base_commit"] / "units.json")
        ]
        index = include_legacy(index, base, old)
        dump(root / "index.json", index)
        (root / "units.json").symlink_to("index.json")
        (root / "knowledge.txt").write_text(
            "Public exact-base source index. index.json (also units.json) contains source metadata, full source excerpts and resolved direct edges. Normal repository sources remain available under /workspace/repo. These are source quotations, not repair instructions or a correctness oracle.\n"
        )
        dump(
            root / "cost.json",
            {
                "seconds": time.monotonic() - started,
                "model_calls": 0,
                "research_executions": 0,
            },
        )
        print({"mechanism": row["mechanism"], **index["coverage"]}, flush=True)
else:
    plan_path = Path("configs/evidence-linked-local-retrieval-v1/plan.json")
    if plan_path.exists():
        raise ValueError("Frozen plan already exists")
    readiness = read(a.output / "development-readiness.json")
    if readiness["status"] != "READY":
        raise ValueError("Development repairs/source review incomplete")

    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    for name, expected in legacy["representation"]["files"].items():
        if sha(a.encoder / name) != expected:
            raise ValueError("Encoder changed")
    if a.overlays is None:
        raise ValueError("Freeze requires qualified trusted overlays")
    task_rows = []
    for row in rows:
        task = a.tasks / row["instance_id"]
        public = {
            k: row[k]
            for k in (
                "instance_id",
                "mechanism",
                "source_order",
                "base_commit",
                "repo",
                "request_sha256",
                "task_sha256",
            )
        }
        public["files"] = {
            kind: hashlib.sha256(
                json.dumps(inventory(task / kind), sort_keys=True).encode()
            ).hexdigest()
            for kind in ("base", "evaluation")
        }
        if (
            public["files"] != row["files"]
            or sha(task / "request.txt") != row["request_sha256"]
        ):
            raise ValueError("Inherited task changed")
        public["public_knowledge_files"] = inventory(
            a.output / "public-knowledge" / row["base_commit"]
        )
        public["trusted_overlay_files"] = inventory(a.overlays / row["instance_id"])
        if not public["trusted_overlay_files"]:
            raise ValueError("Missing trusted overlay")
        task_rows.append(public)
    files = list(Path("src/hermes_skilleval/intervention").glob("*.py")) + list(
        Path("scripts/evidence_linked_local_retrieval").glob("*.py")
    )
    plan = {
        "study": "evidence-linked-local-retrieval-v1",
        "status": "FROZEN",
        "baseline": "86356edbc42c1116c93df38576357ce7d3625e5a",
        "model": legacy["model"],
        "effort": legacy["effort"],
        "image": legacy["image"],
        "image_id": legacy["image_id"],
        "codex_version": legacy["codex_version"],
        "total_seconds": 600,
        "tail_repeats": 2,
        "arms": ["N", "M-local", "H-sim", "H-link"],
        "order_seed": 20260921,
        "tasks": task_rows,
        "max_research_executions": 9 * len(rows),
        "algorithm_files": {str(f): sha(f) for f in sorted(files)},
        "representation": {
            **{
                k: v
                for k, v in legacy["representation"].items()
                if k
                not in {
                    "state_aggregation",
                    "dynamic_retrieval",
                    "max_tokens_per_field",
                }
            },
            "encoding": "CompleteEncoder: complete text split into max_length minus special-token chunks and token-count-weighted normalized mean; no truncation",
            "dynamic_retrieval": "full public requirement queries with current grounded observation links; fixed 0.3 lexical, 0.6 vector, 0.1 symbol",
        },
        "skills": inventory(Path("configs/conditional-applicability-v1/skills")),
        "defaults_sha256": sha(
            "configs/evidence-linked-local-retrieval-v1/defaults.json"
        ),
        "selection_review_sha256": sha(
            "configs/evidence-linked-local-retrieval-v1/selection-review.json"
        ),
        "semantic_method": "one compact state batch, gpt-5.6-sol medium; no resampling known semantic labels",
        "budget": "Each arm charged the same actual index time + encoder initialization + public ledger/retrieval + observation/relation analysis + all selector time; cloning remains in each tail budget. Independent post-prediction review is separately reported evaluation cost.",
        "default_policy": "UNCHANGED",
        "neural_training": "NOT_IN_SCOPE",
        "legacy_results": "PRESERVED",
    }
    plan["plan_digest"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True).encode()
    ).hexdigest()
    dump(plan_path, plan)
