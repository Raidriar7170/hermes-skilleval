"""Continue the authorized frozen study after collection, without new sampling choices."""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from hermes_skilleval.intervention.session import dump

p = argparse.ArgumentParser()
for key in (
    "collection",
    "models",
    "evaluation",
    "protocol",
    "tasks",
    "payloads",
    "skills",
    "encoder",
    "status",
):
    p.add_argument("--" + key, type=Path, required=True)
p.add_argument("--collector-pid", type=int, required=True)
p.add_argument("--revalidated-collection", type=Path)
a = p.parse_args()


def status(stage):
    dump(a.status, {"stage": stage, "pid": os.getpid(), "time_unix": time.time()})
    print(stage, flush=True)


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], check=True)


try:
    status("WAITING_FOR_COMPLETE_FROZEN_COLLECTION")
    records = a.collection / "records.json"
    while not records.exists():
        try:
            os.kill(a.collector_pid, 0)
        except ProcessLookupError as exc:
            raise RuntimeError(
                "collector ended without complete records; no automatic resampling"
            ) from exc
        time.sleep(5)
    status("VERIFYING_COLLECTED_ARTIFACTS")
    run("-m", "hermes_skilleval.intervention.cli", "replay", "--records", records)
    if a.revalidated_collection:
        status("REVALIDATING_SAVED_PATCHES_WITH_VERSIONED_CHECKER")
        run(
            "scripts/intervention/revalidate_labels.py",
            "--collection",
            a.collection,
            "--protocol",
            a.protocol,
            "--tasks",
            a.tasks,
            "--output",
            a.revalidated_collection,
        )
        records = a.revalidated_collection / "records.json"
        run("-m", "hermes_skilleval.intervention.cli", "replay", "--records", records)
    status("TRAINING_REAL_PAIRED_VALUES")
    run(
        "-m",
        "hermes_skilleval.intervention.cli",
        "train",
        "--records",
        records,
        "--output",
        a.models,
        "--payloads",
        a.payloads,
        "--encoder",
        a.encoder,
    )
    status("INDEPENDENT_PROCESS_RELOAD")
    run("-m", "hermes_skilleval.intervention.cli", "reload", "--models", a.models)
    status("PREDECLARED_DEVELOPMENT_DIAGNOSTICS")
    run(
        "scripts/intervention/diagnose_development.py",
        "--records",
        records,
        "--models",
        a.models,
        "--payloads",
        a.payloads,
        "--encoder",
        a.encoder,
        "--output",
        a.models / "development-diagnostics.json",
    )
    status("FROZEN_96_RUN_COMPARISON")
    run(
        "-m",
        "hermes_skilleval.intervention.cli",
        "evaluate",
        "--protocol",
        a.protocol,
        "--tasks",
        a.tasks,
        "--output",
        a.evaluation,
        "--skills",
        a.skills,
        "--payloads",
        a.payloads,
        "--encoder",
        a.encoder,
        "--models",
        a.models,
    )
    status("VERIFYING_FINAL_ARTIFACTS")
    run(
        "-m",
        "hermes_skilleval.intervention.cli",
        "replay",
        "--records",
        a.evaluation / "records.json",
    )
    status("PLANNED_EXECUTIONS_COMPLETE_REVIEW_PENDING")
except BaseException as exc:
    dump(
        a.status,
        {
            "stage": "STOPPED_FOR_ENGINEERING_DIAGNOSIS",
            "error": str(exc),
            "pid": os.getpid(),
            "time_unix": time.time(),
        },
    )
    raise
