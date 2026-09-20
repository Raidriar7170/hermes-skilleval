"""Read-only legacy development/payload inventory; no Agent or final-set calls."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/task-skill-failure-diagnostic-v1"


def read(path):
    return json.loads(path.read_text())


def main():
    legacy = ROOT / "artifacts/functional-gain-v2"
    rows = read(legacy / "collection/records.json")["rows"]
    assert all(r["split"] in ("train", "dev") for r in rows)
    bases = {
        (r["state_id"], r["repeat"]): r
        for r in rows
        if r["action"] == "NO_INTERVENTION"
    }
    pairs = [
        (r, bases[r["state_id"], r["repeat"]])
        for r in rows
        if r["action"] not in ("NO_INTERVENTION", "GENERIC_REMINDER")
    ]
    bad = [
        (r, b) for r, b in pairs if r["y_functional"] == 0 and b["y_functional"] == 1
    ]
    tied = [
        (r, b)
        for r, b in pairs
        if r["y_functional"] is not None and r["y_functional"] == b["y_functional"]
    ]
    controls = [
        next((r, b) for r, b in tied if r["task_id"] == tid)
        for tid in sorted({r["task_id"] for r, b in tied})[:2]
    ]

    def evidence(group, row):
        p = legacy / group / row["evidence_path"]
        for name, digest in row["artifact_sha256"].items():
            assert hashlib.sha256((p / name).read_bytes()).hexdigest() == digest
        failures = []
        for kind in ("target", "regression"):
            for case in ET.parse(p / (kind + "-junit.xml")).iter("testcase"):
                for child in case:
                    if child.tag in ("failure", "error"):
                        failures.append(
                            {
                                "kind": kind,
                                "case": case.get("name"),
                                "detail": child.text,
                            }
                        )
        return {
            k: row.get(k)
            for k in (
                "task_id",
                "split",
                "stage",
                "repeat",
                "action",
                "y_target",
                "y_regression",
                "y_functional",
                "patch_sha256",
                "checks",
            )
        } | {"evidence_path": str(p.relative_to(ROOT)), "failures": failures}

    native = [
        r
        for r in read(legacy / "native/records.json")["rows"]
        if r["task_id"] == "sqlite-utils-fix-60811e7"
    ]
    result = {
        "scope": "legacy_train_dev_only",
        "selection": "two tied task IDs in lexical order, first recorded tied pair; overlap with degradation task is retained",
        "native": [evidence("native", r) for r in native],
        "degradations": [
            {"skill": evidence("collection", r), "noop": evidence("collection", b)}
            for r, b in bad
        ],
        "tied_controls": [
            {"skill": evidence("collection", r), "noop": evidence("collection", b)}
            for r, b in controls
        ],
        "native_recovery_controls": [
            {k: r[k] for k in ("task_id", "stage", "repeat", "y_functional")}
            for r in rows
            if r["task_id"] == "sqlite-utils-fix-60811e7"
            and r["action"] == "NO_INTERVENTION"
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "legacy-inventory.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    registry = read(ROOT / "configs/conditional-applicability-v1/registry.json")
    manifest = read(
        ROOT / "configs/adaptive-skill-intervention-v1/payloads/manifest.json"
    )
    skills = []
    for r, m in zip(registry["skills"], manifest["skills"]):
        assert r["id"] == m["skill_id"]
        payload = ROOT / "configs/adaptive-skill-intervention-v1/payloads" / m["path"]
        assert hashlib.sha256(payload.read_bytes()).hexdigest() == m["payload_sha256"]
        assert hashlib.sha256(r["body"].encode()).hexdigest() == m["source_body_sha256"]
        skills.append(
            {
                k: r.get(k)
                for k in (
                    "id",
                    "source",
                    "origin",
                    "source_revision",
                    "package_revision",
                    "version_scope",
                )
            }
            | m
        )
    (OUT / "skill-inventory.json").write_text(
        json.dumps({"registry_id": registry["registry_id"], "skills": skills}, indent=2)
        + "\n"
    )
    print(
        json.dumps(
            {
                "legacy_degradations": len(bad),
                "ordered_tie_controls": len(controls),
                "frozen_skills_verified": len(skills),
                "new_agent_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
