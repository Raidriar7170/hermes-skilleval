from pathlib import Path
import json
import time
import pyarrow.parquet as pq
from scan import Remote

P = Path(
    __import__("os").environ.get(
        "NATIVE_GAP_PRIVATE", "/tmp/hermes-native-gap-phase1-private"
    )
)
r = json.loads((P / "roster.json").read_text())
rev = json.loads((P / "SWE-rebench-info.json").read_text())["sha"]
cost = []
for file in sorted({v[0]["file"] for v in r["tasks"].values() if len(v) == 1}):
    t = time.monotonic()
    f = Remote(
        f"https://huggingface.co/datasets/nebius/SWE-rebench/resolve/{rev}/{file}"
    )
    q = pq.ParquetFile(f)
    wanted = {
        v[0]["row"]: k
        for k, v in r["tasks"].items()
        if len(v) == 1 and v[0]["file"] == file
    }
    off = 0
    for g in range(q.num_row_groups):
        count = q.metadata.row_group(g).num_rows
        sel = {i - off: k for i, k in wanted.items() if off <= i < off + count}
        if sel:
            tab = q.read_row_group(g)
            for i, k in sel.items():
                row = tab.slice(i, 1).to_pylist()[0]
                d = P / (
                    "trusted-targets" if k in r["target_candidates"] else "source-tasks"
                )
                d.mkdir(exist_ok=True)
                (d / (k + ".json")).write_text(json.dumps(row))
        off += count
    cost.append(
        {
            "file": file,
            "bytes": f.bytes,
            "requests": f.requests,
            "seconds": time.monotonic() - t,
        }
    )
    print(cost[-1], flush=True)
(P / "task-detail-cost.json").write_text(json.dumps(cost, indent=2))
for k in r["target_candidates"]:
    d = json.loads((P / "trusted-targets" / (k + ".json")).read_text())
    print(k, d["docker_image"], d["install_config"], flush=True)
