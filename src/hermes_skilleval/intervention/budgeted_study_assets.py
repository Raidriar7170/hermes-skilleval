"""Final-index preparation and explicit new-study freeze; legacy plans are read-only."""

import hashlib
import json
from pathlib import Path
import subprocess
import time

from .linked_context_study import read
from .local_source_index import build_index, include_legacy
from .relation_store import atomic_json
from .repair_knowledge import RepairKnowledgeUnit
from .session import inventory


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(plan, tasks, legacy_knowledge, output):
    for task in plan["tasks"]:
        root = output / "public-knowledge" / task["base_commit"]
        if root.exists():
            if not (root / "cost.json").exists():
                raise ValueError("Incomplete index preparation; use a versioned output")
            continue
        started = time.monotonic()
        base = tasks / task["instance_id"] / "base"
        index = build_index(base, repository=task["repo"], revision=task["base_commit"])
        legacy = [
            RepairKnowledgeUnit.from_dict(u)
            for u in read(legacy_knowledge / task["base_commit"] / "units.json")
        ]
        include_legacy(index, base, legacy)
        atomic_json(root / "index.json", index)
        (root / "knowledge.txt").write_text(
            "Public exact-base source index; read index.json. Source quotations are not repair instructions or a correctness oracle. Normal sources remain under /workspace/repo.\n"
        )
        atomic_json(
            root / "cost.json",
            {
                "seconds": time.monotonic() - started,
                "scope": "OFFLINE_INDEX_BUILD",
                "index_sha256": sha(root / "index.json"),
                "coverage": index["coverage"],
            },
        )
        print(task["mechanism"], index["coverage"], flush=True)


def freeze(plan_path, tasks, skills, output, encoder, overlays):
    plan = read(plan_path)
    if plan["status"] != "DEVELOPMENT_NOT_FROZEN":
        raise ValueError("Plan already frozen; cannot replace")
    ready = read(output / "development-readiness.json")
    if ready.get("status") != "READY":
        raise ValueError("Development/readiness evidence is incomplete")
    legacy = read("configs/evidence-linked-local-retrieval-v1/plan.json")
    root = Path(__file__).resolve().parents[3]
    tracked = sorted((root / "src/hermes_skilleval/intervention").glob("*.py"))
    tracked += sorted((root / "scripts/budgeted_relation_selection").glob("*.py"))
    plan["algorithm_files"] = {str(p.relative_to(root)): sha(p) for p in tracked}
    plan["skills"] = inventory(skills)
    plan["representation"] = legacy["representation"]
    for name, digest in plan["representation"]["files"].items():
        if sha(encoder / name) != digest:
            raise ValueError("Encoder identity changed")
    actual_image = subprocess.check_output(
        ["docker", "image", "inspect", plan["image"], "--format", "{{.Id}}"], text=True
    ).strip()
    if actual_image != plan["image_id"]:
        raise ValueError("Executor image identity changed")
    version = subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            plan["image"],
            "codex",
            "--version",
        ],
        text=True,
    ).strip()
    if version != plan["codex_version"]:
        raise ValueError("Executor CLI version differs: " + version)
    for task in plan["tasks"]:
        prior = next(
            t for t in legacy["tasks"] if t["instance_id"] == task["instance_id"]
        )
        base = tasks / task["instance_id"]
        for name in ["task.json", "request.txt"]:
            key = "task_sha256" if name == "task.json" else "request_sha256"
            if sha(base / name) != prior[key]:
                raise ValueError("Inherited task changed")
            task[key] = prior[key]
        task["files"] = {
            kind: hashlib.sha256(
                json.dumps(inventory(base / kind), sort_keys=True).encode()
            ).hexdigest()
            for kind in ("base", "evaluation")
        }
        if task["files"] != prior["files"]:
            raise ValueError("Inherited task assets changed")
        task["public_knowledge_files"] = inventory(
            output / "public-knowledge" / task["base_commit"]
        )
        task["trusted_overlay_files"] = inventory(overlays / task["instance_id"])
        if not task["trusted_overlay_files"]:
            raise ValueError("Missing trusted overlay")
    plan["status"] = "FROZEN"
    plan["execution_commit"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    plan["plan_digest"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True).encode()
    ).hexdigest()
    atomic_json(plan_path, plan)
    return plan


def verify(plan, tasks, skills, output, *, overlays=None, encoder=None):
    if plan.get("status") != "FROZEN":
        raise ValueError("New study is not frozen")
    body = {k: v for k, v in plan.items() if k != "plan_digest"}
    if (
        hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        != plan["plan_digest"]
    ):
        raise ValueError("Frozen plan changed")
    if encoder is not None:
        for name, digest in plan["representation"]["files"].items():
            if sha(encoder / name) != digest:
                raise ValueError("Frozen encoder changed")
    root = Path(__file__).resolve().parents[3]
    for name, digest in plan["algorithm_files"].items():
        if sha(root / name) != digest:
            raise ValueError("Frozen algorithm changed: " + name)
    if inventory(skills) != plan["skills"]:
        raise ValueError("Common skill files changed")
    actual = subprocess.check_output(
        ["docker", "image", "inspect", plan["image"], "--format", "{{.Id}}"], text=True
    ).strip()
    if actual != plan["image_id"]:
        raise ValueError("Executor changed")
    for task in plan["tasks"]:
        base = tasks / task["instance_id"]
        if (
            sha(base / "task.json") != task["task_sha256"]
            or sha(base / "request.txt") != task["request_sha256"]
        ):
            raise ValueError("Task changed")
        if (
            inventory(output / "public-knowledge" / task["base_commit"])
            != task["public_knowledge_files"]
        ):
            raise ValueError("Final index changed")
        for kind in ("base", "evaluation"):
            digest = hashlib.sha256(
                json.dumps(inventory(base / kind), sort_keys=True).encode()
            ).hexdigest()
            if digest != task["files"][kind]:
                raise ValueError("Task assets changed")
        if (
            overlays is not None
            and inventory(overlays / task["instance_id"])
            != task["trusted_overlay_files"]
        ):
            raise ValueError("Trusted overlays changed")
