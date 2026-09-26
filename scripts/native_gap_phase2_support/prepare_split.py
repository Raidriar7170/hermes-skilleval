"""Freeze metadata-only identities before fetching target answers or conversion."""

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

STUDY = "native-gap-phase2-same-library-v1"
ROOT = Path(__file__).resolve().parents[2]
OLD = Path("/tmp/hermes-native-gap-phase1-private")
PRIVATE = Path("/tmp/hermes-native-gap-phase2-private")
SEED = 20260926


def order(identity):
    return hashlib.sha256(f"{SEED}:{identity}".encode()).hexdigest()


def main():
    roster = json.loads((OLD / "roster.json").read_text())
    sources = roster["source_issues"]
    prior_answers = sorted(p.stem for p in (OLD / "trusted-targets").glob("*.json"))
    # Identity-only scan of existing research configs, no target patch contents.
    research_ids = set()
    for p in (ROOT / "configs").rglob("*"):
        if p.is_file() and "native-gap-phase" not in str(p):
            research_ids.update(
                re.findall(
                    r"(?:asottile__pyupgrade|encode__httpx)-\d+",
                    p.read_text(errors="replace"),
                )
            )
    excluded = set(sources) | set(prior_answers) | research_ids
    tasks = defaultdict(list)
    for p in sorted(OLD.glob("data_test*.metadata.json")):
        for i, row in enumerate(json.loads(p.read_text())):
            tasks[row["instance_id"]].append(
                dict(
                    row,
                    row=i,
                    file=p.name.replace(".metadata.json", "").replace(
                        "data_", "data/", 1
                    ),
                )
            )
    queue, library_sources = {}, []
    for repo in ["asottile/pyupgrade", "encode/httpx"]:
        eligible = [
            iid
            for iid, rows in tasks.items()
            if len(rows) == 1
            and rows[0]["repo"] == repo
            and rows[0]["docker_image"]
            and iid not in excluded
        ]
        queue[repo] = sorted(eligible, key=order)[:3]
        library_sources += sorted(
            [i for i in sources if roster["tasks"][i][0]["repo"] == repo], key=order
        )[:6]
    result = {
        "study": STUDY,
        "seed": SEED,
        "selection": "SHA256(seed:instance_id) ascending among unique task metadata rows with image mapping; no result or content-fit selection",
        "experience_source": sources,
        "library_source_candidates": library_sources,
        "preflight_dev": prior_answers,
        "pilot_task_candidates": queue,
        "excluded_prior_research_ids": sorted(research_ids),
        "prior_exposure": "Phase 1 scanned 67074 trajectory and 21336 task metadata rows; detailed answers read for source30 and dev4. Target answers not read before this identity freeze.",
        "near_duplicate_status": "PENDING_TRUSTED_SCREEN; no semantic non-leakage claim",
        "chronology": "STATIC_CROSS_ISSUE_TRANSFER; source repair availability time UNKNOWN",
        "library_target": 12,
        "library_max": 16,
        "source_issues_detailed": len(sources),
    }
    target = ROOT / "configs" / STUDY / "split.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert json.loads(target.read_text()) == result, (
            "Refuse changing frozen identities"
        )
    else:
        target.write_text(json.dumps(result, indent=2) + "\n")
    selected = [i for ids in queue.values() for i in ids]
    acquisition = {
        "source_issues": [],
        "target_candidates": selected,
        "tasks": {i: tasks[i] for i in selected},
    }
    PRIVATE.mkdir(exist_ok=True)
    (PRIVATE / "roster.json").write_text(json.dumps(acquisition, indent=2))
    (PRIVATE / "SWE-rebench-info.json").write_bytes(
        (OLD / "SWE-rebench-info.json").read_bytes()
    )
    print(
        json.dumps(
            {"target_queue": queue, "library_source_candidates": library_sources},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
