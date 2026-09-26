"""Prepared-image acquisition; timings are offline, transfer bytes unavailable."""

import json
from pathlib import Path
import subprocess
import time

P = Path("/tmp/hermes-native-gap-phase2-private")
ROOT = Path(__file__).resolve().parents[2]
split = json.loads(
    (ROOT / "configs/native-gap-phase2-same-library-v1/split.json").read_text()
)
for ids in split["pilot_task_candidates"].values():
    for iid in ids[:2]:
        d = json.loads((P / "trusted-targets" / f"{iid}.json").read_text())
        out = P / "images" / iid
        out.mkdir(parents=True, exist_ok=True)
        if (out / "result.json").exists():
            continue
        started = time.monotonic()
        with (out / "pull.log").open("w") as log:
            r = subprocess.run(
                ["docker", "pull", "--platform", "linux/amd64", d["docker_image"]],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        row = {
            "instance_id": iid,
            "image": d["docker_image"],
            "returncode": r.returncode,
            "offline_seconds": time.monotonic() - started,
            "network_bytes": "UNKNOWN_DOCKER_SHARED_LAYER_TRANSFER_NOT_MEASURED",
        }
        if r.returncode == 0:
            info = json.loads(
                subprocess.check_output(
                    ["docker", "image", "inspect", d["docker_image"]]
                )
            )[0]
            row.update(
                image_id=info["Id"],
                repo_digests=info["RepoDigests"],
                platform=info["Architecture"],
                storage_size=info["Size"],
            )
        (out / "result.json").write_text(json.dumps(row, indent=2))
        print(iid, r.returncode, flush=True)
