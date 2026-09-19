"""Freeze original skill bodies into uniform bounded payloads before outcomes."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import tiktoken
from hermes_skilleval.intervention.rollouts import GENERIC
from hermes_skilleval.intervention.session import dump

p = argparse.ArgumentParser()
p.add_argument("--registry", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
registry = json.loads(a.registry.read_text())
tokenizer = tiktoken.get_encoding("o200k_base")
rows = []
for skill in registry["skills"]:
    body = skill["body"]
    parts = body.split("\n\n")
    selected = []
    for part in parts:
        candidate = "\n\n".join([*selected, part])
        if len(tokenizer.encode(candidate)) > 1200:
            break
        selected.append(part)
    payload = "\n\n".join(selected)
    if not payload:
        raise ValueError("first skill section exceeds payload budget")
    path = a.output / (skill["id"] + ".md")
    path.write_text(payload)
    rows.append(
        {
            "skill_id": skill["id"],
            "path": path.name,
            "tokens": len(tokenizer.encode(payload)),
            "source_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
            "complete_body": payload == body,
            "retained_paragraphs": len(selected),
        }
    )

dump(
    a.output / "manifest.json",
    {
        "registry_id": registry["registry_id"],
        "registry_relative_path": os.path.relpath(
            a.registry.resolve(), a.output.resolve()
        ),
        "tokenizer": tokenizer.name,
        "tokenizer_library": "tiktoken==0.12.0",
        "tokenizer_resolution": "GPT-5 family o200k_base proxy; installed tiktoken lacks exact gpt-5.6-sol alias; provider tokenizer UNAVAILABLE",
        "guidance_budget": 1200,
        "selection": "maximal complete paragraph prefix before 1200 tokens; no task conditioning",
        "generic_reminder": GENERIC,
        "generic_tokens": len(tokenizer.encode(GENERIC)),
        "skills": rows,
    },
)
print(json.dumps({"skills": len(rows), "tokens": [r["tokens"] for r in rows]}))
