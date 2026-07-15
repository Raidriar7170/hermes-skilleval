#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hermes_skilleval.router_v2_pilot_evaluation_runner import (
    run_replay_evaluation_once,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the one-shot Router V2 pilot-002 evaluation replay"
    )
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--training-execution-root", required=True, type=Path)
    parser.add_argument("--evaluation-output-root", required=True, type=Path)
    parser.add_argument("--base-model-path", required=True, type=Path)
    args = parser.parse_args()
    summary = run_replay_evaluation_once(
        args.repository_root,
        args.training_execution_root,
        args.evaluation_output_root,
        args.base_model_path,
    )
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
