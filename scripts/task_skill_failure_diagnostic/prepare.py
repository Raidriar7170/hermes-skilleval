"""Materialize only registered qualified-source candidates; no model calls."""

import argparse
import ast
import io
import json
from pathlib import Path
import subprocess
import tarfile
from contracts import REQUESTS, EXTRACT, EXTRA, SQLITE_HEADER, SQLITE_REGRESSION
from hermes_skilleval.repository_profile import SQLITE_UTILS, CSVKIT
from hermes_skilleval.intervention.session import IMAGE


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def extract(repo, ref, file, names):
    text = git(repo, "show", ref + ":" + file).decode()
    lines = text.splitlines(keepends=True)
    parts = []
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            parts.append("".join(lines[start - 1 : node.end_lineno]))
    if len(parts) != len(names):
        raise ValueError("missing public test")
    return "\n\n".join(parts)


def main():
    p = argparse.ArgumentParser()
    for name in ["pool", "sqlite", "csvkit", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for row in json.loads(a.pool.read_text())["rows"]:
        if row["qualification"] == "SOURCE_EXCLUDED":
            continue
        short = row["fix_commit"][:7]
        repo = a.csvkit if row["repository"].endswith("csvkit") else a.sqlite
        task = a.output / row["task_id"]
        task.mkdir()
        for scope, ref in [
            ("base", row["base_commit"]),
            ("reference", row["fix_commit"]),
        ]:
            dest = task / scope
            dest.mkdir()
            with tarfile.open(fileobj=io.BytesIO(git(repo, "archive", ref))) as tar:
                tar.extractall(dest, filter="data")
        # Same base documentation remains available through the read-only skills
        # mount to every native/tail arm; no reference docs are exposed.
        sqlite = row["repository"].endswith("sqlite-utils")
        code = SQLITE_HEADER if sqlite else ""
        for file, names in EXTRACT.get(short, {}).items():
            code += "\n" + extract(repo, row["fix_commit"], file, names)
        code += "\n" + EXTRA.get(short, "")
        if sqlite:
            code += "\n" + SQLITE_REGRESSION
        trusted = task / "trusted"
        trusted.mkdir()
        (trusted / "pytest.ini").write_text("[pytest]\n")
        (trusted / "test_behavior.py").write_text(code + "\n")
        profile = (SQLITE_UTILS if sqlite else CSVKIT).to_dict()
        profile["image"] = IMAGE
        profile["file_policy"] = {
            "version": "operations-v1",
            "rules": [
                {
                    "path": r,
                    "operations": ["add", "modify", "delete"],
                    "max_bytes": 1000000,
                }
                for r in profile["writable_roots"]
            ],
        }
        meta = {
            **row,
            "profile": profile,
            "trusted_test_file": "test_behavior.py",
            "target_selector": "not test_regression",
            "regression_selector": "test_regression",
            "reference_commit": row["fix_commit"],
            "request_ref": row["source"],
        }
        (task / "task.json").write_text(json.dumps(meta, indent=2) + "\n")
        (task / "request.txt").write_text(REQUESTS[short] + "\n")
        rows.append(
            {
                **row,
                "request": REQUESTS[short],
                "source_tests": EXTRACT.get(short, {}),
                "acceptance_adaptation": "Source tests plus behavior-only boundary checks; no dedicated internal helper naming required. Full upstream suite not covered.",
            }
        )
    (a.output / "candidate-roster.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({"prepared": len(rows), "agent_calls": 0}))


if __name__ == "__main__":
    main()
