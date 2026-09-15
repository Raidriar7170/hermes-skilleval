"""Fit/calibrate gate and seal its bytes before the controller starts final runs."""

import argparse
import hashlib
import json
from pathlib import Path
import time

from gate_recipe import train

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fit", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    args = parser.parse_args()

    def read(path):
        return [
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ]

    model = train(read(args.fit), read(args.calibration), args.r_version)
    with args.output.open("x") as stream:
        json.dump(model, stream, indent=2)
    seal = {
        "schema": "repo-aware-gate-freeze-v1",
        "r_version": model["r_version"],
        "gate_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "fit_sha256": hashlib.sha256(args.fit.read_bytes()).hexdigest(),
        "calibration_sha256": hashlib.sha256(args.calibration.read_bytes()).hexdigest(),
        "recipe_sha256": {
            name: hashlib.sha256(
                Path(__file__).with_name(name).read_bytes()
            ).hexdigest()
            for name in ("train_gate.py", "gate_recipe.py")
        },
        "frozen_at": time.time(),
    }
    with args.output.with_suffix(".freeze.json").open("x") as stream:
        json.dump(seal, stream, indent=2)
