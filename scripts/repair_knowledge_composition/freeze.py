"""Freeze before first repair sample. Refuses to replace a prior protocol."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from hermes_skilleval.intervention.session import dump, inventory


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for key in ["pool", "tasks", "knowledge", "qualification", "preflight", "output"]:
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("existing protocol")
    pool = json.loads(a.pool.read_text())
    qual = {r["task_id"]: r for r in json.loads(a.qualification.read_text())["rows"]}
    pre = json.loads(a.preflight.read_text())
    if pre["advertised"] is not True or pre["model"] != "gpt-5.6-sol":
        raise ValueError("model unavailable")
    rows = []
    for row in pool["rows"]:
        tid = row["instance_id"]
        task = a.tasks / tid
        if not qual[tid]["qualified"]:
            raise ValueError("unqualified source")
        # Identical entry point to the public offline knowledge library for all arms.
        note = "\n\nShared environment: public maintenance knowledge is readable at /workspace/public-docs/knowledge.txt and units.json. These are optional source quotations available equally to every continuation. For local tests use PYTHONPATH=lib:test/lib and set ANSIBLE_LOCAL_TEMP=/workspace/scratch/ansible-tmp and HOME=/workspace/scratch as needed.\n"
        request = task / "request.txt"
        if note not in request.read_text():
            request.write_text(request.read_text() + note)
        rows.append(
            {
                **row,
                "files": {
                    scope: hashlib.sha256(
                        json.dumps(inventory(task / scope), sort_keys=True).encode()
                    ).hexdigest()
                    for scope in ["base", "evaluation"]
                },
                "request_sha256": sha(request),
                "task_sha256": sha(task / "task.json"),
                "public_knowledge_files": inventory(a.knowledge / row["base_commit"]),
                "knowledge_sha256": sha(
                    a.knowledge / row["base_commit"] / "units.json"
                ),
            }
        )
    image = "hermes-repair-knowledge-executor:v1"
    image_id = subprocess.check_output(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True
    ).strip()
    codex_version = subprocess.check_output(
        ["docker", "run", "--rm", "--network", "none", image, "codex", "--version"],
        text=True,
    ).strip()
    if codex_version != "codex-cli 0.154.0":
        raise ValueError("inherited Codex version changed: " + codex_version)
    source_files = [
        "src/hermes_skilleval/intervention/repair_knowledge.py",
        "src/hermes_skilleval/intervention/repair_composer.py",
        "src/hermes_skilleval/intervention/repair_content_report.py",
        "scripts/repair_knowledge_composition/build_corpus.py",
    ]
    encoder = (
        Path.home()
        / ".cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    )
    representation = json.loads(
        Path("configs/adaptive-skill-intervention-v1/protocol.json").read_text()
    )["representation"]
    for filename, expected in representation["files"].items():
        if sha(encoder / filename) != expected:
            raise ValueError("frozen encoder differs")
    dump(
        a.output,
        {
            "study": "repair-knowledge-composition-v1",
            "status": "FROZEN",
            "baseline": "b87a39daca9e616ba80305eb0bf228f37605c4cb",
            "model": "gpt-5.6-sol",
            "effort": "medium",
            "codex_version": codex_version,
            "image": image,
            "image_id": image_id,
            "total_seconds": 600,
            "native_repeats": 2,
            "tail_repeats": 2,
            "max_research_executions": 98,
            "max_development_executions": 56,
            "order_seed": 20260920,
            "guidance_token_limit": 1200,
            "max_units": 4,
            "max_candidates": 24,
            "mmr_lambda": 0.7,
            "alpha": 0.1,
            "beta": 0.1,
            "gamma": 0.05,
            "representation": representation,
            "knowledge_model_calls": 0,
            "selection_model_calls": 0,
            "checkpoint": "First native repeat first public E1, otherwise first delivery E2; no outcome filtering",
            "continuation_rule": "Complete planned pilot/ablations, at least two mechanisms M or H mean exceeds max(N,G,L); H need not beat M. No hyperparameter search.",
            "primary": "target behavior and no new protected regression; H-M primary composition comparison",
            "tasks": rows,
            "algorithm_files": {s: sha(Path(s)) for s in source_files},
            "skills": inventory(Path("configs/conditional-applicability-v1/skills")),
            "payloads": inventory(
                Path("configs/adaptive-skill-intervention-v1/payloads")
            ),
            "qualification_sha256": sha(a.qualification),
            "default_policy": "UNCHANGED",
            "new_gain_wait_training": "NOT_IN_SCOPE",
        },
    )
    print("FROZEN", len(rows), "tasks", image_id)
