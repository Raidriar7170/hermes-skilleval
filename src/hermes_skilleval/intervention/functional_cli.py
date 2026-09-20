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
        "roster",
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
    p.add_argument(
        "--phase", choices=("matrix", "panels", "delays", "release"), required=True
    )
    p = commands.add_parser(
        "replay", help="zero-model functional records recomputation"
    )
    for key in ("records", "objective"):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--public-root", type=Path)
    p = commands.add_parser(
        "export", help="compact original patches and verifier evidence"
    )
    for key in ("records", "objective", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument(
        "--group",
        choices=("pilot", "native", "collection", "matrix", "panels", "delays"),
        required=True,
    )
    p = commands.add_parser(
        "summarize", help="verified functional-first status and mechanism tables"
    )
    for key in (
        "protocol",
        "objective",
        "collection",
        "roster",
        "evaluation",
        "models",
        "output",
    ):
        p.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args(argv)
    from .functional_outcomes import decompose

    if args.command == "decompose":
        result = decompose(args.records, args.objective, args.output)
    elif args.command == "summarize":
        from .functional_report import summarize

        result = summarize(
            args.protocol,
            args.objective,
            args.collection,
            args.evaluation,
            args.models,
            args.output,
            args.roster,
        )
    elif args.command == "replay":
        from .functional_export import replay

        result = replay(args.records, args.objective, public_root=args.public_root)
    elif args.command == "export":
        from .functional_export import export

        result = export(args.records, args.objective, args.output, group=args.group)
    elif args.command == "evaluate":
        from .functional_evaluate import matrix, panels, release

        call = {"matrix": matrix, "release": release}.get(args.phase, panels)
        kwargs = {"delayed": args.phase == "delays"} if call is panels else {}
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
            args.roster,
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
