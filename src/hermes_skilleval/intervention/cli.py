"""Explicit research CLI; no change to existing routing defaults."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hermes-intervention")
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ["collect", "evaluate"]:
        p = subs.add_parser(name)
        for key in ["protocol", "tasks", "output", "skills", "payloads", "encoder"]:
            p.add_argument("--" + key, type=Path, required=True)
        if name == "evaluate":
            p.add_argument("--models", type=Path, required=True)
    p = subs.add_parser(
        "prepare", help="verify prepared frozen tasks and resources without Agent calls"
    )
    for key in ["protocol", "tasks", "skills", "payloads", "encoder"]:
        p.add_argument("--" + key, type=Path, required=True)
    p = subs.add_parser("train")
    for key in ["records", "output", "payloads", "encoder"]:
        p.add_argument("--" + key, type=Path, required=True)
    p = subs.add_parser("reload")
    p.add_argument("--models", type=Path, required=True)
    for name in ["replay", "summarize"]:
        p = subs.add_parser(name)
        p.add_argument("--records", type=Path, required=True)
    a = parser.parse_args(argv)
    if a.command == "prepare":
        from .study import read, verify_freeze

        protocol = read(a.protocol)
        verify_freeze(protocol, a.tasks, a.payloads, a.skills, a.encoder)
        result = {
            "status": "FROZEN_ASSET_VERIFIED",
            "tasks": len(protocol["tasks"]),
            "split_counts": protocol["split_counts"],
        }
    elif a.command == "collect":
        from .study import collect

        result = collect(a.protocol, a.tasks, a.output, a.skills, a.payloads, a.encoder)
    elif a.command == "evaluate":
        from .evaluate import evaluate

        result = evaluate(
            a.protocol, a.tasks, a.output, a.skills, a.payloads, a.encoder, a.models
        )
    elif a.command == "train":
        from .learning import train

        result = train(a.records, a.output, a.payloads, a.encoder)
    elif a.command == "reload":
        from .learning import reload_probe

        result = reload_probe(a.models)
    else:
        from .evaluate import replay

        result = replay(a.records)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
