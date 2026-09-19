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
    p = commands.add_parser(
        "collect", help="same-state functional tails and registered native chains"
    )
    for key in (
        "protocol",
        "objective",
        "tasks",
        "output",
        "skills",
        "payloads",
        "encoder",
        "session-home",
        "pilot-root",
    ):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--native-only", action="store_true")
    p = commands.add_parser(
        "train", help="fit independently initialized pure functional models"
    )
    for key in (
        "records",
        "protocol",
        "objective",
        "learning",
        "output",
        "payloads",
        "encoder",
    ):
        p.add_argument("--" + key, type=Path, required=True)
    p = commands.add_parser(
        "reload", help="independent process functional model reload probe"
    )
    p.add_argument("--models", type=Path, required=True)
    p = commands.add_parser(
        "evaluate", help="frozen functional matrix or prospective mechanism panels"
    )
    for key in (
        "protocol",
        "objective",
        "tasks",
        "output",
        "skills",
        "payloads",
        "encoder",
        "models",
    ):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--phase", choices=("matrix", "panels", "delays"), required=True)
    args = parser.parse_args(argv)
    from .functional_outcomes import decompose

    if args.command == "decompose":
        result = decompose(args.records, args.objective, args.output)
    elif args.command == "evaluate":
        from .functional_evaluate import matrix, panels

        call = matrix if args.phase == "matrix" else panels
        kwargs = {} if args.phase == "matrix" else {"delayed": args.phase == "delays"}
        result = call(
            args.protocol,
            args.objective,
            args.tasks,
            args.output,
            args.skills,
            args.payloads,
            args.encoder,
            args.models,
            **kwargs,
        )
    elif args.command == "train":
        from .functional_learning import train

        result = train(
            args.records,
            args.protocol,
            args.objective,
            args.learning,
            args.output,
            args.payloads,
            args.encoder,
        )
    elif args.command == "reload":
        from .functional_learning import reload_probe

        result = reload_probe(args.models)
    elif args.command == "collect":
        from .functional_collection import collect

        result = collect(
            args.protocol,
            args.objective,
            args.tasks,
            args.output,
            args.skills,
            args.payloads,
            args.encoder,
            args.session_home,
            args.pilot_root,
            native_only=args.native_only,
        )
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
