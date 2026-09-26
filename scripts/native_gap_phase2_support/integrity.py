"""Recheck frozen private resources without exposing their contents."""

import hashlib
from pathlib import Path

P = Path("/tmp/hermes-native-gap-phase2-private")
OLD = Path("/tmp/hermes-native-gap-phase1-private")
MODEL = (
    Path.home()
    / ".cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
)


def verify_private_assets(freeze):
    bases = {
        "encoder": MODEL,
        "linux-client": OLD / "codex-linux-arm64",
        "metadata-index": P,
        "system-skills": P / "permissions-v3/state/skills",
        "author-parser": OLD / "swebench-fork/swebench/harness/log_parsers",
    }
    for entry in freeze["private_assets"]:
        base = (
            P / "trusted-targets"
            if entry["asset"].startswith("trusted-task-")
            else bases[entry["asset"]]
        )
        f = base / entry["path"]
        if hashlib.sha256(f.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(
                "frozen private asset changed: " + entry["asset"] + "/" + entry["path"]
            )
