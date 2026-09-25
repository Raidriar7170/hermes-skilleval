import json
import hashlib
from pathlib import Path

P = Path(
    __import__("os").environ.get(
        "NATIVE_GAP_PRIVATE", "/tmp/hermes-native-gap-phase1-private"
    )
)
roster = json.loads((P / "roster.json").read_text())
results = []
chains = []
for selected in roster["trajectories"]:
    f = P / "raw-selected-trajectories" / (selected["trajectory_id"] + ".json")
    if not f.exists():
        continue
    wrapper = json.loads(f.read_text())["rows"][0]
    row = wrapper["row"]
    actions = []
    observations = []
    errors = []
    for index, msg in enumerate(row["trajectory"]):
        for call in msg.get("tool_calls") or []:
            fn = call.get("function", {})
            if fn.get("name") in ("think", "finish"):
                continue
            args = fn.get("arguments")
            try:
                args = json.loads(args) if isinstance(args, str) else args
            except ValueError:
                errors.append(index)
            actions.append(
                {
                    "index": index,
                    "name": fn.get("name"),
                    "arguments": args,
                    "id": call.get("id"),
                }
            )
        if msg.get("role") == "tool" and msg.get("name") not in ("think", "finish"):
            observations.append(
                {
                    "index": index,
                    "name": msg.get("name"),
                    "tool_call_id": msg.get("tool_call_id"),
                    "content": msg.get("content"),
                }
            )
    task = json.loads((P / "source-tasks" / (row["instance_id"] + ".json")).read_text())
    entry = {
        k: row.get(k)
        for k in [
            "trajectory_id",
            "instance_id",
            "repo",
            "exit_status",
            "resolved",
            "gen_tests_correct",
            "pred_passes_gen_tests",
        ]
    }
    entry.update(
        trajectory_parse="PARTIAL" if errors or wrapper["truncated_cells"] else "OK",
        tool_actions_observed=bool(actions),
        tool_observations_observed=bool(observations),
        model_patch_present=bool(row.get("model_patch")),
        author_resolved_label=row.get("resolved"),
        task_join="MATCHED",
        base_commit=task["base_commit"],
        image_mapping="RESOLVED" if task.get("docker_image") else "NOT_AVAILABLE",
        license={"dataset": "CC-BY-4.0", "repository": task["license_name"]},
        sample_role="EXPERIENCE_SOURCE_EXPLORATION",
        actions=len(actions),
        observations=len(observations),
        raw_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),
        patch_sha256=hashlib.sha256(
            (row.get("model_patch") or "").encode()
        ).hexdigest(),
    )
    results.append(entry)
    if (
        len(chains) < 3
        and entry["trajectory_parse"] == "OK"
        and row["instance_id"] not in [x["instance_id"] for x in chains]
    ):
        chain = {
            **entry,
            "problem_statement": task["problem_statement"],
            "actions": actions,
            "observations": observations,
            "candidate_patch": row.get("model_patch"),
        }
        chains.append(chain)
(P / "data-sample.jsonl").write_text("".join(json.dumps(x) + "\n" for x in results))
(P / "source-chains.json").write_text(json.dumps(chains, indent=2))
print(
    "rows",
    len(results),
    "issues",
    len({x["instance_id"] for x in results}),
    "chains",
    [(x["instance_id"], x["actions"][0]["name"]) for x in chains],
)
# Compact source-only model input; assistant prose/reasoning excluded by construction.
source = []
for x in chains:
    source.append(
        {
            k: x[k]
            for k in [
                "instance_id",
                "trajectory_id",
                "problem_statement",
                "author_resolved_label",
                "exit_status",
                "license",
            ]
        }
    )
    source[-1]["tool_actions"] = x["actions"]
    source[-1]["tool_observations"] = [
        {**o, "content": str(o["content"])[:2500]} for o in x["observations"]
    ]
(P / "skill-source-input.json").write_text(json.dumps(source, indent=2))
