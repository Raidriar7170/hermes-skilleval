"""Offline verification of public run records and task-clustered summaries."""

from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate_costs(rows):
    """Sum observed values only; subsets and missing usage remain explicit."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["split"], row["repository"], row["arm"])].append(row)
    result = []
    for (split, repository, arm), items in sorted(grouped.items()):
        measures = {}
        for field in [
            "input_tokens",
            "cached_input_tokens",
            "cache_write_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
            "uncached_input_tokens",
            "execution_seconds",
            "pipeline_wall_seconds",
            "recommend_wall_seconds",
        ]:
            values = []
            for row in items:
                usage = row.get("usage") or {}
                if field == "uncached_input_tokens":
                    value = (
                        usage.get("input_tokens") - usage.get("cached_input_tokens")
                        if all(
                            isinstance(usage.get(k), (int, float))
                            for k in ["input_tokens", "cached_input_tokens"]
                        )
                        else None
                    )
                elif field.endswith("_tokens"):
                    value = usage.get(field)
                elif field == "recommend_wall_seconds":
                    value = row.get(field)
                else:
                    value = (row.get("timing") or {}).get(field)
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                    and value >= 0
                ):
                    values.append(value)
            measures[field] = {
                "sum_known": sum(values) if values else None,
                "known_attempts": len(values),
                "total_attempts": len(items),
            }
        result.append(
            {
                "split": split,
                "repository": repository,
                "arm": arm,
                "measures": measures,
                "cost_usd": None,
            }
        )
    return result


def recompute(index, output):
    index = Path(index).resolve()
    output = Path(output)
    if output.exists():
        raise ValueError("preserve existing records/output")
    manifest = json.loads(index.read_text())
    rows = []
    seen = set()
    for entry in manifest["runs"]:
        key = tuple(entry[k] for k in ["task_id", "arm", "attempt"])
        if key in seen:
            raise ValueError("duplicate task/arm/attempt")
        seen.add(key)
        row = {
            k: entry[k]
            for k in [
                "task_id",
                "repository",
                "family_id",
                "split",
                "arm",
                "attempt",
                "execution_status",
            ]
        }
        row.update(
            resolved=None,
            verifier_valid=False,
            usage=entry.get("usage"),
            timed_out=entry.get("timed_out"),
            exit_code=entry.get("exit_code"),
            timeout_seconds=entry.get("timeout_seconds"),
            timing=entry.get("timing"),
            cost_usd=entry.get("cost_usd"),
            policy_rejected=entry.get("policy_rejected", False),
        )
        try:
            files = {}
            for label, item in entry["files"].items():
                path = (index.parent / item["path"]).resolve()
                if not path.is_relative_to(index.parent):
                    raise ValueError("evidence path escapes index directory")
                if sha(path) != item["sha256"]:
                    raise ValueError("evidence missing or changed: " + label)
                files[label] = path
            if "route" in files:
                route = json.loads(files["route"].read_text())
                row["recommend_wall_seconds"] = route.get("recommend_wall_seconds")
                row["route_timing"] = route.get("timing")
            if "patch" not in files:
                raise ValueError("patch missing")
            if "binding" not in files:
                raise ValueError("verification binding missing")
            binding = json.loads(files["binding"].read_text())
            if any(
                binding.get(k) != entry.get(k)
                for k in ["task_id", "arm", "attempt", "run_id", "base_commit"]
            ):
                raise ValueError("verification task/arm binding mismatch")
            if binding.get("patch_sha256") != entry["files"]["patch"]["sha256"]:
                raise ValueError("verification patch binding mismatch")
            if binding.get("verifier_valid") is not True:
                raise ValueError("original verifier invalid")
            for kind in ["target", "regression"]:
                if binding["test_files"].get(kind) != entry["files"][kind]["sha256"]:
                    raise ValueError("verification test binding mismatch")
            outcomes = {}
            for kind in ["target", "regression"]:
                junit = ET.parse(files[kind])
                cases = list(junit.iter("testcase"))
                ids = [c.attrib["classname"] + "::" + c.attrib["name"] for c in cases]
                if not cases or sorted(ids) != sorted(entry["expected_test_ids"][kind]):
                    raise ValueError("test collection mismatch: " + kind)
                if any(
                    c.find("skipped") is not None or c.find("error") is not None
                    for c in cases
                ):
                    raise ValueError("skip/error in mandatory tests: " + kind)
                outcomes[kind] = all(c.find("failure") is None for c in cases)
            resolved = (
                all(outcomes.values()) if row["execution_status"] == "STARTED" else None
            )
            if resolved is not binding.get("resolved"):
                raise ValueError("original/recomputed conclusion mismatch")
            row.update(verifier_valid=True, resolved=resolved, **outcomes)
        except (OSError, ValueError, KeyError, ET.ParseError) as exc:
            row.update(error=str(exc), resolved=None, verifier_valid=False)
        rows.append(row)
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["split"], row["repository"], row["arm"])].append(row)
    summary = []
    for (split, repo, arm), items in sorted(grouped.items()):
        summary.append(
            {
                "split": split,
                "repository": repo,
                "arm": arm,
                "attempts": len(items),
                "policy_rejected": sum(r.get("policy_rejected") is True for r in items),
                "timeouts": sum(r.get("timed_out") is True for r in items),
                "tasks": len({r["task_id"] for r in items}),
                "resolved": sum(r["resolved"] is True for r in items),
                "failed": sum(r["resolved"] is False for r in items),
                "unknown": sum(r["resolved"] is None for r in items),
            }
        )
    output.mkdir(parents=True)
    result = {
        "schema": "maintenance-records-v1",
        "records_only": True,
        "rows": rows,
        "summary": summary,
        "cost_summary": aggregate_costs(rows),
        "limitations": [
            "Selected target and related regressions only.",
            "Repeated attempts are not independent tasks.",
            "All ties do not establish equivalence.",
        ],
    }
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
