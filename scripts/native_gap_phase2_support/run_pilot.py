"""Sequential fixed denominator; no acceptance feedback or replacement attempts."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from native_gap_phase2 import run_descriptor  # noqa: E402

P = Path("/tmp/hermes-native-gap-phase2-private")
C = ROOT / "configs/native-gap-phase2-same-library-v1"


def main():
    if sys.version_info < (3, 11):
        raise RuntimeError("Python >=3.11 required before any attempts")
    freeze = json.loads((C / "freeze.json").read_text())
    assert freeze["formal_runs_authorized_by_checks"] is True
    from native_gap_phase2_support.integrity import verify_private_assets

    verify_private_assets(freeze)
    for entry in freeze["tracked_inputs"]:
        assert (
            hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest()
            == entry["sha256"]
        ), entry["path"]
    plan = json.loads((C / "plan.json").read_text())
    for item in plan["order"]:
        root = P / "runs" / item["id"]
        if root.exists():
            if not (root / "result.json").exists():
                raise RuntimeError(
                    "Nonterminal attempt must be recovered, not restarted: "
                    + item["id"]
                )
            previous = json.loads((root / "result.json").read_text())
            if not previous.get("parent_cleanup", {}).get(
                "no_running_tool_confirmation"
            ):
                raise RuntimeError(
                    "Preserved attempt cleanup unconfirmed: " + item["id"]
                )
            print(item["id"], "PRESERVED_EXISTING_ATTEMPT", flush=True)
            continue
        descriptor = P / "descriptors" / f"{item['id']}.json"
        # This is identity metadata only. Task/index input reads happen inside the clock.
        result = run_descriptor(str(descriptor), root, 900, item["descriptor_sha256"])
        print(
            item["id"],
            result["parent_status"],
            round(result["elapsed_seconds"], 3),
            flush=True,
        )
        if result.get("parent_cleanup_error"):
            raise RuntimeError("Stop queue until owned resource cleanup confirmed")
    (P / "all-repair-calls-terminal.json").write_text(
        json.dumps(
            {"ids": [i["id"] for i in plan["order"]], "count": len(plan["order"])},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
