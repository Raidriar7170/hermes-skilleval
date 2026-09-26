"""Prepare shared material, descriptors and deterministic order before freezing."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from native_gap_phase2_support.navigation import build_index  # noqa: E402

P = Path("/tmp/hermes-native-gap-phase2-private")
OLD = Path("/tmp/hermes-native-gap-phase1-private")
STUDY = "native-gap-phase2-same-library-v1"
C = ROOT / "configs" / STUDY
MODEL = (
    Path.home()
    / ".cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if (C / "freeze.json").exists():
        raise RuntimeError("Already frozen; no regeneration")
    lib = json.loads((C / "library-manifest.json").read_text())
    assert len(lib["completed_initial_batches"]) == 4
    split = json.loads((C / "split.json").read_text())
    screen = json.loads((ROOT / "artifacts" / STUDY / "split-screen.json").read_text())
    excluded = {x["instance_id"] for x in screen["rows"] if x["excluded"]}
    systems = [
        {
            "path": str(
                f.relative_to(
                    OLD.parent
                    / "hermes-native-gap-phase2-private/permissions-v3/state/skills"
                )
            ),
            "sha256": digest(f),
        }
        for f in sorted((P / "permissions-v3/state/skills").rglob("*"))
        if f.is_file()
    ]
    system_names = [
        s["name"]
        for group in json.loads((P / "permissions-v3/result.json").read_text())[
            "worker"
        ]["skills_list"]["data"]
        for s in group["skills"]
        if s["path"].startswith("/state/skills/")
    ]
    entries = [
        {k: e[k] for k in ["name", "description", "path"]} for e in lib["entries"]
    ]
    index = P / "metadata-index.json"
    build_index(entries, MODEL, index)
    bindings = [
        {"name": str(f.relative_to(ROOT)), "path": str(f), "sha256": digest(f)}
        for f in sorted((C / "skills").rglob("*"))
        if f.is_file()
    ]

    def common():
        return {
            "skills": str(C / "skills"),
            "binary_dir": str(OLD / "codex-linux-arm64"),
            "seccomp": str(
                ROOT / "src/hermes_skilleval/_maintenance/docker-seccomp-userns.json"
            ),
            "expected_skill_names": system_names + [e["name"] for e in entries],
            "expected_skill_metadata": entries,
            "system_assets": systems,
            "bindings": bindings,
            "encoder_path": str(MODEL),
            "index_path": str(index),
            "index_sha256": digest(index),
        }

    tasks = []
    for ids in split["pilot_task_candidates"].values():
        qualified = []
        for iid in ids:
            if iid in excluded:
                continue
            candidates = list(
                (P / "prepared-images-v3" / iid).glob("result.json")
            ) + list((P / "prepared-images" / iid).glob("result.json"))
            valid = [
                json.loads(f.read_text())
                for f in candidates
                if json.loads(f.read_text())["returncode"] == 0
            ]
            if valid:
                qualified.append((iid, valid[0]))
        assert len(qualified) >= 2, "insufficient qualified prepared tasks"
        tasks += qualified[:2]
    order = []
    rng = random.Random(20260926)
    for repeat in [1, 2]:
        for iid, image in tasks:
            arms = ["NATIVE", "ASSIST"]
            rng.shuffle(arms)
            for arm in arms:
                ident = f"{iid}-{arm.lower()}-r{repeat}"
                task = P / "public-tasks" / f"{iid}.json"
                d = common()
                d.update(
                    id=ident,
                    arm=arm,
                    public_task=str(task),
                    image=image["image_id"],
                    budget_seconds=900,
                    purpose="FORMAL_REPAIR",
                )
                d["bindings"] = bindings + [
                    {"name": "public_task", "path": str(task), "sha256": digest(task)}
                ]
                path = P / "descriptors" / f"{ident}.json"
                path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps(d, indent=2))
                order.append(
                    {
                        "id": ident,
                        "instance_id": iid,
                        "arm": arm,
                        "repeat": repeat,
                        "descriptor_sha256": digest(path),
                        "image_id": image["image_id"],
                    }
                )
    # Two harmless new model fixtures share the complete intended library and protocol.
    fixture = P / "preflight-fixture"
    fixture.mkdir(exist_ok=False)
    (fixture / "README.md").write_text(
        "A harmless packaging fixture. Install with pip install .; license MIT.\n"
    )
    (fixture / "sample.py").write_text("def add(a,b):\n    return a+b\n")
    for args in [
        ["init", "-q"],
        ["add", "."],
        [
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Harmless fixture",
        ],
    ]:
        subprocess.run(["git", "-C", str(fixture), *args], check=True)
    base = (
        subprocess.check_output(["git", "-C", str(fixture), "rev-parse", "HEAD"])
        .decode()
        .strip()
    )
    prompts = [
        "This is a harmless access check, not a repair. Read /state/skills/.system/skill-creator/SKILL.md and its references/openai_yaml.md. Read the complete experience catalog and one user skill of your choice. Report the filenames you successfully inspected and this fixture README. Do not modify skill assets or solve historical tasks.",
        "Inspect this small fixture and report what its README says about installation and licensing. The complete experience catalog is available; historical entries are optional and may be ignored if inapplicable. Do not modify the fixture or solve any historical issue.",
    ]
    for i, prompt in enumerate(prompts, 1):
        task = P / f"preflight-public-{i}.json"
        task.write_text(
            json.dumps(
                {
                    "instance_id": f"preflight-{i}",
                    "repo": "harmless-fixture",
                    "language": "Python",
                    "base_commit": base,
                    "problem_statement": prompt,
                }
            )
        )
        d = common()
        d.update(
            id=f"preflight-{i}",
            arm="NATIVE" if i == 1 else "ASSIST",
            public_task=str(task),
            fixture_dir=str(fixture),
            fixture_prompt=prompt,
            image=tasks[0][1]["image_id"],
            budget_seconds=180,
            purpose="HARMLESS_PREFLIGHT",
        )
        (P / f"preflight-descriptor-{i}.json").write_text(json.dumps(d, indent=2))
    plan = {
        "study": STUDY,
        "status": "PREPARED_NOT_FROZEN",
        "seed": 20260926,
        "arms": ["NATIVE", "ASSIST"],
        "order": order,
        "task_count": len(tasks),
        "library_count": len(entries),
        "repeats": 2,
        "planned_runs": len(order),
        "method": "ASSIST_METADATA_MMR",
        "top_k": 3,
        "lambda": 0.7,
        "stop": "nonpositive",
        "tie_break": "stable name ascending",
        "query": "Repository: <repo>\nLanguage: <language>\nProblem statement:\n<original statement>",
        "memory_use": False,
        "memory_generation": False,
        "total_seconds": 900,
        "shutdown_reserve": 15,
        "model": "gpt-6-sol",
        "effort": "high",
        "client": "0.155.0-alpha.16.4-linux-arm64",
        "system_assets": systems,
        "hidden_acceptance": "after all 16 calls terminate",
        "no_training": True,
        "default_policy": "UNCHANGED",
        "publication": "DRAFT_PR_ONLY",
    }
    (C / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    print(
        "prepared",
        len(order),
        "descriptors",
        len(entries),
        "skills; formal freeze still pending preflights/review",
    )


if __name__ == "__main__":
    main()
