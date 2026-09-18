"""Live capability qualification on an already-seen development task, not a study."""

import argparse
import json
import os
from pathlib import Path
import shutil

from hermes_skilleval.intervention.session import (
    Session,
    NEUTRAL,
    dump,
    inventory,
    snapshot,
)

p = argparse.ArgumentParser()
p.add_argument("--task", type=Path, required=True)
p.add_argument("--skills", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
p.add_argument("--payload", type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
home = a.output / "session-home"
home.mkdir(mode=0o700)
auth = home / "auth.json"
shutil.copyfile(
    Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json", auth
)
auth.chmod(0o600)
source = a.output / "prefix-source"
shutil.copytree(a.task / "base", source)
# Codex fork re-applies its protected .git mount; it must exist before the prefix.
(source / ".git").mkdir(exist_ok=True)
scratch = a.output / "prefix-scratch"
scratch.mkdir()
public = (a.task / "request.txt").read_text()
try:
    with Session(source, scratch, home, a.skills, a.output / "prefix") as session:
        session.start()
        turn = session.turn(
            public
            + "\n\n"
            + NEUTRAL
            + "\nFor this first segment inspect the source and reproduce the reported behavior, then yield before implementing the fix.",
            180,
        )
        if turn["status"] != "completed":
            raise RuntimeError(turn)
    meta = json.loads((a.output / "prefix/session.json").read_text())
    checkpoint = snapshot(source, scratch, a.output / "checkpoint", meta)
    prefix_files = inventory(source)
    remaining = 600 - session.active_seconds
    results = []
    for arm in ("native", "skill"):
        root = a.output / arm
        shutil.copytree(checkpoint / "source", root / "source")
        shutil.copytree(checkpoint / "scratch", root / "scratch")
        initial = inventory(root / "source")
        with Session(
            root / "source", root / "scratch", home, a.skills, root / "execution"
        ) as tail:
            fork = tail.fork(meta["thread_id"], meta["last_turn_id"])
            # Public returned turns let us compare observable history without reading internal files.
            dump(root / "fork.json", fork)
            prompt = NEUTRAL
            if arm == "skill":
                prompt += "\n\nExternal skill guidance:\n" + a.payload.read_text()
            status = tail.turn(prompt, remaining)
        results.append(
            {
                "arm": arm,
                "remaining_budget": remaining,
                "initial_matches": initial == prefix_files,
                "parent_unchanged": inventory(source) == prefix_files,
                "turn_status": status["status"],
                "active_seconds": tail.active_seconds,
                "changed_files": [
                    k
                    for k, v in inventory(root / "source").items()
                    if initial.get(k) != v
                ],
                "thread_id": tail.thread_id,
            }
        )
        dump(a.output / "qualification.json", {"prefix": meta, "branches": results})
    print(json.dumps(results, indent=2))
finally:
    auth.unlink(missing_ok=True)
