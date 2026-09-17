"""Validate literal sources and reconcile two blind text judgments before scoring."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def expand(document):
    if isinstance(document, list):
        return document
    rows = []
    for task, skill, label, role, quote, request, application, unknown in document[
        "rows"
    ]:
        rows.append(
            dict(
                task_id=document["tasks"][task],
                skill_id=document["skills"][skill],
                label=label,
                role=role,
                quote=document["skill_quotes"][quote],
                request_quote=document["request_quotes"][request],
                application=application,
                uncertainty=unknown,
            )
        )
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in (
        "pass-a",
        "pass-b",
        "registry",
        "manifest",
        "protocol",
        "requests",
        "output",
    ):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    registry = json.loads(a.registry.read_text())
    skills = {s["id"]: s for s in registry["skills"]}
    manifest = json.loads(a.manifest.read_text())["candidates"]
    tasks = {t["task_id"]: t for t in manifest if t["admission"] == "QUALIFIED"}
    protocol = json.loads(a.protocol.read_text())
    passes = []
    for path in (a.pass_a, a.pass_b):
        entries = expand(json.loads(path.read_text()))
        indexed = {}
        for r in entries:
            key = (r["task_id"], r["skill_id"])
            if key in indexed or key[0] not in tasks or key[1] not in skills:
                raise ValueError("duplicate/unknown annotation key")
            skill = skills[key[1]]
            fields = [
                f
                for f in ("body", "description")
                if r["quote"] and r["quote"] in skill.get(f, "")
            ]
            request = (a.requests / (key[0] + "-public.md")).read_text()
            if (
                not fields
                or not r["request_quote"]
                or r["request_quote"] not in request
            ):
                raise ValueError("nonliteral quote: " + str(key))
            if r["label"] not in {
                "SUPPORTED",
                "NOT_APPLICABLE",
                "CONTRADICTED",
                "UNKNOWN",
            }:
                raise ValueError("invalid label")
            if r["label"] == "SUPPORTED" and r["role"] not in {
                "procedure",
                "implementation",
                "verification",
            }:
                raise ValueError("supported role required")
            indexed[key] = {
                **r,
                "source_field": fields[0],
                "source": "model_judged_text",
            }
        if set(indexed) != {(t, s) for t in tasks for s in skills}:
            raise ValueError("each pass must cover full task x skill pool")
        passes.append(indexed)
    rows = []
    for key in sorted(passes[0]):
        left, right = [d[key] for d in passes]
        task = tasks[key[0]]
        family = task["family_id"]
        for group, members in protocol["group_merges"].items():
            if family in members:
                family = group
        split = (
            "support-fit"
            if task["split"] in {"rank-train", "rank-dev"}
            else "support-check"
            if task["split"] == "final-test"
            else "support-cal"
        )
        agreed = left["label"] == right["label"]
        label = left["label"] if agreed else "UNKNOWN"
        rows.append(
            dict(
                task_id=key[0],
                skill_id=key[1],
                family=family,
                split=split,
                previously_observed=True,
                label=label,
                agreement=agreed,
                source="model_judged_text",
                human_reviewed=False,
                constraint_state="known offline source-repair environment; no affirmative network precondition",
                support_roles=sorted({r["role"] for r in (left, right) if r["role"]}),
                support_quotes=[r["quote"] for r in (left, right)]
                if label == "SUPPORTED"
                else [],
                judgments=[left, right],
                package_sha256=skills[key[1]]["package_sha256"],
            )
        )
    families = {}
    for row in rows:
        previous = families.setdefault(row["family"], row["split"])
        if previous != row["split"]:
            raise ValueError("family overlap between partitions")
    result = dict(
        schema="text-support-labels-v1",
        rows=rows,
        pass_sha256=[
            hashlib.sha256(p.read_bytes()).hexdigest() for p in (a.pass_a, a.pass_b)
        ],
        protocol_sha256=hashlib.sha256(a.protocol.read_bytes()).hexdigest(),
        registry_id=registry["registry_id"],
        counts=dict(Counter(r["label"] for r in rows)),
        disagreements=sum(not r["agreement"] for r in rows),
        split_families={
            s: sorted(f for f, v in families.items() if v == s)
            for s in sorted(set(families.values()))
        },
        limitation="two model judgments and literal quotes are not human truth; complete public request is one composite requirement",
    )
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {k: result[k] for k in ("counts", "disagreements", "split_families")}
        )
    )


if __name__ == "__main__":
    main()
