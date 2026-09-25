import json
import time
import urllib.request
import urllib.parse
import concurrent.futures
from pathlib import Path

P = Path(
    __import__("os").environ.get(
        "NATIVE_GAP_PRIVATE", "/tmp/hermes-native-gap-phase1-private"
    )
)
r = json.loads((P / "roster.json").read_text())
rev = json.loads((P / "SWE-rebench-openhands-trajectories-info.json").read_text())[
    "sha"
]
out = P / "raw-selected-trajectories"
out.mkdir(exist_ok=True)


def one(x):
    t = time.monotonic()
    u = "https://datasets-server.huggingface.co/rows?" + urllib.parse.urlencode(
        {
            "dataset": "nebius/SWE-rebench-openhands-trajectories",
            "config": "default",
            "split": "train",
            "offset": x["row"],
            "length": 1,
        }
    )
    try:
        response = urllib.request.urlopen(u, timeout=75)
        b = response.read()
        d = json.loads(b)
        assert response.headers.get("x-revision") == rev, "revision mismatch"
        assert (
            len(d["rows"]) == 1
            and d["rows"][0]["row"]["trajectory_id"] == x["trajectory_id"]
        ), "identity mismatch"
        (out / (x["trajectory_id"] + ".json")).write_bytes(b)
        return {
            **x,
            "bytes": len(b),
            "seconds": time.monotonic() - t,
            "revision": rev,
            "truncated_cells": d["rows"][0]["truncated_cells"],
            "status": "FETCHED",
        }
    except Exception as e:
        return {
            **x,
            "status": "ERROR",
            "error": str(e),
            "seconds": time.monotonic() - t,
        }


with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    results = []
    for v in ex.map(one, r["trajectories"]):
        results.append(v)
        (P / "trajectory-detail-fetch.json").write_text(json.dumps(results, indent=2))
        print(len(results), v["status"], v.get("bytes"), flush=True)
