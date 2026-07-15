from __future__ import annotations

import argparse
import json
from pathlib import Path

from hermes_skilleval.router_v2_internal_package import build_internal_package


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the frozen Router V2 internal training package."
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    manifest = build_internal_package(args.repository_root)
    print(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
