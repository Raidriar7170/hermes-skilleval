"""Extract action feedback from actual independently checked replay records."""

import argparse
import json
from pathlib import Path


def collect(protocol_path):
    protocol = json.loads(Path(protocol_path).read_text())
    config = json.loads(Path(protocol["routing_config"]).read_text())
    records = []
    for cell in protocol["cells"]:
        action = {"native": "N", "fixed": "F", "repo-aware": "R"}[cell["policy"]]
        directory = Path(protocol["output"]) / cell["run_id"]
        run = json.loads((directory / "run.json").read_text())
        route = json.loads((directory / "routing.json").read_text())
        task = json.loads(
            (Path(protocol["tasks"]) / cell["task_id"] / "task.json").read_text()
        )
        if route["r_version"] != config["r_version"]:
            raise ValueError("R version mismatch in feedback")
        quality = (
            int(run["resolved"])
            if run.get("execution_status") == "STARTED"
            and run.get("verifier_valid") is True
            and type(run.get("resolved")) is bool
            else None
        )
        usage = run.get("usage")
        tokens = (
            usage["input_tokens"] + usage["output_tokens"]
            if usage
            and usage.get("input_tokens") is not None
            and usage.get("output_tokens") is not None
            else None
        )
        records.append(
            {
                "run_id": cell["run_id"],
                "repair_family": task["family_id"],
                "repository": task["repository"],
                "split": task["split"],
                "features": route["features"],
                "action": action,
                "realized_action": route["action"],
                "r_version": route["r_version"],
                "source": "real_execution",
                "quality": quality,
                "seconds": run.get("pipeline_wall_seconds"),
                "tokens": tokens,
                "execution_status": run["execution_status"],
                "verifier_valid": run.get("verifier_valid"),
                "dollar_cost": None,
            }
        )
    return records


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--protocol", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    rows = collect(a.protocol)
    with a.output.open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    print(
        json.dumps(
            {
                "observations": len(rows),
                "known_quality": sum(r["quality"] is not None for r in rows),
            }
        )
    )
