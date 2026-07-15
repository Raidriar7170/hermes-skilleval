from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
from pathlib import Path  # noqa: E402

from hermes_skilleval.router_v2_pilot_run_pack import (  # noqa: E402
    build_run_pack,
)
from hermes_skilleval.router_v2_pilot_runtime import canonical_json_line  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the frozen Router V2 A/B/C pilot run pack."
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--execution-root", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_run_pack(args.repository_root, execution_root=args.execution_root)
    print(canonical_json_line(manifest), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
