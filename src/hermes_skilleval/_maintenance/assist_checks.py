"""Frozen, paired checks with conservative requirement coverage."""

from pathlib import Path
import re
from hermes_skilleval.repository_maintenance import manifest, copy_manifest
from hermes_skilleval._maintenance.check import check


def parse_checks(path):
    import json

    config = json.loads(path.read_text())
    if (
        set(config) != {"version", "requirements", "checks"}
        or config["version"] != "assist-checks-v1"
    ):
        raise ValueError("unsupported checks configuration")
    requirements = {}
    for item in config["requirements"]:
        if (
            set(item) != {"id", "description"}
            or not re.fullmatch(r"[A-Za-z0-9_-]+", item["id"])
            or not item["description"]
            or item["id"] in requirements
        ):
            raise ValueError("invalid/duplicate requirement")
        requirements[item["id"]] = item["description"]
    ids = set()
    for item in config["checks"]:
        if set(item) != {
            "id",
            "kind",
            "requirements",
            "trusted_dir",
            "argv",
            "cwd",
            "env",
            "timeout",
        }:
            raise ValueError("unsupported/missing check fields")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", item["id"]) or item["id"] in ids:
            raise ValueError("invalid/duplicate check ID")
        ids.add(item["id"])
        if (
            item["kind"] not in ("existing", "requirement")
            or not set(item["requirements"]) <= requirements.keys()
        ):
            raise ValueError("invalid check source or requirement mapping")
        if item["kind"] == "existing" and item["requirements"]:
            raise ValueError("existing checks cannot certify new requirements")
        argv = item["argv"]
        if (
            not isinstance(argv, list)
            or len(argv) != 6
            or argv[:3] != ["python", "-m", "pytest"]
            or argv[4] != "-k"
            or not isinstance(argv[5], str)
            or not argv[5].strip()
            or not re.fullmatch(r"test_[A-Za-z0-9_]+\.py", argv[3])
        ):
            raise ValueError(
                "supported argv: [python, -m, pytest, test_NAME.py, -k, SELECTOR]"
            )
        if item["cwd"] != "/tmp" or item["env"] != {}:
            raise ValueError(
                "trusted checks support only cwd=/tmp and env={}; overrides rejected"
            )
        if type(item["timeout"]) is not int or not 1 <= item["timeout"] <= 1800:
            raise ValueError("check timeout must be 1..1800 seconds per isolated step")
        root = Path(item["trusted_dir"])
        root = root if root.is_absolute() else path.resolve().parent / root
        root = root.resolve()
        if not (root / argv[3]).is_file() or not (root / "pytest.ini").is_file():
            raise ValueError(
                "trusted directory requires declared test file and pytest.ini"
            )
        from hermes_skilleval._maintenance.assist_snapshot import SECRET

        files = manifest(root, strict=True)
        if any(d.startswith("symlink:") for d in files.values()):
            raise ValueError("trusted checks cannot contain symlinks")
        if any(SECRET.search((root / name).read_bytes()) for name in files):
            raise ValueError("sensitive content in trusted checks")
        item["trusted_dir"] = str(root)
        item["manifest"] = files
    return config


def freeze_checks(config, destination):
    import copy

    result = copy.deepcopy(config)
    for item in result["checks"]:
        target = destination / item["id"]
        target.mkdir(parents=True)
        copy_manifest(Path(item["trusted_dir"]), target, item["manifest"])
        item["trusted_dir"] = str(target)
    return result


def run_checks(config, candidate, output, profile):
    results = {}
    for item in config["checks"]:
        root = Path(item["trusted_dir"])
        if manifest(root, strict=True) != item["manifest"]:
            raise ValueError("frozen controller checks changed")
        results[item["id"]] = check(
            candidate,
            root,
            output / item["id"],
            item["argv"][5],
            test_file=item["argv"][3],
            profile=profile,
            timeout=item["timeout"],
        )
    return results


def paired_results(config, baseline, candidate):
    pairs = {}
    requirements = {
        r["id"]: {
            "description": r["description"],
            "status": "NOT_VERIFIED",
            "checks": [],
        }
        for r in config["requirements"]
    }
    for item in config["checks"]:
        key = item["id"]
        b, c = baseline.get(key, {}), candidate.get(key, {})
        bm = {x["id"]: x["outcome"] for x in b.get("cases", [])}
        cm = {x["id"]: x["outcome"] for x in c.get("cases", [])}
        valid = bool(b.get("valid") and c.get("valid") and bm.keys() == cm.keys())
        pair = {
            "kind": item["kind"],
            "valid_comparison": valid,
            "baseline_passed": b.get("passed"),
            "candidate_passed": c.get("passed"),
            "pre_existing_failures": sorted(k for k, v in bm.items() if v == "failed"),
            "new_failures": sorted(
                k for k, v in cm.items() if v == "failed" and bm.get(k) == "passed"
            ),
            "unknown": not valid,
            "baseline_cases": bm,
            "candidate_cases": cm,
        }
        pairs[key] = pair
        for requirement in item["requirements"]:
            requirements[requirement]["checks"].append(key)
    for requirement in requirements.values():
        checks = [pairs[k] for k in requirement["checks"]]
        if checks and all(p["valid_comparison"] for p in checks):
            requirement["status"] = (
                "CHECKED_PASS"
                if all(p["candidate_passed"] for p in checks)
                else "CHECKED_FAIL"
            )
    return {
        "checks": pairs,
        "requirements": requirements,
        "resolved": None,
        "scope": "Declared controller checks only; Agent tests are development evidence, not acceptance criteria.",
    }
