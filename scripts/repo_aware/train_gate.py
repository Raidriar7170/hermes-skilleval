"""Fit/calibrate gate and seal its bytes before the controller starts final runs."""

import argparse
import hashlib
import json
from pathlib import Path
import time

from hermes_skilleval.repo_routing.gate import main

if __name__ == "__main__":
    main()
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fit", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    args, _ = parser.parse_known_args()
    model = json.loads(args.output.read_text())
    seal = {
        "schema": "repo-aware-gate-freeze-v1",
        "r_version": model["r_version"],
        "gate_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "fit_sha256": hashlib.sha256(args.fit.read_bytes()).hexdigest(),
        "calibration_sha256": hashlib.sha256(args.calibration.read_bytes()).hexdigest(),
        "frozen_at": time.time(),
    }
    with args.output.with_suffix(".freeze.json").open("x") as stream:
        json.dump(seal, stream, indent=2)
