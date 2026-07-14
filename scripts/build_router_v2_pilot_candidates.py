from __future__ import annotations

import argparse
import json
from pathlib import Path

from hermes_skilleval.router_v2_pilot_candidates import build_candidate_bundle


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the frozen Router V2 pilot candidate bundle."
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = build_candidate_bundle(
        repository_root=args.repository_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
