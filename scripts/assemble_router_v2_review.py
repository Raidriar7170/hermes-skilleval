from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from hermes_skilleval.router_v2_review_assembler import (
    assemble_adjudication_review,
    assemble_pass_review,
)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--decisions-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assemble bounded Router V2 model-only review rows."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    pass_parser = subparsers.add_parser("assemble-pass")
    _add_common(pass_parser)
    pass_parser.add_argument(
        "--pass-id", choices=("MODEL_PASS_1", "MODEL_PASS_2"), required=True
    )
    pass_parser.add_argument("--pass-run-id", required=True)

    adjudication_parser = subparsers.add_parser("assemble-adjudication")
    _add_common(adjudication_parser)
    adjudication_parser.add_argument("--pass-1-file", type=Path, required=True)
    adjudication_parser.add_argument("--pass-2-file", type=Path, required=True)

    args = parser.parse_args()
    result: dict[str, Any]
    if args.command == "assemble-pass":
        result = assemble_pass_review(
            repository_root=args.repository_root,
            pass_id=args.pass_id,
            pass_run_id=args.pass_run_id,
            decisions_path=args.decisions_file,
            output_path=args.output_file,
        )
    else:
        result = assemble_adjudication_review(
            repository_root=args.repository_root,
            pass_1_path=args.pass_1_file,
            pass_2_path=args.pass_2_file,
            decisions_path=args.decisions_file,
            output_path=args.output_file,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
