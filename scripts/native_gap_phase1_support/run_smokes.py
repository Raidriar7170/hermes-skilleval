"""Execute the two preregistered native repair turns once, preserving records."""

import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_gap_phase1 import native_smoke

root = Path(__file__).resolve().parents[2]
private = Path(
    os.environ.get("NATIVE_GAP_PRIVATE", "/tmp/hermes-native-gap-phase1-private")
)
skills = root / "configs/native-gap-phase1-v1/skills"
for ident, iid, image in [
    (
        "smoke-pyupgrade330",
        "asottile__pyupgrade-330",
        "swerebench/sweb.eval.x86_64.asottile_1776_pyupgrade-330",
    ),
    ("smoke-httpx386", "encode__httpx-386", "hermes-native-gap-httpx386:v1"),
]:
    if (private / ident).exists():
        raise SystemExit("Refusing to repeat an existing native attempt: " + ident)
    record = json.loads((private / "trusted-targets" / (iid + ".json")).read_text())
    task = {
        k: record[k]
        for k in ["instance_id", "base_commit", "problem_statement", "repo"]
    }
    frozen = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            root / "configs/native-gap-phase1-v1/plan.json",
            *sorted(skills.glob("*/SKILL.md")),
        ]
    }
    (private / (ident + "-frozen.json")).write_text(json.dumps(frozen, indent=2))
    result = native_smoke(
        private,
        ident,
        task,
        skills,
        image,
        private / "codex-linux-arm64",
        root / "src/hermes_skilleval/_maintenance/docker-seccomp-userns.json",
    )
    print(
        ident,
        result.get("terminal"),
        result.get("candidate_bytes"),
        result["elapsed_seconds"],
        flush=True,
    )
