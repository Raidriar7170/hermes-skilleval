"""Export method-free source rows for a finite independent model review."""

import argparse
import hashlib
import json
from pathlib import Path
import random

p = argparse.ArgumentParser()
p.add_argument("--root", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--tasks", type=Path, required=True)
p.add_argument(
    "--plan",
    type=Path,
    default=Path("configs/repair-knowledge-composition-v1/plan.json"),
)
a = p.parse_args()
tasks = json.loads(a.plan.read_text())["tasks"]
a.output.mkdir(parents=True, exist_ok=True)
mapping = {}
for directory in sorted(a.root.iterdir()):
    poolpath = directory / "full-pool.json"
    if not poolpath.exists():
        poolpath = directory / "pool.json"
    if not poolpath.exists():
        continue
    pool = json.loads(poolpath.read_text())
    ledger = json.loads((directory / "ledger.json").read_text())
    shuffled = list(pool["candidates"])
    random.Random(20260921).shuffle(shuffled)
    units = []
    ids = {}
    for i, c in enumerate(shuffled):
        unit = c["unit"]
        uid = f"Q{i + 1:02}"
        ids[unit["unit_id"]] = uid
        units.append(
            {
                "blind_id": uid,
                "role": unit["claim_role"],
                "symbols": unit["applies_to"],
                "conditions": unit["preconditions"],
                "text": unit["statement"],
                "source_spans": unit["source_spans"],
            }
        )
    packs = []
    packpath = directory / "packs.json"
    if packpath.exists():
        data = list(json.loads(packpath.read_text()).items())
    elif (directory / "selection.json").exists():
        data = list(
            json.loads((directory / "selection.json").read_text())
            .get("packs", {})
            .items()
        )
    else:
        data = []
    random.Random(431).shuffle(data)
    packmap = {}
    for i, (method, pack) in enumerate(data):
        packid = f"P{i + 1}"
        packs.append(
            {
                "blind_pack_id": packid,
                "units": [ids[u["unit_id"]] for u in pack["units"]],
            }
        )
        packmap[packid] = method
    value = {
        "state": directory.name,
        "request": (
            a.tasks
            / next(
                r["instance_id"]
                for r in tasks
                if directory.name in {r["instance_id"], r["mechanism"]}
            )
            / "request.txt"
        ).read_text(),
        "requirements": ledger["requirements"],
        "observations": ledger["observations"],
        "units": units,
        "packs": packs,
        "review_instruction": "Independently judge concrete source relationship to each requirement. No selector scores or method labels are provided. Return positive pairs and explicit rejected or unknown pairs; do not assume a selected pack is correct. Inspect exact conditions, topical distractors, requirement completeness, anchor hits and missing prerequisites. This is model-assisted finite review, not human gold.",
    }
    dest = a.output / (directory.name + ".json")
    dest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    mapping[directory.name] = {
        "unit_mapping": ids,
        "pack_mapping": packmap,
        "input_sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
    }
(a.output.parent / (a.output.name + "-private-mapping.json")).write_text(
    json.dumps(mapping, indent=2) + "\n"
)
