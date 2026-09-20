"""Read saved execution usage; never invoke models, training or verifiers."""

import argparse
from pathlib import Path

from hermes_skilleval.intervention.functional_costs import from_files
from hermes_skilleval.intervention.session import dump


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--records", action="append", required=True, metavar="CATEGORY=PATH"
    )
    parser.add_argument("--training", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = []
    for value in args.records:
        category, separator, path = value.partition("=")
        if not separator or category not in (
            "collection",
            "online_evaluation",
            "mechanism_probes",
        ):
            parser.error(
                "records must use collection, online_evaluation or mechanism_probes"
            )
        sources.append((category, Path(path)))
    dump(args.output, from_files(sources, args.training))


if __name__ == "__main__":
    main()
