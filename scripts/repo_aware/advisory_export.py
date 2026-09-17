"""Export bounded public evidence, retaining all plan cells and complete source patches."""

import argparse
import json
import re
import shlex
import shutil
from pathlib import Path
from hermes_skilleval.repo_routing.advisory_study import read, write, sha

p = argparse.ArgumentParser()
p.add_argument("--project", type=Path, required=True)
p.add_argument("--private", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
root = a.output
root.mkdir(parents=True, exist_ok=True)
protocol = read(a.project / "configs/advisory-utility-replay-v1/protocol.json")
write(root / "protocol.json", protocol)
source = a.private / "runs"
rows = []
reads = []
for cell in protocol["schedule"]:
    folder = source / cell["run_id"]
    path = folder / "result.json"
    if not path.exists():
        rows.append({**cell, "result": "NOT_RUN", "reason": "pending frozen schedule"})
        continue
    r = read(path)
    keys = (
        "execution_status",
        "result",
        "patch_status",
        "policy_status",
        "patch_sha256",
        "changed_files",
        "checks",
        "usage",
        "execution_seconds",
        "timed_out",
        "package_prepare_seconds",
        "cleanup_confirmed",
        "model",
        "effort",
    )
    row = {**cell, **{k: r.get(k) for k in keys}}
    row["private_result_sha256"] = sha(path)
    row["verification_seconds_sum"] = sum(
        read(f)["seconds"] for f in folder.glob("verification/*/result.json")
    )
    row["post_agent_seconds_derived_from_mtime"] = max(
        0.0, path.stat().st_mtime - (folder / "executor.json").stat().st_mtime
    )
    row["timing_boundary"] = (
        "Agent and verifier times instrumented; post-Agent interval is a filesystem-timestamp derivation including archive/capture/rebuild/checks"
    )
    for name in (
        "raw-inventory.json",
        "raw-candidate.tar",
        "events.jsonl",
        "executor.json",
    ):
        if (folder / name).exists():
            row[name + "_sha256"] = sha(folder / name)
    row["method"] = r["method"]
    if r.get("error"):
        row["error"] = (
            r["error"]
            .replace(str(a.private), "[private]")
            .replace(str(a.project), "[project]")
        )
    rows.append(row)
    if r.get("patch_sha256"):
        (root / "patches").mkdir(exist_ok=True)
        shutil.copy2(
            folder / "capture/candidate.patch",
            root / "patches" / (cell["run_id"] + ".patch"),
        )
    for kind in ("target", "regression"):
        xml = folder / "verification" / kind / "junit.xml"
        if xml.exists():
            dest = root / "checks" / cell["run_id"]
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(xml, dest / (kind + ".xml"))
    events = (
        [
            json.loads(line)
            for line in (folder / "events.jsonl").read_text().splitlines()
        ]
        if (folder / "events.jsonl").exists()
        else []
    )
    row["model_generation_status"] = (
        "OBSERVED"
        if any(
            e.get("item", {}).get("type")
            in ("agent_message", "command_execution", "file_change")
            for e in events
        )
        else "UNKNOWN"
    )
    row["provider_error_events"] = [
        e.get("type") for e in events if e.get("type") in ("error", "turn.failed")
    ]
    if row["provider_error_events"] and row["result"] == "FUNCTIONAL_FAILURE":
        row["raw_executor_result"] = row["result"]
        row["result"] = "UNKNOWN"
        row["reason"] = "provider/model error is not a known functional negative"
    observed = []
    for e in events:
        item = e.get("item", {})
        if (
            e.get("type") == "item.completed"
            and item.get("type") == "command_execution"
            and item.get("exit_code") == 0
            and bool(item.get("aggregated_output", "").strip())
        ):
            command = item.get("command", "")
            for mount in r["mounted_skills"]:
                skill = mount["skill_id"]
                body_path = mount["relative_path"]
                package_path = str(Path(body_path).parent) + "/"
                if re.search(r"(?:cat|sed|head|read_text|read_bytes)\b", command) and (
                    body_path in command or package_path in command
                ):
                    verified = False
                    if body_path in command:
                        try:
                            outer = shlex.split(command)
                            inner = (
                                shlex.split(outer[-1])
                                if len(outer) == 3 and outer[1] == "-lc"
                                else outer
                            )
                            skill_record = next(
                                x
                                for x in read(
                                    a.project
                                    / "configs/conditional-applicability-v1/registry.json"
                                )["skills"]
                                if x["id"] == skill
                            )
                            body = (
                                (
                                    a.project
                                    / "configs/conditional-applicability-v1"
                                    / skill_record["package_path"]
                                    / "SKILL.md"
                                )
                                .read_text()
                                .strip()
                            )
                            output_text = item["aggregated_output"].strip()
                            verified = (
                                inner[0] in ("cat", "sed", "head")
                                and inner[-1].endswith(body_path)
                                and not any(
                                    token in command
                                    for token in (";", "&&", "||", "`", "$", ">")
                                )
                                and len(output_text) >= 80
                                and output_text in body
                            )
                        except (ValueError, IndexError, StopIteration):
                            verified = False
                    observed.append(
                        {
                            "skill_id": skill,
                            "event_id": item.get("id"),
                            "command": command.replace(r["workspace"], "[workspace]"),
                            "kind": "body_read"
                            if verified
                            else "read_candidate_unknown",
                            "output_matches_frozen_body": verified,
                            "boundary": "standalone reader and output substring verified only when flagged; otherwise unknown; no causal attribution",
                        }
                    )
    reads.append(
        {
            "run_id": cell["run_id"],
            "recommended_ids": r["method"]["ranked_ids"],
            "exposed_ids": r["selected_ids"],
            "mounted_ids": [s["skill_id"] for s in r["mounted_skills"]],
            "observable_reads": observed,
            "usage_without_read_evidence": "UNKNOWN",
        }
    )
write(root / "runs.json", rows)
write(root / "skill-reads.json", reads)
q = []
for tid in protocol["qualification_sha256"]:
    q.append(
        {
            k: v
            for k, v in read(
                a.private / "qualification-1" / tid / "qualified.json"
            ).items()
            if k != "base_manifest"
        }
    )
    check_source = a.private / "tasks-v2" / tid / "trusted/test_behavior.py"
    if sha(check_source) != q[-1]["trusted_manifest"]["test_behavior.py"]["sha256"]:
        raise ValueError("trusted check changed after qualification: " + tid)
    (root / "checks-source").mkdir(exist_ok=True)
    shutil.copy2(check_source, root / "checks-source" / (tid + ".py.txt"))
write(root / "qualification.json", {"tasks": q})
review_path = root / "patch-review.json"
reviews = read(review_path).get("runs", {}) if review_path.exists() else {}
review_complete = all(
    r["result"] != "NOT_RUN" and reviews.get(r["run_id"], {}).get("status") == "PASS"
    for r in rows
)
write(
    root / "evidence-index.json",
    {
        "schema": "advisory-public-evidence-v1",
        "files": {
            str(f.relative_to(root)): sha(f)
            for f in sorted(root.rglob("*"))
            if f.is_file() and f.name not in ("evidence-index.json", "records.json")
        },
        "private_raw_traces": "retained locally; not published",
        "patch_review": "PASS" if review_complete else "REVIEW_REQUIRED",
    },
)
print(
    json.dumps(
        {
            "completed_records": sum(r["result"] != "NOT_RUN" for r in rows),
            "planned": 32,
        }
    )
)
