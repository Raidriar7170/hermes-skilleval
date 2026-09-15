"""Export fixed public revisions; controller-only history never enters execution."""

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path
from hermes_skilleval.repository_maintenance import capture
from hermes_skilleval.repository_profile import CSVKIT


def prepare(upstream, output, fix, public_request, test_source):
    if not hasattr(tarfile, "data_filter"):
        raise RuntimeError(
            "Python 3.11.8+ or 3.12+ is required for safe archive extraction"
        )
    output.mkdir(parents=True, exist_ok=False)

    def git(*args):
        return subprocess.check_output(["git", "-C", str(upstream), *args])

    fix = git("rev-parse", fix + "^{commit}").decode().strip()
    base = git("rev-parse", fix + "^").decode().strip()
    for name, rev in [("base", base), ("reference", fix)]:
        dest = output / name
        dest.mkdir()
        with tarfile.open(fileobj=io.BytesIO(git("archive", rev))) as archive:
            archive.extractall(
                dest,
                members=[
                    m
                    for m in archive.getmembers()
                    if not (
                        m.name == "examples/realdata"
                        or m.name.startswith("examples/realdata/")
                    )
                ],
                filter="data",
            )
    trusted = output / "trusted"
    trusted.mkdir()
    (trusted / "test_behavior.py").write_bytes(test_source.read_bytes())
    (trusted / "pytest.ini").write_text("[pytest]\n")
    (output / "public.md").write_bytes(public_request.read_bytes())
    task = {
        "task_id": "csvkit-1345-ndjson",
        "repository": "wireservice/csvkit",
        "source_url": "https://github.com/wireservice/csvkit/pull/1345",
        "export_exclusions": ["examples/realdata/"],
        "split": "dev",
        "family_id": "ndjson-extension-detection",
        "base_commit": base,
        "reference_fix_commit": fix,
        "profile": CSVKIT.to_dict(),
        "target_selector": "ndjson",
        "regression_selector": "existing_formats",
        "trusted_test_file": "test_behavior.py",
        "public_request_sha256": hashlib.sha256(
            public_request.read_bytes()
        ).hexdigest(),
    }
    (output / "task.json").write_text(json.dumps(task, indent=2) + "\n")
    capture(output / "base", output / "reference", output / "reference-capture")
    return task


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for key in ["upstream", "output", "public-request", "test-source"]:
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--fix", required=True)
    a = p.parse_args()
    print(
        json.dumps(
            prepare(a.upstream, a.output, a.fix, a.public_request, a.test_source),
            indent=2,
        )
    )
