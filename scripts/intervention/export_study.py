"""Export compact review evidence, not full datasets, weights or Agent traces."""

from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
from hermes_skilleval.intervention.session import dump
from hermes_skilleval.intervention.study import read
from hermes_skilleval.intervention.evaluate import replay, summarize_rows
from hermes_skilleval.intervention.report import (
    collection_diagnostics,
    final_comparisons,
)
from hermes_skilleval.intervention.learning import model_identity

p = argparse.ArgumentParser()
for key in ("collection", "evaluation", "models", "tasks", "protocol", "output"):
    p.add_argument("--" + key, type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
protocol = read(a.protocol)
replay(a.collection)
replay(a.evaluation)
collection = read(a.collection)["rows"]
evaluation = read(a.evaluation)["rows"]
assert len(evaluation) == protocol["final_runs"]
assert len({r["task_id"] for r in evaluation}) == protocol["split_counts"]["test"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_rows(rows, group):
    public = []
    for row in rows:
        run = Path(row["run"])
        relative = Path(group) / row["task_id"]
        relative = relative / (
            row["method"] + "-r" + str(row["repeat"])
            if "method" in row
            else row["stage"] + "/r" + str(row["repeat"]) + "/" + row["action"]
        )
        dest = a.output / relative
        dest.mkdir(parents=True, exist_ok=True)
        source = run.parent / (run.name + "-checks")
        execution = row["execution"]
        small_execution = {
            k: execution.get(k)
            for k in (
                "status",
                "thread_id",
                "turns",
                "total_seconds",
                "initial_remaining",
                "tail_seconds",
                "prefix_seconds",
                "preparation_seconds",
                "model_input_observed",
                "injected",
                "payload_tokens",
            )
        }
        small_execution["decisions"] = [
            {k: v for k, v in d.items() if k != "state"}
            for d in execution.get("decisions", [])
        ]
        record = {
            k: row[k]
            for k in (
                "task_id",
                "split",
                "stage",
                "state_id",
                "candidates",
                "repeat",
                "action",
                "method",
                "quality",
                "utility",
                "payload_tokens",
                "gain_model_calls",
                "wait_model_calls",
            )
            if k in row
        }
        record.update(
            execution=small_execution,
            evidence_path=relative.as_posix(),
            checks={},
            artifact_sha256={},
        )
        if "state" in row:
            record["state_summary"] = {
                k: row["state"][k]
                for k in (
                    "stage",
                    "completed_turn_index",
                    "remaining_seconds",
                    "public_tests_run",
                    "public_test_exit",
                    "public_test_failure_seen",
                    "repeated_error_count",
                    "files_changed",
                    "observed_skill_reads",
                    "text_original_chars",
                    "text_retained_chars",
                )
            }
        if (source / "acceptance.json").exists():
            acceptance = read(source / "acceptance.json")
            if "capture" in acceptance:
                capture = acceptance["capture"]
                shutil.copyfile(
                    source / "capture/candidate.patch", dest / "candidate.patch"
                )
                record["patch_sha256"] = capture["patch_sha256"]
                record["changed_files"] = capture["changed_files"]
            for kind, check in row["checks"].items():
                record["checks"][kind] = {
                    k: check[k]
                    for k in ("valid", "passed", "cases", "returncode", "error")
                    if k in check
                }
                for name in ("junit.xml", "collected.json"):
                    original = source / kind / name
                    if original.exists():
                        exported = dest / (kind + "-" + name)
                        shutil.copyfile(original, exported)
            (dest / "checks.json").write_text(
                json.dumps(record["checks"], indent=2) + "\n"
            )
        else:
            record["checks"] = {
                k: {"valid": v.get("valid", False), "passed": v.get("passed", False)}
                for k, v in row["checks"].items()
            }
        if (run / "fork.json").exists():
            shutil.copyfile(run / "fork.json", dest / "fork.json")
        record["artifact_sha256"] = {
            file.name: sha(file) for file in dest.iterdir() if file.is_file()
        }
        public.append(record)
    return public


public_collection = export_rows(collection, "collection")
public_evaluation = export_rows(evaluation, "evaluation")
for kind, rows in [
    ("collection", public_collection),
    ("evaluation", public_evaluation),
]:
    dump(
        a.output / (kind + "-records.json"),
        {
            "format": "asi-public-v1",
            "protocol_sha256": sha(a.protocol),
            "rows": rows,
            "scope": "captured patch and verifier-record recomputation; fresh clean-base source verification requires private source evidence",
        },
    )
for row in protocol["tasks"]:
    trusted = a.tasks / row["task_id"] / "trusted"
    dest = a.output / "checks" / row["task_id"]
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(trusted, dest)
    dump(dest / "profile.json", read(a.tasks / row["task_id"] / "task.json")["profile"])
training = read(a.models / "training.json")
reload = read(a.models / "independent-reload.json")
dump(a.output / "training.json", training)
dump(a.output / "independent-reload.json", reload)
dump(
    a.output / "model-identities.json",
    {
        name: model_identity(a.models / name)
        for name in ("full", "no-state", "state-only")
    },
)
if (a.models / "development-diagnostics.json").exists():
    shutil.copyfile(
        a.models / "development-diagnostics.json",
        a.output / "development-diagnostics.json",
    )
summary = {
    "scope": "FROZEN_12_TRAIN_4_DEV_8_TEST_TWO_FINAL_REPEATS",
    "collection": collection_diagnostics(collection),
    "final": summarize_rows(evaluation),
    "paired_H_full_vs": final_comparisons(evaluation),
    "scheduled_final_runs": 96,
    "actual_final_runs": len(evaluation),
    "execution_statuses": dict(Counter(r["execution"]["status"] for r in evaluation)),
    "gain_model_calls": sum(r["gain_model_calls"] for r in evaluation),
    "wait_model_calls": sum(r["wait_model_calls"] for r in evaluation),
    "unknown_runs": sum(r["quality"] is None for r in evaluation),
    "api_total_tokens": None,
    "dollar_bill": None,
}
dump(a.output / "results.json", summary)
print(json.dumps(summary, indent=2))
