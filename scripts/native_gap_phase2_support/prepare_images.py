"""Build only qualified prepared images, with offline import-path adaptation."""

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
        adapter = "pythonpath" if iid == "encode__httpx-2523" else "editable"
        qualifier = (
            P
            / (
                "qualification-pythonpath"
                if adapter == "pythonpath"
                else "qualification"
            )
            / iid
            / "result.json"
        )
        result = json.loads(qualifier.read_text())
        assert result["qualified"]
        pulled = json.loads((P / "images" / iid / "result.json").read_text())
        dest = P / "prepared-images" / iid
        dest.mkdir(parents=True, exist_ok=True)
        if (dest / "result.json").exists():
            old = json.loads((dest / "result.json").read_text())
            if old["returncode"] == 0:
                continue
            dest = P / "prepared-images-v3" / iid
            dest.mkdir(parents=True, exist_ok=True)
            if (dest / "result.json").exists():
                continue
        tag = (
            "hermes-phase2-"
            + iid.replace("__", "-")
            + (":v3" if "v3" in str(dest) else ":v1")
        )
        dockerfile = "FROM " + pulled["repo_digests"][0] + "\nWORKDIR /testbed\n"
        if adapter == "editable":
            dockerfile += "RUN source /opt/miniconda3/bin/activate testbed && python -m pip install --no-deps --no-build-isolation -e .\n"
        dockerfile += "ENV PYTHONPATH=/testbed\n"
        (dest / "Dockerfile").write_text(dockerfile)
        started = time.monotonic()
        with (dest / "build.log").open("w") as log:
            r = subprocess.run(
                [
                    "docker",
                    "build",
                    "--platform",
                    "linux/amd64",
                    "--network",
                    "none",
                    "-t",
                    tag,
                    str(dest),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        row = {
            "instance_id": iid,
            "prepared_image": tag,
            "adapter": adapter,
            "returncode": r.returncode,
            "offline_seconds": time.monotonic() - started,
            "source_image_id": pulled["image_id"],
            "source_digest": pulled["repo_digests"][0],
        }
        if r.returncode == 0:
            info = json.loads(
                subprocess.check_output(["docker", "image", "inspect", tag])
            )[0]
            row.update(
                image_id=info["Id"],
                storage_size=info["Size"],
                architecture=info["Architecture"],
            )
        (dest / "result.json").write_text(json.dumps(row, indent=2))
        print(iid, r.returncode, flush=True)
