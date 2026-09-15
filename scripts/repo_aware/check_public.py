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

# Gate fitting is deterministic and lightweight; verify its published recipe too.
gate_root = root / "gate"
if (gate_root / "model.json").exists():
    import math
    import hashlib
    from gate_recipe import train

    def read_rows(path):
        return [
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ]

    fit_rows = read_rows(gate_root / "fit.jsonl")
    calibration_rows = read_rows(gate_root / "calibration.jsonl")
    model = json.loads((gate_root / "model.json").read_text())
    seal = json.loads((gate_root / "freeze.json").read_text())
    for name, key in (
        ("model.json", "gate_sha256"),
        ("fit.jsonl", "fit_sha256"),
        ("calibration.jsonl", "calibration_sha256"),
    ):
        if hashlib.sha256((gate_root / name).read_bytes()).hexdigest() != seal[key]:
            raise ValueError("Gate freeze bytes mismatch")
    for name, digest in seal["recipe_sha256"].items():
        if (
            name not in ("train_gate.py", "gate_recipe.py")
            or hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            != digest
        ):
            raise ValueError("Gate training recipe changed after freeze")
    final_index = root / "final-test/index.json"
    if final_index.exists():
        final = json.loads(final_index.read_text())
        launches = [
            event["time"] for event in final["events"] if event["event"] == "launch"
        ]
        if not launches or seal["frozen_at"] >= min(launches):
            raise ValueError("Gate not frozen before final execution")
        from hermes_skilleval.repo_routing.gate import decide

        for cell in final["cells"]:
            if cell["policy"] == "auto" and cell["execution_status"] == "STARTED":
                decision = decide(cell["features"], model, final["expected_r_version"])
                if decision["action"] != cell["action"]:
                    raise ValueError("Actual auto action disagrees with frozen gate")
    actual = train(fit_rows, calibration_rows, model["r_version"])

    def equivalent(a, b):
        if isinstance(a, dict) and isinstance(b, dict):
            return a.keys() == b.keys() and all(equivalent(a[k], b[k]) for k in a)
        if isinstance(a, list) and isinstance(b, list):
            return len(a) == len(b) and all(equivalent(x, y) for x, y in zip(a, b))
        if isinstance(a, float) and isinstance(b, (float, int)):
            return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)
        return a == b

    if not equivalent(actual, model):
        raise ValueError("Published gate does not match fit/calibration recipe")
    for phase, feedback in (
        ("gate-fit", fit_rows),
        ("gate-calibration", calibration_rows),
    ):
        records = recompute(root / phase / "index.json")
        qualities = {row["run_id"]: row["quality"] for row in records["rows"]}
        if any(row["quality"] != qualities[row["run_id"]] for row in feedback):
            raise ValueError("Gate feedback disagrees with independent verification")
    print(json.dumps({"gate_recomputed": True, "r_version": model["r_version"]}))
