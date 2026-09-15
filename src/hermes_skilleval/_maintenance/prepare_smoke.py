"""Controller-only first public replay preparation; never mounted in task Agent."""

import argparse
import json
import subprocess
import tarfile
import io
import hashlib
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--upstream", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=False)


def git(*args):
    return subprocess.check_output(["git", "-C", str(a.upstream), *args])


fix = git("rev-parse", "c5063f6").decode().strip()
base = git("rev-parse", fix + "^").decode().strip()
for name, rev in [("base", base), ("reference", fix)]:
    d = a.output / name
    d.mkdir()
    tarfile.open(fileobj=io.BytesIO(git("archive", rev))).extractall(d, filter="data")
tests = a.output / "trusted"
tests.mkdir()
for name in ["conftest.py", "test_cli_convert.py"]:
    (tests / name).write_bytes(git("show", fix + ":tests/" + name))
(tests / "pytest.ini").write_text("[pytest]\n")
row = {
    "task_id": "sqlite-utils-829-dry-run",
    "source_kind": "public_issue_replay",
    "repository": "simonw/sqlite-utils",
    "issue_number": 829,
    "base_commit": base,
    "reference_fix_commit": fix,
    "family_id": "convert-dryrun-identifiers",
    "split": "dev",
    "target_selector": "test_convert_dryrun_table_and_column_names_containing_closing_bracket",
    "regression_selector": "not test_convert_dryrun_table_and_column_names_containing_closing_bracket",
    "trusted_test_file": "test_cli_convert.py",
    "base_manifest": {
        str(f.relative_to(a.output / "base")): hashlib.sha256(
            f.read_bytes()
        ).hexdigest()
        for f in sorted((a.output / "base").rglob("*"))
        if f.is_file()
    },
}
(a.output / "task.json").write_text(json.dumps(row, indent=2) + "\n")
