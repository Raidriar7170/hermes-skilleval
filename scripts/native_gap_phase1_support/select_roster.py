"""Metadata-only fixed-seed identity selection; never read outcome fields."""

from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path

P = Path(os.environ.get("NATIVE_GAP_PRIVATE", "/tmp/hermes-native-gap-phase1-private"))
trajectories = json.loads((P / "trajectories.parquet.metadata.json").read_text())
tasks = defaultdict(list)
for path in sorted(P.glob("data_test*.metadata.json")):
    for index, row in enumerate(json.loads(path.read_text())):
        tasks[row["instance_id"]].append(
            dict(
                row,
                file=path.name.replace(".metadata.json", "").replace(
                    "data_", "data/", 1
                ),
                row=index,
            )
        )


def order(identity):
    return hashlib.sha256(("20260925:" + identity).encode()).hexdigest()


repos = ["asottile/pyupgrade", "encode/httpx", "tobymao/sqlglot"]
sources, targets = [], []
for repo in repos:
    ids = sorted(
        {r["instance_id"] for r in trajectories if r["repo"] == repo}, key=order
    )
    reserved = (
        [i for i in ids if len(tasks.get(i, [])) == 1 and tasks[i][0]["docker_image"]][
            :2
        ]
        if repo in repos[:2]
        else []
    )
    targets.extend(reserved)
    sources.extend([i for i in ids if i not in reserved][:10])
roster = {
    "seed": 20260925,
    "repos": repos,
    "repository_selection": "Three explicitly selected Python maintenance repositories, chosen for inspectable Python scope; not representative. Within repository SHA256 seeded identity ordering; no outcome fields read.",
    "source_issues": sources,
    "target_candidates": targets,
    "trajectories": [],
    "tasks": {i: tasks.get(i, []) for i in sources + targets},
}
for iid in sources:
    rows = sorted(
        [(i, x) for i, x in enumerate(trajectories) if x["instance_id"] == iid],
        key=lambda z: order(z[1]["trajectory_id"]),
    )[:2]
    roster["trajectories"] += [{"row": i, **x} for i, x in rows]
target = P / "roster.json"
if target.exists():
    assert json.loads(target.read_text()) == roster, (
        "Existing frozen roster differs; refusing replacement"
    )
else:
    target.write_text(json.dumps(roster, indent=2))
print(
    "Verified 30 source identities and four disjoint candidates without outcome selection"
)
