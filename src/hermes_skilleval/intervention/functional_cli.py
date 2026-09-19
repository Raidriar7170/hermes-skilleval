"""Explicit functional-v2 commands, isolated from legacy research defaults."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hermes-intervention functional-v2")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser(
        "decompose", help="records-only old train/dev functional diagnosis"
    )
    for key in ("records", "objective", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    p = commands.add_parser("pilot", help="fixed real native training pilot")
    for key in (
        "protocol",
        "objective",
        "tasks",
        "output",
        "skills",
        "payloads",
        "encoder",
    ):
        p.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args(argv)
    from .functional_outcomes import decompose

    if args.command == "decompose":
        result = decompose(args.records, args.objective, args.output)
    else:
        from .functional_pilot import pilot

        result = pilot(
            args.protocol,
            args.objective,
            args.tasks,
            args.output,
            args.skills,
            args.payloads,
            args.encoder,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
