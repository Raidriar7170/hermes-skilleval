"""Trusted-side identity/patch screen; export exclusions, never target solutions."""

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
P = Path("/tmp/hermes-native-gap-phase2-private")
OLD = Path("/tmp/hermes-native-gap-phase1-private")
STUDY = "native-gap-phase2-same-library-v1"


def signature(d):
    # Ignore diff offsets/index hashes; retain filenames and changed text.
    lines = [
        x
        for x in d["patch"].splitlines()
        if x.startswith(("+", "-")) and not x.startswith(("+++", "---"))
    ]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def changed_tokens(d):
    return set(
        re.findall(
            r"[A-Za-z_][A-Za-z_0-9]*|[0-9]+",
            "\n".join(
                x
                for x in d["patch"].splitlines()
                if x.startswith(("+", "-")) and not x.startswith(("+++", "---"))
            ),
        )
    )


def main():
    split = json.loads((ROOT / "configs" / STUDY / "split.json").read_text())
    sources = [
        json.loads((OLD / "source-tasks" / f"{i}.json").read_text())
        for i in split["experience_source"]
    ]
    old = [
        json.loads((OLD / "trusted-targets" / f"{i}.json").read_text())
        for i in split["preflight_dev"]
    ]
    rows = []
    seen = []
    for ids in split["pilot_task_candidates"].values():
        for iid in ids:
            d = json.loads((P / "trusted-targets" / f"{iid}.json").read_text())
            reasons = []
            similarity = []
            for other in sources + old + seen:
                if d["repo"] != other["repo"]:
                    continue
                if d["base_commit"] == other["base_commit"]:
                    reasons.append(
                        {"other": other["instance_id"], "reason": "same_base"}
                    )
                if signature(d) == signature(other):
                    reasons.append(
                        {
                            "other": other["instance_id"],
                            "reason": "same_normalized_changed_text",
                        }
                    )
                a, b = changed_tokens(d), changed_tokens(other)
                jaccard = len(a & b) / len(a | b) if a | b else 0
                similarity.append(
                    {"other": other["instance_id"], "changed_token_jaccard": jaccard}
                )
                if jaccard >= 0.8:
                    reasons.append(
                        {
                            "other": other["instance_id"],
                            "reason": "near_duplicate_changed_token_jaccard_ge_0.8",
                        }
                    )
                for key in [
                    "merge_commit_sha",
                    "fix_commit",
                    "pull_number",
                    "pr_number",
                ]:
                    if d.get(key) is not None and d.get(key) == other.get(key):
                        reasons.append(
                            {"other": other["instance_id"], "reason": "same_" + key}
                        )
            rows.append(
                {
                    "instance_id": iid,
                    "excluded": bool(reasons),
                    "reasons": reasons,
                    "closest_changed_token_groups": sorted(
                        similarity, key=lambda x: -x["changed_token_jaccard"]
                    )[:3],
                    "base_commit": d["base_commit"],
                    "reference_patch_sha256": hashlib.sha256(
                        d["patch"].encode()
                    ).hexdigest(),
                    "normalized_change_sha256": signature(d),
                    "identity_fields_available": [
                        k for k in d if re.search("commit|pull|pr_number", k)
                    ],
                }
            )
            seen.append(d)
            public = {
                k: d[k]
                for k in ["instance_id", "repo", "base_commit", "problem_statement"]
            }
            public["language"] = "Python"
            out = P / "public-tasks" / f"{iid}.json"
            out.parent.mkdir(exist_ok=True)
            out.write_text(json.dumps(public, indent=2))
    report = {
        "rows": rows,
        "boundary": "Exact issue/base/fix, normalized changes and changed-token Jaccard >=0.8 grouping; not semantic non-leakage proof. Primary conversion contexts never receive target patches or tests.",
    }
    out = ROOT / "artifacts" / STUDY / "split-screen.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            [
                {
                    "instance_id": x["instance_id"],
                    "excluded": x["excluded"],
                    "reasons": x["reasons"],
                }
                for x in rows
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
