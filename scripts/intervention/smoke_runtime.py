"""End-to-end engineering smoke on an already-seen development mechanism."""

import argparse
import json
from pathlib import Path
import shutil

from hermes_skilleval.intervention.session import dump
from hermes_skilleval.intervention.rollouts import execute, accept
from hermes_skilleval.intervention.value import Encoder, Retriever

p = argparse.ArgumentParser()
p.add_argument("--task", type=Path, required=True)
p.add_argument("--assets", type=Path, required=True)
p.add_argument("--payloads", type=Path, required=True)
p.add_argument("--encoder", required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)
home = a.output / "session-home"
home.mkdir(mode=0o700)
auth = home / "auth.json"
shutil.copyfile(Path.home() / ".codex/auth.json", auth)
auth.chmod(0o600)
try:
    manifest = json.loads((a.payloads / "manifest.json").read_text())
    payloads = {
        s["skill_id"]: (a.payloads / s["path"]).read_text() for s in manifest["skills"]
    }
    retriever = Retriever(Encoder(a.encoder), payloads)
    native = execute(a.task, a.output / "native", home, a.assets, retriever=retriever)
    dump(a.output / "native-result.json", native)
    checkpoints = native["checkpoints"]
    print(
        json.dumps({"native_status": native["status"], "checkpoints": checkpoints}),
        flush=True,
    )
    if native["status"] not in ("COMPLETED", "TIMEOUT"):
        raise RuntimeError(native)
    cp = Path(checkpoints[-1])
    meta = json.loads((cp / "checkpoint.json").read_text())
    kid = meta["candidates"][0]
    tails = []
    for arm, payload in [("N", None), ("skill", payloads[kid])]:
        r = execute(
            a.task,
            a.output / arm,
            home,
            a.assets,
            from_checkpoint=cp,
            payload=payload,
            payload_tokens=next(
                r["tokens"] for r in manifest["skills"] if r["skill_id"] == kid
            )
            if payload
            else 0,
        )
        tails.append({"arm": arm, "execution": r})
        print(
            json.dumps(
                {"arm": arm, "status": r["status"], "seconds": r["tail_seconds"]}
            ),
            flush=True,
        )
    # Labels are requested only after BOTH real continuations finish.
    for tail in tails:
        tail["checks"] = accept(
            a.task, a.output / tail["arm"], a.output / (tail["arm"] + "-checks")
        )
    dump(a.output / "smoke.json", {"native": native, "tails": tails})
finally:
    auth.unlink(missing_ok=True)
