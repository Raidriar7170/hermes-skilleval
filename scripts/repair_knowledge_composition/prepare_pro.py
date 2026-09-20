"""Qualification-only materialization. No hidden fields are passed to builders."""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request


def public_request(row):
    parts = []
    for key, title in (
        ("problem_statement", "problem"),
        ("requirements", "requirements"),
        ("interface", "interface"),
    ):
        text = row.get(key) or ""
        try:
            decoded = json.loads(text)
        except ValueError:
            decoded = text
        if isinstance(decoded, str):
            text = decoded
        parts.append("## Public " + title + "\n" + text)
    return "\n\n".join(parts) + "\n"


def materialize(row, full, output):
    tid = row["instance_id"]
    task = output / tid
    if (task / "prepared.json").exists():
        return tid
    task.mkdir(parents=True, exist_ok=True)
    archive = output / (row["base_commit"] + ".tar.gz")
    if not archive.exists():
        urllib.request.urlretrieve(
            f"https://codeload.github.com/{row['repo']}/tar.gz/{row['base_commit']}",
            archive,
        )
    base = task / "base"
    if not base.exists():
        base.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive.read_bytes())) as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts[1:]
                if not parts:
                    continue
                member.name = str(Path(*parts))
                tar.extract(member, base, filter="data")
    hidden = task / "evaluation"
    hidden.mkdir(exist_ok=True)
    record = full[tid]
    (hidden / "reference.patch").write_text(record["patch"])
    (hidden / "test.patch").write_text(record["test_patch"])
    for variant in ("reference",):
        target = task / variant
        if not target.exists():
            shutil.copytree(base, target, symlinks=True)
            subprocess.run(
                [
                    "git",
                    "apply",
                    str((hidden / "reference.patch").resolve()),
                ],
                cwd=target,
                check=True,
                capture_output=True,
            )
    # Raw source requirements are public inputs, not hidden answer material.
    (task / "request.txt").write_text(public_request(row))
    meta = {
        **row,
        "profile": {"packages": {"ansible": "lib"}},
        "fail_to_pass": ast.literal_eval(record["fail_to_pass"]),
        "pass_to_pass": ast.literal_eval(record["pass_to_pass"]),
        "selected_test_files_to_run": record["selected_test_files_to_run"],
    }
    (task / "task.json").write_text(json.dumps(meta, indent=2) + "\n")
    (task / "prepared.json").write_text(
        json.dumps(
            {
                "task_id": tid,
                "base": row["base_commit"],
                "source": "frozen Pro parquet",
                "agent_calls": 0,
            }
        )
        + "\n"
    )
    return tid


def main():
    import pyarrow.parquet as pq

    p = argparse.ArgumentParser()
    for key in ("pool", "parquet", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    rows = json.loads(a.pool.read_text())["rows"]
    full = {r["instance_id"]: r for r in pq.read_table(a.parquet).to_pylist()}
    a.output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as executor:
        for tid in executor.map(lambda row: materialize(row, full, a.output), rows):
            print("prepared", tid, flush=True)


if __name__ == "__main__":
    main()
