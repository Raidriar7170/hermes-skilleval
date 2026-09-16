"""Versioned weak-label preparation. Labels and source quotations never feed inference."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

SCHEMA = "conditional-applicability-v1"
APP = {"APPLICABLE", "NOT_APPLICABLE", "CONFLICT", "UNKNOWN"}
SPEC = {"TASK_SPECIFIC", "GENERAL_WORKFLOW", "UNKNOWN"}


def read_json(path):
    return json.loads(Path(path).read_text())


def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )


def write_rows(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        "".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in rows)
    )


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_splits(tasks):
    seen = defaultdict(set)
    ids = set()
    for t in tasks:
        if t["task_id"] in ids or t["split"] not in {
            "fit",
            "model-dev",
            "cal",
            "check",
        }:
            raise ValueError("duplicate task or invalid split")
        ids.add(t["task_id"])
        for key in ("parent_task_id", "repair_group_id"):
            seen[(key, t[key])].add(t["split"])
        if t.get("derived_from"):
            seen[("parent_task_id", t["derived_from"])].add(t["split"])
    if any(len(v) != 1 for v in seen.values()):
        raise ValueError("parent/variant/repair group crosses splits")


def targets(row):
    a, s = row["applicability_label"], row["specificity_label"]
    if a not in APP or (a == "APPLICABLE" and s not in SPEC):
        raise ValueError("invalid dual-axis label")
    if a != "APPLICABLE" and s is not None:
        raise ValueError("specificity only defined given applicability")
    return (
        (None if a == "UNKNOWN" else float(a == "APPLICABLE")),
        (float(s == "TASK_SPECIFIC") if a == "APPLICABLE" and s != "UNKNOWN" else None),
    )


def group_weights(rows):
    """One unit per group, then equal tasks, requirements and candidate rows."""
    tree = defaultdict(lambda: defaultdict(Counter))
    for r in rows:
        tree[r["repair_group_id"]][r["parent_task_id"]][r["requirement_id"]] += 1
    return [
        1
        / len(tree)
        / len(tree[r["repair_group_id"]])
        / len(tree[r["repair_group_id"]][r["parent_task_id"]])
        / tree[r["repair_group_id"]][r["parent_task_id"]][r["requirement_id"]]
        for r in rows
    ]


def merge_annotations(tasks_path, registry_path, pass_paths, output):
    tasks = read_json(tasks_path)
    validate_splits(tasks)
    ti = {t["task_id"]: t for t in tasks}
    reg = read_json(registry_path)
    si = {s["id"]: s for s in reg["skills"]}
    expected = {(t, s) for t in ti for s in si}
    passes = []
    annotators = []
    for path in pass_paths:
        doc = read_json(path)
        annotators.append(doc["annotator_id"])
        indexed = {}
        if doc.get("human_reviewed") is not False:
            raise ValueError("weak-label provenance required")
        for r in doc["rows"]:
            key = (r["task_id"], r["skill_id"])
            if key not in expected or key in indexed:
                raise ValueError("unknown/duplicate annotation pair")
            targets(r)
            if (
                not r["request_quote"]
                or r["request_quote"] not in ti[key[0]]["request"]
            ):
                raise ValueError("request quote not literal: " + str(key))
            if not r["skill_quote"] or r["skill_quote"] not in si[key[1]]["body"]:
                raise ValueError("skill quote not literal: " + str(key))
            if not r["application_explanation"] or not set(r["roles"]) <= {
                "procedure",
                "implementation",
                "verification",
            }:
                raise ValueError("invalid role/explanation")
            if r["applicability_label"] == "APPLICABLE" and not r["roles"]:
                raise ValueError("applicable step requires role")
            indexed[key] = r
        if set(indexed) != expected:
            raise ValueError("incomplete full-catalog annotation")
        passes.append(indexed)
    if len(passes) != 2 or len(set(annotators)) != 2:
        raise ValueError("two distinct independent contexts required")
    merged = []
    for key in sorted(expected):
        t, s = ti[key[0]], si[key[1]]
        a, b = [p[key] for p in passes]
        agree = a["applicability_label"] == b["applicability_label"]
        app = a["applicability_label"] if agree else "UNKNOWN"
        spec_agree = a["specificity_label"] == b["specificity_label"]
        spec = (
            (a["specificity_label"] if spec_agree else "UNKNOWN")
            if app == "APPLICABLE"
            else None
        )
        row = {
            k: t[k]
            for k in (
                "task_id",
                "parent_task_id",
                "requirement_id",
                "repair_group_id",
                "split",
                "repository",
                "source_revision",
                "request_ref",
                "public_context_ref",
                "origin_kind",
                "derived_from",
                "previously_observed",
                "composite_requirement",
            )
        }
        row.update(
            schema=SCHEMA,
            row_id=key[0] + "::" + key[1],
            skill_id=key[1],
            package_revision=s["package_revision"],
            package_hash=s["package_sha256"],
            registry_id=reg["registry_id"],
            applicability_label=app,
            specificity_label=spec,
            roles=sorted(set(a["roles"]) | set(b["roles"])),
            conditions=[a["conditions"], b["conditions"]],
            request_quote_refs=[a["request_quote"], b["request_quote"]],
            skill_quote_refs=[a["skill_quote"], b["skill_quote"]],
            application_explanation=[
                a["application_explanation"],
                b["application_explanation"],
            ],
            label_source="two_independent_model_contexts",
            annotator_ids=annotators,
            agreement={
                "applicability": agree,
                "specificity": spec_agree if app == "APPLICABLE" else None,
            },
            human_reviewed=False,
            annotation_records=[a, b],
        )
        merged.append(row)
    write_rows(output, merged)
    return {
        "rows": len(merged),
        "source_hashes": [file_hash(p) for p in pass_paths],
        "validation": "literal provenance only; semantic weak-label truth not certified",
    }


def identifiability(rows):
    """Development only: callers cannot accidentally inspect check outcomes here."""
    rows = [r for r in rows if r["split"] in {"fit", "model-dev"}]
    by = defaultdict(list)
    for r in rows:
        by[r["skill_id"]].append(r)
    result = {}
    for skill, rr in by.items():
        pos = {r["repair_group_id"] for r in rr if targets(r)[0] == 1}
        neg = {r["repair_group_id"] for r in rr if targets(r)[0] == 0}
        result[skill] = {
            "labels": dict(Counter(r["applicability_label"] for r in rr)),
            "specificity": dict(
                Counter(r["specificity_label"] for r in rr if r["specificity_label"])
            ),
            "positive_groups": sorted(pos),
            "negative_groups": sorted(neg),
            "conditional_group_pairs": len(
                {(a, b) for a in pos for b in neg if a != b}
            ),
            "agreement": sum(r["agreement"]["applicability"] for r in rr) / len(rr),
        }
    return {
        "scope": "fit/model-dev only",
        "skills": result,
        "conditional_signal": sum(
            v["conditional_group_pairs"] for v in result.values()
        ),
    }


def records_equal(actual, expected):
    """Tiny float-only portability tolerance; discrete decisions remain exact."""
    import math

    if type(actual) is not type(expected):
        return False
    if isinstance(actual, float):
        return (
            math.isfinite(actual)
            and math.isfinite(expected)
            and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10)
        )
    if isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(
            records_equal(actual[k], expected[k]) for k in actual
        )
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(
            records_equal(a, b) for a, b in zip(actual, expected)
        )
    return actual == expected


def validate_merged(rows, tasks, registry):
    """Recheck the two literal judgment records and consensus, without a model."""
    validate_splits(tasks)
    ti = {t["task_id"]: t for t in tasks}
    si = {s["id"]: s for s in registry["skills"]}
    expected = {(t, s) for t in ti for s in si}
    if (
        len(rows) != len(expected)
        or {(r["task_id"], r["skill_id"]) for r in rows} != expected
    ):
        raise ValueError("complete unique task-catalog product required")
    for r in rows:
        t, s = ti[r["task_id"]], si[r["skill_id"]]
        if any(
            r[k] != t[k]
            for k in (
                "split",
                "repair_group_id",
                "parent_task_id",
                "requirement_id",
                "source_revision",
                "request_ref",
            )
        ):
            raise ValueError("row provenance mismatch")
        if (
            r["package_hash"] != s["package_sha256"]
            or r["registry_id"] != registry["registry_id"]
        ):
            raise ValueError("row registry mismatch")
        if r["human_reviewed"] is not False or len(r["annotation_records"]) != 2:
            raise ValueError("two model judgments required")
        a, b = r["annotation_records"]
        for original in (a, b):
            targets(original)
            if (
                not original["request_quote"]
                or original["request_quote"] not in t["request"]
                or not original["skill_quote"]
                or original["skill_quote"] not in s["body"]
            ):
                raise ValueError("annotation citation mismatch")
        app = (
            a["applicability_label"]
            if a["applicability_label"] == b["applicability_label"]
            else "UNKNOWN"
        )
        spec = (
            (
                a["specificity_label"]
                if a["specificity_label"] == b["specificity_label"]
                else "UNKNOWN"
            )
            if app == "APPLICABLE"
            else None
        )
        if (r["applicability_label"], r["specificity_label"]) != (app, spec):
            raise ValueError("consensus mismatch")
