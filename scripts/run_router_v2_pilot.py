from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
from pathlib import Path  # noqa: E402

from hermes_skilleval.router_v2_pilot_runtime import (  # noqa: E402
    build_skill_unique_plan,
    canonical_json_line,
    execute_training_run,
    load_and_seal_internal_package,
    load_json_object_file,
    preflight,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preflight or prepare the isolated Router V2 pilot runtime."
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--base-model-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    try:
        config = load_json_object_file(args.config, label="config")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    result = preflight(
        repository_root=args.repository_root,
        config=config,
        base_model_path=args.base_model_path,
        output_root=args.output_root,
    )
    if args.preflight_only:
        print(canonical_json_line(result), end="")
        return 0

    handoff = load_and_seal_internal_package(args.repository_root)
    plan = build_skill_unique_plan(handoff, seed=config["seed"], epochs=3)
    summary = execute_training_run(
        config,
        handoff,
        plan,
        repository_root=args.repository_root,
        preflight_result=result,
        base_model_path=args.base_model_path,
        output_root=args.output_root,
    )
    print(canonical_json_line(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
