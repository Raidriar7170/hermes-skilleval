"""Recompute every committed execution table without models or private assets."""

import json
from pathlib import Path

from recompute_execution import recompute
from report import analyze

root = Path("artifacts/repo-aware-routing")
checked = []
for index in sorted(root.glob("*/index.json")):
    data = json.loads(index.read_text())
    if data.get("schema") != "repo-aware-public-execution-v1":
        continue
    expected = json.loads(index.with_name("results.json").read_text())
    if recompute(index) != expected:
        raise ValueError(f"Stale or changed recomputation: {index}")
    report = index.with_name("analysis.json")
    if report.exists() and analyze(index) != json.loads(report.read_text()):
        raise ValueError(f"Stale analysis: {report}")
    checked.append(str(index))
if not checked:
    raise ValueError("No execution evidence found")
print(json.dumps({"records_recomputed": checked}))
