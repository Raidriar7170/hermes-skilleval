"""Export a private replay protocol through a narrow public evidence allowlist."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET


PATH = re.compile(r"(?:/Users/|/home/|/private/var/|[A-Za-z]:\\Users\\)[^\s\"'<>]+")
SECRET = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|eyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{8,}"
    r"|Bearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?:api_key|access_token|refresh_token|id_token|client_secret|password)[\"']?\s*[=:]\s*['\"]?[^\s'\"]{8,})",
    re.I,
)
ID = re.compile(r"[A-Za-z0-9_.+-]+\Z")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeError):
        return {"_parse_error": True}
    return value if isinstance(value, dict) else {"_parse_error": True}


def clean(value):
    return SECRET.sub("[REDACTED_SECRET]", PATH.sub("[REDACTED_PATH]", str(value)))


def number(value):
    return (
        value
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
        else None
    )


def identifier(value):
    return value if isinstance(value, str) and ID.fullmatch(value) else None


def digest(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value)
        else None
    )


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def export_junit(source, target):
    """Keep outcomes and IDs; drop stack bodies, properties, streams and hostnames."""
    root = ET.Element("testsuite")
    for case in ET.parse(source).iter("testcase"):
        new = ET.SubElement(
            root,
            "testcase",
            {k: clean(case.attrib.get(k, "")) for k in ("classname", "name")},
        )
        for tag in ("failure", "error", "skipped"):
            node = case.find(tag)
            if node is not None:
                ET.SubElement(new, tag, {"type": clean(node.attrib.get("type", tag))})
    target.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)


def export(protocol, output):
    config = read(protocol)
    output.mkdir(parents=True, exist_ok=False)
    private = Path(config["output"])
    protocol_sha = sha(protocol)
    events = []
    ledger = private / "attempts.jsonl"
    if ledger.exists():
        for line_number, line in enumerate(ledger.read_text().splitlines(), 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                events.append({"event": "MALFORMED_LEDGER_LINE", "line": line_number})
                continue
            events.append(
                {
                    "event": value.get("event")
                    if value.get("event") in ("launch", "exit")
                    else "UNKNOWN_EVENT",
                    "run_id": identifier(value.get("run_id")),
                    "time": number(value.get("time")),
                    "exit_code": value.get("exit_code")
                    if isinstance(value.get("exit_code"), int)
                    else None,
                    "protocol_sha256": digest(value.get("protocol_sha256")),
                }
            )
    result = {
        "schema": "repo-aware-public-execution-v1",
        "protocol_sha256": protocol_sha,
        "routing_config_sha256": sha(Path(config["routing_config"]))
        if config.get("routing_config") and Path(config["routing_config"]).is_file()
        else None,
        "registry_sha256": sha(Path(config["registry"]))
        if config.get("registry") and Path(config["registry"]).is_file()
        else None,
        "ledger_sha256": sha(ledger) if ledger.exists() else None,
        "protocol_lock_matches": (private / "protocol-sha256.txt").is_file()
        and (private / "protocol-sha256.txt").read_text().strip() == protocol_sha,
        "dollars": None,
        "cells": [],
        "events": events,
        "privacy": "Allowlisted metadata; raw patches withheld on sensitive-pattern detection; JUnit stack bodies omitted.",
    }
    seen = set()
    for cell in config["cells"]:
        run_id, task_id = (
            identifier(cell.get("run_id")),
            identifier(cell.get("task_id")),
        )
        if (
            not run_id
            or not task_id
            or run_id in seen
            or run_id in (".", "..")
            or task_id in (".", "..")
        ):
            raise ValueError("Unsafe or duplicate planned run identity")
        seen.add(run_id)
        directory = private / run_id
        run_path = directory / "run.json"
        run = read(run_path)
        executor_path = directory / "executor.json"
        executor = read(executor_path)
        routing_path = directory / "routing.json"
        if not routing_path.exists():
            routing_path = private / (run_id + "-decision.json")
        routing = read(routing_path)
        qpath = Path(config["qualification"]) / task_id / "qualified.json"
        qualification = read(qpath)
        metadata = run or executor
        policy = identifier(cell.get("policy"))
        out = {
            "run_id": run_id,
            "task_id": task_id,
            "family_id": identifier(
                cell.get("family_id") or qualification.get("family_id") or task_id
            ),
            "family_source": "protocol"
            if cell.get("family_id")
            else "qualification"
            if qualification.get("family_id")
            else "task_id_fallback",
            "policy": policy,
            "repeat": number(cell.get("repeat")),
            "execution_status": identifier(metadata.get("execution_status"))
            or "NOT_OBSERVED",
            "exit_code": metadata.get("exit_code")
            if isinstance(metadata.get("exit_code"), int)
            else None,
            "timed_out": metadata.get("timed_out")
            if isinstance(metadata.get("timed_out"), bool)
            else None,
            "error_present": bool(metadata.get("error")),
            "parse_errors": [
                name
                for name, value in [
                    ("run", run),
                    ("executor", executor),
                    ("routing", routing),
                    ("qualification", qualification),
                ]
                if value.get("_parse_error")
            ],
            "run_sha256": sha(run_path) if run_path.exists() else None,
            "executor_sha256": sha(executor_path) if executor_path.exists() else None,
            "routing_sha256": sha(routing_path) if routing_path.exists() else None,
            "qualification_sha256": sha(qpath) if qpath.exists() else None,
            "base_commit": identifier(metadata.get("base_commit")),
            "registry_id": identifier(metadata.get("registry_id")),
            "r_version": digest(routing.get("r_version")),
            "routing_policy": identifier(routing.get("requested_policy")),
            "routing_registry_id": identifier(routing.get("registry_id")),
            "source_sha256": {
                key: digest(value)
                for key, value in metadata.get("source_sha256", {}).items()
                if isinstance(key, str)
                and not Path(key).is_absolute()
                and ".." not in Path(key).parts
                and re.fullmatch(r"[A-Za-z0-9_./-]+", key)
                and digest(value)
            },
            "action": identifier(routing.get("action") or metadata.get("arm")),
            "adapter_sha256": digest(routing.get("adapter_sha256")),
            "context_digest": digest(routing.get("context_digest")),
            "selected_ids": [
                identifier(x) for x in metadata.get("selected_ids", []) if identifier(x)
            ],
            "model": identifier(metadata.get("model")),
            "effort": identifier(metadata.get("effort")),
            "timing": {
                k: number(metadata.get(k))
                for k in (
                    "pipeline_wall_seconds",
                    "execution_seconds",
                    "package_prepare_seconds",
                    "capture_seconds",
                    "finalize_seconds",
                )
            },
            "calls": {
                k: number(routing.get("calls", {}).get(k))
                for k in ("heavy_constructors", "encoder_queries", "reranker_forwards")
            },
            "usage": None,
            "patch": None,
            "checks": {},
            "binding": {},
        }
        usage = metadata.get("usage")
        if isinstance(usage, dict):
            out["usage"] = {
                key: number(usage.get(key))
                for key in (
                    "input_tokens",
                    "cached_input_tokens",
                    "output_tokens",
                    "reasoning_output_tokens",
                )
            }
        launch = [
            e for e in events if e.get("run_id") == run_id and e["event"] == "launch"
        ]
        out["binding"] = {
            "single_launch": len(launch) == 1,
            "launch_protocol_matches": len(launch) == 1
            and launch[0]["protocol_sha256"] == protocol_sha,
            "task_and_base_match": metadata.get("task_id")
            == task_id
            == qualification.get("task_id")
            and metadata.get("base_commit") is not None
            and metadata.get("base_commit") == qualification.get("base_commit"),
            "qualification_matches": bool(qualification.get("qualified"))
            and metadata.get("qualification_sha256") == out["qualification_sha256"]
            and out["qualification_sha256"] is not None,
            "registry_matches": bool(out["registry_id"])
            and (
                policy == "native-minus"
                or routing.get("registry_id") == out["registry_id"]
            ),
            "policy_matches": policy == "native-minus"
            or routing.get("requested_policy") == policy,
            "r_version_present": policy == "native-minus" or bool(out["r_version"]),
            "patch_applies": run.get("patch_applies") is True,
            "finalize_no_error": bool(run) and not bool(run.get("error")),
        }
        patch = directory / "saved-capture/candidate.patch"
        if patch.is_file():
            raw = patch.read_bytes()
            patch_sha = sha(patch)
            sensitive = bool(
                PATH.search(raw.decode("utf-8", errors="replace"))
                or SECRET.search(raw.decode("utf-8", errors="replace"))
            )
            relative = Path(run_id) / "candidate.patch"
            if not sensitive:
                (output / run_id).mkdir(parents=True, exist_ok=True)
                (output / relative).write_bytes(raw)
            out["patch"] = {
                "sha256": patch_sha,
                "path": relative.as_posix() if not sensitive else None,
                "status": "WITHHELD_PRIVACY" if sensitive else "EXPORTED",
                "run_binding_matches": run.get("patch_sha256") == patch_sha,
            }
        for kind in ("target", "regression"):
            check_dir = directory / "verification" / kind
            check_path, junit = check_dir / "result.json", check_dir / "junit.xml"
            check = read(check_path)
            if not check_path.is_file() or not junit.is_file():
                out["checks"][kind] = {"status": "MISSING"}
                continue
            relative = Path(run_id) / (kind + ".xml")
            try:
                export_junit(junit, output / relative)
            except (ET.ParseError, UnicodeError):
                out["checks"][kind] = {
                    "status": "INVALID_JUNIT",
                    "raw_junit_sha256": sha(junit),
                }
                continue
            expected = qualification.get("test_ids", {}).get(kind, [])
            qimage = qualification.get("qualification_binding", {}).get("image_id")
            recorded = run.get("check_evidence", {}).get(kind, {})
            out["checks"][kind] = {
                "status": "EXPORTED",
                "junit": relative.as_posix(),
                "junit_sha256": sha(output / relative),
                "raw_junit_sha256": sha(junit),
                "result_sha256": sha(check_path),
                "expected_ids": sorted(clean(x) for x in expected),
                "image_id": check.get("image_id")
                if re.fullmatch(r"sha256:[a-f0-9]{64}", str(check.get("image_id")))
                else None,
                "returncode": check.get("returncode"),
                "build_ok": check.get("build_returncode") == 0,
                "canary_ok": check.get("cli_returncode") == 0,
                "collection_ok": check.get("collection_returncode") == 0,
                "image_matches": bool(qimage) and check.get("image_id") == qimage,
                "candidate_import_isolated": check.get("identity", {}).get(
                    "candidate_root_on_sys_path"
                )
                is False,
                "run_hashes_match": recorded.get("result.json") == sha(check_path)
                and recorded.get("junit.xml") == sha(junit),
            }
        result["cells"].append(out)
    write(output / "index.json", result)
    return {
        "planned_cells": len(result["cells"]),
        "events": len(events),
        "index_sha256": sha(output / "index.json"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.protocol, args.output), indent=2))
