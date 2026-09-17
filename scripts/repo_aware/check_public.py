"""Recompute every committed execution table without models or private assets."""

import argparse
import json
from pathlib import Path

from recompute_execution import recompute
from report import analyze

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=Path("artifacts/repo-aware-routing"))
root = parser.parse_args().root
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

    def equivalent(a, b):
        if isinstance(a, dict) and isinstance(b, dict):
            return a.keys() == b.keys() and all(equivalent(a[k], b[k]) for k in a)
        if isinstance(a, list) and isinstance(b, list):
            return len(a) == len(b) and all(equivalent(x, y) for x, y in zip(a, b))
        if isinstance(a, float) and isinstance(b, (float, int)):
            return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)
        return a == b

    final_index = root / "final-test/index.json"
    if final_index.exists():
        final = json.loads(final_index.read_text())
        launches = [
            event["time"] for event in final["events"] if event["event"] == "launch"
        ]
        if not launches or seal["frozen_at"] >= min(launches):
            raise ValueError("Gate not frozen before final execution")
        for event in final["events"]:
            if event["event"] == "launch" and (
                event.get("gate_sha256") != seal["gate_sha256"]
                or event.get("routing_config_sha256") != final["routing_config_sha256"]
                or event.get("r_version") != seal["r_version"]
            ):
                raise ValueError("Final launch did not bind the frozen gate/config")
        from hermes_skilleval.repo_routing.gate import decide

        for cell in final["cells"]:
            if cell["policy"] == "auto" and cell["execution_status"] == "STARTED":
                if type(cell.get("context_supported")) is not bool:
                    raise ValueError("Missing actual context support state")
                decision = decide(
                    cell["features"],
                    model,
                    final["expected_r_version"],
                    supported=cell["context_supported"] is True,
                )
                if (
                    decision["action"] != cell["action"]
                    or decision["fallback_reason"] != cell["fallback_reason"]
                    or not equivalent(
                        decision["predictions"], cell.get("gate_predictions")
                    )
                ):
                    raise ValueError("Actual auto action disagrees with frozen gate")
    actual = train(fit_rows, calibration_rows, model["r_version"])

    if not equivalent(actual, model):
        raise ValueError("Published gate does not match fit/calibration recipe")
    for phase, feedback in (
        ("gate-fit", fit_rows),
        ("gate-calibration", calibration_rows),
    ):
        records = recompute(root / phase / "index.json")
        by_id = {row["run_id"]: row for row in records["rows"]}
        cells = {
            row["run_id"]: row
            for row in json.loads((root / phase / "index.json").read_text())["cells"]
        }
        if len(feedback) != len(by_id) or {row["run_id"] for row in feedback} != set(
            by_id
        ):
            raise ValueError("Missing or duplicate gate feedback")
        for row in feedback:
            record, cell = by_id[row["run_id"]], cells[row["run_id"]]
            expected = {
                "quality": record["quality"],
                "action": {"native": "N", "fixed": "F", "repo-aware": "R"}[
                    cell["policy"]
                ],
                "realized_action": cell["action"],
                "repair_family": cell["family_id"],
                "repository": cell["repository"],
                "split": phase,
                "features": cell["features"],
                "seconds": record["elapsed_seconds"],
                "tokens": record["total_tokens"],
                "r_version": cell["r_version"],
                "source": "real_execution",
            }
            if any(
                not equivalent(row.get(key), value) for key, value in expected.items()
            ):
                raise ValueError("Gate feedback inputs/costs disagree with execution")
    print(json.dumps({"gate_recomputed": True, "r_version": model["r_version"]}))

if (root / "assist/record.json").exists():
    from check_assist import check_assist

    print(json.dumps(check_assist(root)))
