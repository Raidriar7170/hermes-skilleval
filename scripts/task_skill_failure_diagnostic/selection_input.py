"""Export only pre-decision public observations for a fresh content analyst.

No trusted/reference directory, native terminal verdict, panel stratum, terminal
candidate or future turn is included. The coordinating author is answer-exposed.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from hermes_skilleval.intervention.session import dump, inventory


def read(p):
    return json.loads(p.read_text())


def main():
    p = argparse.ArgumentParser()
    for key in ("native", "plan", "tasks", "output", "skills", "payloads"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    plan = read(a.plan)
    plan_sha = hashlib.sha256(a.plan.read_bytes()).hexdigest()
    if read(a.native / "identity.json") != {"plan_sha256": plan_sha}:
        raise ValueError("native plan mismatch")
    panel = read(a.native / "panel.json")
    audit = a.native / "acceptance-audit.json"
    if (
        panel.get("acceptance_audit_sha256")
        != hashlib.sha256(audit.read_bytes()).hexdigest()
    ):
        raise ValueError("panel lacks acceptance validity audit")
    if (
        read(audit)["records_sha256"]
        != hashlib.sha256((a.native / "records.json").read_bytes()).hexdigest()
    ):
        raise ValueError("native records changed after acceptance audit")
    manifest = read(a.payloads / "manifest.json")
    shutil.copytree(a.skills, a.output / "skills")
    shutil.copytree(a.payloads, a.output / "payloads")
    # Manifest has a relative registry path; include only its public skill
    # metadata/bodies, not the containing research configs.
    registry = read(a.payloads / manifest["registry_relative_path"])
    dump(a.output / "registry.json", registry)
    for entry in panel["states"]:
        task = next(t for t in plan["tasks"] if t["task_id"] == entry["task_id"])
        cp = Path(entry["checkpoint"])
        meta = read(cp / "checkpoint.json")
        for scope in ("source", "scratch"):
            if inventory(cp / scope) != meta["files"][scope]:
                raise ValueError("visible checkpoint changed")
        dest = a.output / task["task_id"]
        dest.mkdir()
        shutil.copytree(cp / "source", dest / "source", symlinks=True)
        # Scratch is not copied: may contain redundant bulky diagnostics. All
        # observed public tool outputs and source are included; omission explicit.
        shutil.copytree(a.tasks / task["task_id"] / "public-docs", dest / "public-docs")
        dump(
            dest / "context.json",
            {
                "task_id": task["task_id"],
                "repository": task["repository"],
                "base_commit": task["base_commit"],
                "state": meta["state"],
                "visible_events": meta["visible_events"],
                "remaining_seconds": meta["remaining_seconds"],
                "visible_prefix_sha256": meta["visible_prefix_sha256"],
                "source_files": meta["files"]["source"],
                "scratch_visibility": "Tool outputs retained; unobserved scratch file contents omitted from analyst input only. Real tails restore full scratch.",
            },
        )
    instructions = """# Public-only content selection
Read only this directory. It is your complete allowed analysis input. Do not access parent directories, prior studies, trusted/reference tests, terminal records, GitHub fixes, the Internet, or future/source files outside it. Do not execute repair agents or modify files.
For each task directory use context.json and the actual source/public-docs at that checkpoint, plus all ten skills and actual payloads. Choose one existing skill with the strongest concrete payload passage and version-compatible guidance. Break equal evidence by registry order. If none has supported applicability, use skill_id null and status NO_SUPPORTED_EXISTING_SKILL. Generic debugging/verification can be supported when a specific observed workflow obstacle matches their actual instructions; do not select purely by name.
Return a JSON object keyed by task_id. For each provide public_requirement, visible_obstacle, obstacle_evidence (exact input locations), hypothesized_missing_knowledge (explicit hypothesis), nonknowledge_alternatives, skill_id, source_version, relevant_actual_payload_passage (verbatim substring of the actual payload), scope_match (direct/partial/none/unknown), version_match (supported/conflict/unknown), observed_previous_use (yes/no/unknown), rationale, and other_candidates with a reason for each of the other nine (or all ten if none) in registry order.
Do not infer hidden test results or base-model knowledge. K is evidence-selected existing guidance, never an oracle or learned routing result. No new guidance can be generated. Do not propose extra hints to inject.
"""
    (a.output / "INSTRUCTIONS.md").write_text(instructions)
    dump(
        a.output / "input-manifest.json",
        {
            "role": "answer-exposed coordinator exported public prefix for fresh analysis context",
            "plan_sha256": plan_sha,
            "files": inventory(a.output),
            "excluded": [
                "reference",
                "trusted",
                "terminal verdicts",
                "native terminal source",
                "panel strata",
                "future branch outcomes",
            ],
            "model_calls": 0,
        },
    )
    print(
        json.dumps(
            {"states": len(panel["states"]), "output": str(a.output), "model_calls": 0}
        )
    )


if __name__ == "__main__":
    main()
