from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from hermes_skilleval import (  # noqa: E402
    router_v2_blind_v2_output_schema_preflight as preflight,
)


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Run only the synthetic Router V2 blind-v2 successor preflight."
    )


def main(argv: Sequence[str] | None = None) -> int:
    _parser().parse_args(argv)
    receipt = preflight.run_successor_preflight()
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["preflight_state"] == "PREFLIGHT_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
