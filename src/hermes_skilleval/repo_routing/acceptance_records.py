"""Portable records adapter: Git omits empty directories, never evidence files.

The frozen execution checker remains unchanged. Recreate only unrepresented
empty output directories in a temporary copy, then use its original verifier.
"""

import argparse
import json
from pathlib import Path
import shutil
import tempfile

from . import acceptance_review as frozen


def records(legacy, config, output):
    frozen.verify_freeze(config)
    frozen.safe_files(output)
    index = frozen.read(output / "evidence-index.json")["files"]
    inventory = frozen.read(config / "inventory.json")
    missing = []
    for row in inventory["rows"]:
        if not row["affected"]:
            continue
        alias = row["alias"]
        if Path(alias).name != alias:
            raise ValueError("invalid frozen alias")
        keys = (
            (
                "csv_original_fixture_content",
                "csv_multisheet_content",
                "csv_file_input_regression",
                "csv_multisheet_file_regression",
            )
            if row["task_id"] == frozen.TASKS[0]
            else tuple(
                m + "_" + k
                for m in ("package", "submodule", "console")
                for k in ("help", "function")
            )
        )
        for key in keys:
            relative = f"{alias}/behavior/{key}/files"
            if not (output / relative).exists():
                if any(name.startswith(relative + "/") for name in index):
                    raise ValueError("missing indexed output files")
                missing.append(relative)
    if not missing:
        return frozen.records(legacy, config, output)
    with tempfile.TemporaryDirectory(prefix="hermes-acceptance-records-") as tmp:
        copy = Path(tmp) / "evidence"
        shutil.copytree(output, copy, symlinks=True)
        for relative in missing:
            (copy / relative).mkdir(parents=True, exist_ok=False)
        return frozen.records(legacy, config, copy)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("legacy", "config", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args(argv)
    print(json.dumps(records(a.legacy, a.config, a.output), indent=2))
