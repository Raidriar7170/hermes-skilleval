"""Bounded advisory replay using frozen selection and the shared isolated executor."""

import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path

from .advisory_capture import inventory

STUDY = "advisory-utility-replay-v1"
ARMS = ("N", "F2", "T2", "J2")
TASKS = (
    "sqlite-utils-issue-344",
    "sqlite-utils-issue-400",
    "sqlite-utils-issue-368",
    "csvkit-issue-1225",
)
J_SHA = "62974d9088aaaa27effdc65d8407e7ccb93d2669487642eb7d826227c60b8645"


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2) + "\n")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def load_catalog(path, assets):
    """Verify legacy file-map identity; derive runner's size/mode-aware identity."""
    from hermes_skilleval.skill_package import package_manifest

    registry = read(path)
    if digest(registry["skills"]) != registry["registry_id"]:
        raise ValueError("registry identity mismatch")
    for skill in registry["skills"]:
        root = assets / skill["package_path"]
        if not root.resolve().is_relative_to(assets.resolve()):
            raise ValueError("package escape")
        actual = package_manifest(root)
        files = {r["path"]: r["sha256"] for r in actual["files"]}
        if files != skill["package_files"] or digest(files) != skill["package_sha256"]:
            raise ValueError("frozen complete package changed")
        skill["legacy_package_sha256"] = skill["package_sha256"]
        skill["package_sha256"] = actual["sha256"]
    registry["legacy_registry_id"] = registry["registry_id"]
    registry["registry_id"] = digest(registry["skills"])
    return registry


def schedule():
    rng = random.Random(7170)
    rows = []
    for tid in TASKS:
        for repeat in (1, 2):
            arms = list(ARMS)
            rng.shuffle(arms)
            for arm in arms:
                rows.append(
                    {
                        "task_id": tid,
                        "arm": arm,
                        "repeat": repeat,
                        "run_id": f"advisory-{tid}-{arm}-r{repeat}",
                        "timeout": 600,
                    }
                )
    return rows


def select(arm, registry, fixed, repository, rows):
    catalog = [s["id"] for s in registry["skills"]]
    if arm == "N":
        ranked = catalog
    elif arm == "F2":
        ranked = fixed.get(repository, fixed["default"])
    elif arm in ("T2", "J2"):
        if {r["skill_id"] for r in rows} != set(catalog) or len(rows) != len(catalog):
            raise ValueError("incomplete candidate pool")
        key = "text" if arm == "T2" else "joint"
        if any(not math.isfinite(r[key]) for r in rows):
            raise ValueError("invalid score")
        ranked = [
            r["skill_id"]
            for r in sorted(rows, key=lambda r: (-r[key], r["skill_id"]))[:2]
        ]
    else:
        raise ValueError("unknown arm")
    if (
        len(set(ranked)) != len(ranked)
        or not set(ranked) <= set(catalog)
        or (arm != "N" and len(ranked) != 2)
    ):
        raise ValueError("invalid frozen selection")
    return {
        "ranked_ids": ranked,
        "presented_ids": [i for i in catalog if i in ranked],
        "recommendation_mode": "advisory",
        "support_certified": False,
        "recommendation_status": "SELECTED",
        "selection_source": dict(
            N="native", F2="frozen_fixed", T2="frozen_text", J2="frozen_joint"
        )[arm],
    }


def prepare(a):
    from hermes_skilleval._maintenance.check import check, identity
    from hermes_skilleval.repository_profile import profile_for

    a.output.mkdir(parents=True, exist_ok=False)
    records = []
    for tid in TASKS:
        root = a.tasks / tid
        t = read(root / "task.json")
        profile = profile_for(t)
        cells = {}
        for variant in ("base", "reference"):
            for kind in ("target", "regression"):
                cells[variant + "-" + kind] = check(
                    root / variant,
                    root / "trusted",
                    a.output / tid / (variant + "-" + kind),
                    t[kind + "_selector"],
                    test_file=t["trusted_test_file"],
                    profile=profile,
                )
        valid = all(c["valid"] for c in cells.values())
        passed = (
            valid
            and not cells["base-target"]["passed"]
            and all(
                cells[k]["passed"]
                for k in ("base-regression", "reference-target", "reference-regression")
            )
        )
        tests = {
            k: sorted(c["id"] for c in cells["reference-" + k]["cases"])
            for k in ("target", "regression")
        }
        passed = passed and all(
            sorted(c["id"] for c in cells["base-" + k]["cases"]) == tests[k]
            for k in tests
        )
        rec = {
            "task_id": tid,
            "qualified": passed,
            "task_sha256": sha(root / "task.json"),
            "base_manifest": inventory(root / "base"),
            "trusted_manifest": inventory(root / "trusted"),
            "image_id": identity(profile.image),
            "test_ids": tests,
            "cells": {
                k: {x: v[x] for x in ("valid", "passed", "cases")}
                for k, v in cells.items()
            },
        }
        write(a.output / tid / "qualified.json", rec)
        records.append(rec)
        print(tid, passed, flush=True)
    write(a.output / "summary.json", records)


def recommend(a):
    from .pointwise_support import public_input, representation, scorer_identity
    from .reranker import Reranker
    from .applicability_eval import predict_text
    from .gate import sigmoid

    if a.output.exists():
        raise ValueError("preserve recommendation lock")
    registry = load_catalog(a.registry, a.assets)
    tasks = read(a.tasks / "public-tasks.json")
    model = read(a.model_config)["J"]
    model["adapter"] = str(Path(model["adapter"]).resolve())
    if (
        model["lambda_spec"] != 1
        or sha(Path(model["adapter"]) / "adapter_model.safetensors") != J_SHA
    ):
        raise ValueError("wrong J candidate")
    identity = scorer_identity(model)
    if (
        identity
        != read(a.project / "configs/frozen-independent-validation-v1/protocol.json")[
            "models"
        ]["J"]["scorer_identity"]
    ):
        raise ValueError("J scorer identity changed")
    for root, field in [
        (model["base"], "base_files"),
        (model["adapter"], "adapter_files"),
    ]:
        for name, value in model[field].items():
            if sha(Path(root) / name) != value:
                raise ValueError("frozen model asset changed")
    baselines = read(
        a.project / "artifacts/conditional-applicability-v1/baseline-models.json"
    )
    start = time.monotonic()
    scorer = Reranker(
        model["base"],
        adapter=model["adapter"],
        device=model["device"],
        max_length=model["max_length"],
    )
    load_s = time.monotonic() - start
    results = {}
    forward_start = time.monotonic()
    for t in tasks:
        if inventory(a.tasks / t["task_id"] / "base") != t["source_manifest"]:
            raise ValueError("base changed before score")
        rows = []
        for skill in registry["skills"]:
            inp = public_input(t, skill)
            logits, obs = scorer.scores(
                [
                    representation(inp, axis)
                    for axis in ("applicability", "specificity_given_applicable")
                ]
            )
            z = logits.detach().cpu().tolist()
            rows.append(
                {
                    "skill_id": skill["id"],
                    "logits": z,
                    "joint": sigmoid(z[0]) * sigmoid(z[1]),
                    "text": predict_text(baselines["models"]["cheap_text"], inp)[0],
                    "input_sha256": digest(inp.__dict__),
                    "tokens": obs,
                }
            )
        results[t["task_id"]] = {
            "rows": rows,
            "methods": {
                arm: select(arm, registry, baselines["fixed"], t["repository"], rows)
                for arm in ARMS
            },
        }
        print(
            t["task_id"],
            {
                k: v["presented_ids"]
                for k, v in results[t["task_id"]]["methods"].items()
            },
            flush=True,
        )
    out = {
        "study": STUDY,
        "candidate": "training-lambda-1",
        "epoch": 3,
        "adapter_sha256": J_SHA,
        "scorer_identity": identity,
        "registry_sha256": sha(a.registry),
        "public_tasks_sha256": sha(a.tasks / "public-tasks.json"),
        "baseline_sha256": sha(
            a.project / "artifacts/conditional-applicability-v1/baseline-models.json"
        ),
        "fixed": baselines["fixed"],
        "tasks": results,
        "cost": {
            "load_seconds": load_s,
            "score_seconds": time.monotonic() - forward_start,
            "forward_calls": scorer.forward_calls,
            "candidate_pairs": 40,
            "axes": 2,
            "dollars": None,
        },
    }
    write(a.output, out)


def verify_lock(a):
    from hermes_skilleval._maintenance.check import identity

    protocol = read(a.protocol)
    recs = read(a.recommendations)
    if (
        protocol["schedule"] != schedule()
        or protocol["model"] != "gpt-5.6-sol"
        or protocol["effort"] != "medium"
        or protocol["concurrency"] != 1
    ):
        raise ValueError("frozen design changed")
    for name, path in [
        ("recommendations", a.recommendations),
        ("registry", a.registry),
        ("public_tasks", a.tasks / "public-tasks.json"),
    ]:
        if sha(path) != protocol[name + "_sha256"]:
            raise ValueError("lock changed: " + name)
    for relative, expected in protocol["executor_sources"].items():
        package = Path(__file__).resolve().parents[1]
        if sha(package / relative) != expected:
            raise ValueError("executor/verifier source changed: " + relative)
    registry = load_catalog(a.registry, a.assets)
    if (
        sha(a.registry) != recs["registry_sha256"]
        or sha(a.tasks / "public-tasks.json") != recs["public_tasks_sha256"]
    ):
        raise ValueError("recommendation binding changed")
    for t in read(a.tasks / "public-tasks.json"):
        result = recs["tasks"][t["task_id"]]
        for row in result["rows"]:
            z = row["logits"]
            product = 1 / (1 + math.exp(-z[0])) / (1 + math.exp(-z[1]))
            if abs(product - row["joint"]) > 1e-12:
                raise ValueError("joint score changed")
        for arm in ARMS:
            if result["methods"][arm] != select(
                arm, registry, recs["fixed"], t["repository"], result["rows"]
            ):
                raise ValueError("selection mismatch")
    if a.command == "run":
        canary = read(a.canary)
        if not canary["passed"] or canary["images"].get(protocol["image"]) != identity(
            protocol["image"]
        ):
            raise ValueError("isolation binding changed")
    return protocol, recs, registry


def run(a):
    import shutil
    import tarfile
    from hermes_skilleval._maintenance.execution import run_agent
    from hermes_skilleval._maintenance import container_runner
    from hermes_skilleval._maintenance.check import check, identity
    from hermes_skilleval.repository_profile import profile_for, validate_changes
    from hermes_skilleval.live_agent_runtime import (
        LiveAgentSkill,
        prepare_live_agent_workspace,
    )
    from .context import shared_prompt
    from .advisory_capture import capture_complete, reconstruct

    protocol, recs, registry = verify_lock(a)
    for x in [a.tasks, a.private_root, a.workspace_root, a.output, a.assets]:
        for y in [a.workspace_root]:
            if x != y and (
                x.resolve().is_relative_to(y.resolve())
                or y.resolve().is_relative_to(x.resolve())
            ):
                raise ValueError("workspace visibility overlap")
    a.output.mkdir(parents=True, exist_ok=True)
    public = {t["task_id"]: t for t in read(a.tasks / "public-tasks.json")}
    for cell in protocol["schedule"]:
        tid, arm, rid = cell["task_id"], cell["arm"], cell["run_id"]
        output = a.output / rid
        if (output / "result.json").exists():
            prior = read(output / "result.json")
            if any(
                prior.get(k) != cell[k] for k in ("run_id", "task_id", "arm", "repeat")
            ) or prior.get("recommendations_sha256") != sha(a.recommendations):
                raise ValueError("resume result binding mismatch")
            if prior["result"] in ("UNKNOWN", "NOT_RUN"):
                raise ValueError(
                    "unresolved attempt; inspect and finalize without model replay"
                )
            if prior.get("patch_sha256") != sha(output / "capture/candidate.patch"):
                raise ValueError("resume patch changed")
            continue
        if output.exists():
            raise ValueError(
                "unfinished attempt requires inspection, never overwrite: " + rid
            )
        root = a.tasks / tid
        t = read(root / "task.json")
        q = read(a.qualification / tid / "qualified.json")
        profile = profile_for(t)
        if profile.image != protocol["image"]:
            raise ValueError("task image differs from sandbox canary")
        if not q["qualified"]:
            raise ValueError("task unqualified: " + tid)
        if (
            sha(root / "task.json") != q["task_sha256"]
            or inventory(root / "base") != q["base_manifest"]
            or inventory(root / "trusted") != q["trusted_manifest"]
            or identity(profile.image) != q["image_id"]
        ):
            raise ValueError("qualification changed")
        if (
            sha(a.qualification / tid / "qualified.json")
            != protocol["qualification_sha256"][tid]
        ):
            raise ValueError("qualification lock changed")
        if any(
            k.split("/")[0] in (".git", ".agents", ".codex")
            for k in inventory(root / "base")
        ):
            raise ValueError("base skill/config contamination")
        method = recs["tasks"][tid]["methods"][arm]
        ids = method["presented_ids"]
        mounted = [
            LiveAgentSkill(
                s["id"],
                s["name"],
                s["body"],
                s["description"],
                a.assets / s["package_path"],
                s["package_sha256"],
            )
            for s in registry["skills"]
            if s["id"] in ids
        ]
        initial = prepare_live_agent_workspace(
            base_dir=a.private_root / "initial", run_id=rid, mounted_skills=mounted
        )
        shutil.copytree(root / "base", initial.workspace_path, dirs_exist_ok=True)
        before = inventory(initial.workspace_path)
        container_runner.IMAGE = profile.image
        r = run_agent(
            base=root / "base",
            public_request=shared_prompt(
                public[tid]["request"], public[tid]["context"]
            ),
            profile=profile,
            registry=registry,
            ids=ids,
            skill_assets=a.assets,
            output=output,
            workspace_root=a.workspace_root,
            private_root=a.private_root,
            run_id=rid,
            task_id=tid,
            arm=arm,
            timeout=cell["timeout"],
            model=protocol["model"],
            effort=protocol["effort"],
            scratch=True,
            metadata={
                "repeat": cell["repeat"],
                "base_commit": t["base_commit"],
                "recommendations_sha256": sha(a.recommendations),
            },
        )
        r.update(
            result="UNKNOWN",
            policy_status="UNKNOWN",
            patch_status="MISSING",
            method=method,
        )
        if not r["cleanup_confirmed"]:
            write(output / "result.json", r)
            raise RuntimeError("cleanup unconfirmed")
        candidate = Path(r["workspace"])
        write(output / "raw-inventory.json", inventory(candidate, runtime=True))
        # Private complete archive retained even when later patch/policy checks reject.
        with tarfile.open(
            output / "raw-candidate.tar", "w", dereference=False
        ) as archive:
            archive.add(candidate, arcname="candidate")
        try:
            cap = capture_complete(
                initial.workspace_path, candidate, output / "capture"
            )
            if cap["before"] != before:
                raise ValueError("initial workspace changed")
            write(output / "capture.json", cap)
            r["patch_status"] = "CAPTURED"
            r["patch_sha256"] = cap["patch_sha256"]
            r["changed_files"] = cap["changed_files"]
            try:
                validate_changes(
                    profile,
                    cap["changed_files"],
                    before=cap["before"],
                    after=cap["after"],
                    candidate=output / "capture/snapshot",
                )
            except ValueError as exc:
                r.update(
                    result="POLICY_FAILURE", policy_status="REJECTED", error=str(exc)
                )
                write(output / "result.json", r)
                print(rid, r["result"], flush=True)
                continue
            r["policy_status"] = "PASS"
            expected = {
                k: v for k, v in cap["after"].items() if not k.startswith(".agents/")
            }
            reconstruct(
                root / "base",
                output / "capture/candidate.patch",
                output / "verification/rebuilt",
                expected,
            )
            r["patch_status"] = "RECONSTRUCTED"
            results = {
                kind: check(
                    output / "verification/rebuilt",
                    root / "trusted",
                    output / "verification" / kind,
                    t[kind + "_selector"],
                    test_file=t["trusted_test_file"],
                    profile=profile,
                )
                for kind in ("target", "regression")
            }
            valid = all(
                v["valid"] and sorted(c["id"] for c in v["cases"]) == q["test_ids"][k]
                for k, v in results.items()
            )
            r["checks"] = {
                k: {field: v[field] for field in ("valid", "passed", "cases")}
                for k, v in results.items()
            }
            r["verifier_valid"] = valid
            if r["execution_status"] == "NOT_STARTED":
                r["result"] = "NOT_RUN"
            elif valid and r["execution_status"] == "STARTED":
                r["result"] = (
                    "SUCCESS"
                    if all(v["passed"] for v in results.values())
                    else "TIMEOUT"
                    if r.get("timed_out")
                    else "FUNCTIONAL_FAILURE"
                )
        except Exception as exc:
            r["error"] = str(exc)
        write(output / "result.json", r)
        print(rid, r["result"], flush=True)
        if r["result"] in ("UNKNOWN", "NOT_RUN"):
            raise RuntimeError(
                "infrastructure/launch uncertainty; pause frozen schedule"
            )


def summarize(a):
    from collections import Counter

    protocol, recs, registry = verify_lock(a)
    rows = []
    for cell in protocol["schedule"]:
        p = a.output / cell["run_id"] / "result.json"
        r = (
            read(p)
            if p.exists()
            else {"result": "NOT_RUN", "reason": "pending frozen schedule"}
        )
        if (
            p.exists()
            and r.get("patch_sha256")
            and sha(p.parent / "capture/candidate.patch") != r["patch_sha256"]
        ):
            raise ValueError("patch changed")
        rows.append(
            {
                **cell,
                **{
                    k: r.get(k)
                    for k in (
                        "result",
                        "reason",
                        "execution_status",
                        "timed_out",
                        "patch_status",
                        "policy_status",
                        "checks",
                        "usage",
                        "execution_seconds",
                        "changed_files",
                        "patch_sha256",
                        "error",
                    )
                },
            }
        )
    counts = {
        arm: dict(Counter(r["result"] for r in rows if r["arm"] == arm)) for arm in ARMS
    }
    out = {
        "study": STUDY,
        "study_scope": "EXPLORATORY_REPLAY_ON_SEEN_TASKS",
        "planned": 32,
        "rows": rows,
        "counts": counts,
        "support_certification": "NOT_CLAIMED",
        "deployment_recommendation": "KEEP_NATIVE",
        "recommendation_cost": recs["cost"],
    }
    write(a.output / "summary.json", out)
    print(json.dumps(counts, indent=2))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "command", choices=["prepare", "recommend", "run", "summarize", "records"]
    )
    for name in [
        "project",
        "tasks",
        "registry",
        "assets",
        "model-config",
        "output",
        "qualification",
        "recommendations",
        "protocol",
        "canary",
        "private-root",
        "workspace-root",
    ]:
        p.add_argument("--" + name, type=Path)
    a = p.parse_args(argv)
    if a.command == "prepare":
        prepare(a)
    elif a.command == "recommend":
        recommend(a)
    elif a.command == "run":
        run(a)
    else:
        summarize(a)


if __name__ == "__main__":
    main()
