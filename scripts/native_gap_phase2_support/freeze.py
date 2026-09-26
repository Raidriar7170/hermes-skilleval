"""Final pre-run gate: real preflights, qualified tasks and fresh asset identities."""

import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
P = Path("/tmp/hermes-native-gap-phase2-private")
OLD = Path("/tmp/hermes-native-gap-phase1-private")
C = ROOT / "configs/native-gap-phase2-same-library-v1"
A = ROOT / "artifacts/native-gap-phase2-same-library-v1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not (C / "freeze.json").exists(), "Freeze is immutable once written"
    plan = json.loads((C / "plan.json").read_text())
    assert plan["planned_runs"] == 16 and len(plan["order"]) == 16
    assert not (P / "runs").exists(), "No formal attempts before freeze"
    preflights = []
    for ident in ["preflight-1", "preflight-2"]:
        r = json.loads((P / ident / "result.json").read_text())
        w = r["worker"]
        assert w["terminal"] == "completed" and r["budget_valid"], ident
        assert w["discovery_identity_verified"] and w["input_bindings_verified"], ident
        assert r["parent_cleanup"]["no_running_tool_confirmation"]
        if ident == "preflight-2":
            assert w["navigation_fallback"] is False
        preflights.append(
            {
                "id": ident,
                "result_sha256": digest(P / ident / "result.json"),
                "elapsed_seconds": r["elapsed_seconds"],
            }
        )
    review = json.loads((A / "preflight/review-progress.json").read_text())
    assert all(str(i) in review["batches"] for i in range(1, 5))
    assert review.get("all_factual_corrections_applied") is True
    for item in plan["order"]:
        assert (
            digest(P / "descriptors" / f"{item['id']}.json")
            == item["descriptor_sha256"]
        )
    plan["status"] = "FROZEN"
    (C / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    library = json.loads((C / "library-manifest.json").read_text())
    library["status"] = "FROZEN"
    (C / "library-manifest.json").write_text(json.dumps(library, indent=2) + "\n")
    started = time.monotonic()
    inputs = []
    paths = (
        list(C.rglob("*"))
        + list((ROOT / "scripts/native_gap_phase2_support").glob("*.py"))
        + [
            ROOT / "scripts/native_gap_phase2.py",
            ROOT / "scripts/native_gap_phase1.py",
            ROOT / "src/hermes_skilleval/intervention/value.py",
            ROOT / "src/hermes_skilleval/intervention/repair_composer.py",
            ROOT / "src/hermes_skilleval/_maintenance/docker-seccomp-userns.json",
        ]
    )
    for f in sorted(set(paths)):
        if f.is_file():
            inputs.append({"path": str(f.relative_to(ROOT)), "sha256": digest(f)})
    private = []

    def asset(label, base):
        files = sorted(base.rglob("*")) if base.is_dir() else [base]
        for f in files:
            if f.is_file():
                private.append(
                    {
                        "asset": label,
                        "path": str(f.relative_to(base))
                        if base.is_dir()
                        else base.name,
                        "bytes": f.stat().st_size,
                        "sha256": digest(f),
                    }
                )

    encoder = Path(
        json.loads((P / "preflight-descriptor-2.json").read_text())["encoder_path"]
    )
    asset("encoder", encoder)
    asset("linux-client", OLD / "codex-linux-arm64")
    asset("metadata-index", P / "metadata-index.json")
    asset("system-skills", P / "permissions-v3/state/skills")
    asset("author-parser", OLD / "swebench-fork/swebench/harness/log_parsers/python.py")
    for iid in sorted({r["instance_id"] for r in plan["order"]}):
        asset("trusted-task-" + iid, P / "trusted-targets" / f"{iid}.json")
    frozen = {
        "study": plan["study"],
        "formal_runs_authorized_by_checks": True,
        "frozen_unix": time.time(),
        "preflights": preflights,
        "tracked_inputs": inputs,
        "private_assets": private,
        "hash_seconds": time.monotonic() - started,
        "hash_algorithm": "SHA256_FRESH",
        "parent_commit": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"]
        )
        .decode()
        .strip(),
        "execution_version": "Frozen source hashes; record actual execution commit before launching matrix",
        "review": "Independent model context, not human gold; no functional gain claim",
    }
    (C / "freeze.json").write_text(json.dumps(frozen, indent=2) + "\n")
    print(
        "FROZEN",
        len(inputs),
        "tracked inputs",
        len(private),
        "private asset identities",
    )


if __name__ == "__main__":
    main()
