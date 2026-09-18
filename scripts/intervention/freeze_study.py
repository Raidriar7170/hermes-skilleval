"""Freeze a resource-qualified study before inspecting any policy outcomes."""

import argparse
import hashlib
import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from hermes_skilleval.intervention.session import dump, inventory, IMAGE

p = argparse.ArgumentParser()
for key in (
    "tasks",
    "qualification",
    "controls",
    "payloads",
    "skills",
    "encoder",
    "output",
    "public_output",
):
    p.add_argument("--" + key.replace("_", "-"), type=Path, required=True)
a = p.parse_args()
if a.output.exists() or a.public_output.exists():
    raise ValueError("freeze is immutable")


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


qualification = read(a.qualification)
controls = read(a.controls)
assert len(qualification) == 24 and all(
    r["reference"]["valid"] and r["reference"]["passed"] for r in qualification
)
assert all(r["qualified_negative"] for r in controls)
neg = {r["task_id"] for r in controls}
for r in qualification:
    assert all(
        c["outcome"] == "passed" for c in r["base"]["cases"] if "regression" in c["id"]
    )
    assert r["task_id"] in neg or (r["base"]["valid"] and not r["base"]["passed"])
rows = []
for row in read(a.tasks / "candidate-roster.json"):
    root = a.tasks / row["task_id"]
    rows.append(
        {
            **row,
            "qualification": "REFERENCE_GREEN_NEGATIVE_REJECTED",
            "files": {
                scope: inventory(root / scope)
                for scope in ("base", "trusted", "reference")
            },
            "request_sha256": sha(root / "request.txt"),
            "profile_sha256": sha(root / "task.json"),
        }
    )
# Exactly one quarter of all possible train/dev opportunities, before outcomes.
potential = [
    r["task_id"] + ":" + s
    for r in rows
    if r["split"] != "test"
    for s in ("E0", "E1", "E2")
]
repeats = sorted(random.Random(7170).sample(potential, len(potential) // 4))
encoder_files = {
    p.name: sha(p)
    for p in a.encoder.iterdir()
    if p.name
    in (
        "model.safetensors",
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "vocab.txt",
    )
}
assert "model.safetensors" in encoder_files
image_id = subprocess.check_output(
    ["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"], text=True
).strip()
protocol = {
    "version": "asi-v1",
    "status": "FROZEN",
    "frozen_at": datetime.now(timezone.utc).isoformat(),
    "tasks": rows,
    "total_seconds": 600,
    "order_seed": 7170,
    "repeat_states": repeats,
    "final_repeats": 2,
    "split_counts": {"train": 12, "dev": 4, "test": 8},
    "max_offline_tails": 240,
    "final_runs": 96,
    "resource_basis": {
        "local_ram_gib": 48,
        "disk_free_gib_observed": 495,
        "weekly_remaining_percent_observed": 81,
        "remote_gpu": False,
        "paid_resource_purchase": False,
        "capacity_guaranteed": False,
    },
    "agent": {
        "image": IMAGE,
        "image_id": image_id,
        "codex_version": "0.154.0",
        "model": "gpt-5.6-sol",
        "effort": "medium",
        "activity_budget_includes": "source/scratch copies, session setup, completed turns, state extraction, checkpoints, online scoring, teardown",
        "billing": "UNKNOWN",
    },
    "representation": {
        "encoder": "sentence-transformers/all-MiniLM-L6-v2",
        "revision": a.encoder.name,
        "files": encoder_files,
        "max_tokens_per_field": 256,
        "dimensions": 384,
        "state_aggregation": "mean of separately encoded public failure, source and diff",
        "dynamic_retrieval": "mean of separately encoded request, public failure and source",
    },
    "payloads": inventory(a.payloads),
    "skills": inventory(a.skills),
    "registry_sha256": sha(
        a.payloads / read(a.payloads / "manifest.json")["registry_relative_path"]
    ),
    "guidance": read(a.payloads / "manifest.json"),
    "learning": {
        "width": 64,
        "epochs_grid": [80, 160],
        "seed": 7170,
        "selection": "dev task macro paired utility MSE",
        "cost_weights": {"time": 0.05, "context": 0.02},
        "margin": 0,
        "folds": "nested leave-task-out",
        "no_state_candidates": "static top two, no observed-state retrieval",
        "quality": "target and protected regression and file policy pass",
    },
    "methods": ["N0", "S1", "R1", "H-myopic", "H-no-state", "H-full"],
    "stochasticity": "paired observable prefixes; hidden RNG not cloned; all fixed repeats retained",
    "stop_policy": "retain every attempted sample; infrastructure unknown is never a negative label; no outcome-driven resampling or task replacement",
    "qualification_sha256": sha(a.qualification),
    "negative_controls_sha256": sha(a.controls),
    "implementation_at_freeze": inventory(Path("src/hermes_skilleval/intervention")),
}
# Exclude interpreter caches from the frozen source scope.
protocol["implementation_at_freeze"] = {
    k: v
    for k, v in protocol["implementation_at_freeze"].items()
    if "__pycache__" not in k and k.endswith(".py")
}
dump(a.output, protocol)
public = {
    **protocol,
    "tasks": [
        {k: v for k, v in row.items() if k not in ("files", "request")} for row in rows
    ],
}
public["private_protocol_sha256"] = sha(a.output)
dump(a.public_output, public)
print(
    json.dumps(
        {
            "frozen": str(a.output),
            "tasks": 24,
            "max_offline_tails": 240,
            "final_runs": 96,
            "repeat_states": repeats,
        }
    )
)
