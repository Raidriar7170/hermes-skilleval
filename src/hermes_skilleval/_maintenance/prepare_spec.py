"""Prepare a controller task from a public, relative-path specification."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
from hermes_skilleval.repository_maintenance import capture
from hermes_skilleval.repository_profile import profile_for


def prepare(spec_path, upstream, output):
    spec_path = spec_path.resolve()
    spec = json.loads(spec_path.read_text())
    profile_for(spec)
    if not hasattr(tarfile, "data_filter"):
        raise ValueError("safe extraction requires Python 3.11.8+ or 3.12+")
    output.mkdir(parents=True, exist_ok=False)

    def git(*args):
        return subprocess.check_output(["git", "-C", str(upstream), *args])

    fix = git("rev-parse", spec["reference_fix_commit"] + "^{commit}").decode().strip()
    base = (
        git("rev-parse", spec.get("base_commit", fix + "^") + "^{commit}")
        .decode()
        .strip()
    )
    exclusions = spec.get("export_exclusions", [])
    for kind, rev in [("base", base), ("reference", fix)]:
        dest = output / kind
        dest.mkdir()
        with tarfile.open(fileobj=io.BytesIO(git("archive", rev))) as archive:
            archive.extractall(
                dest,
                members=[
                    m
                    for m in archive.getmembers()
                    if not any(
                        m.name == x.rstrip("/")
                        or m.name.startswith(x.rstrip("/") + "/")
                        for x in exclusions
                    )
                ],
                filter="data",
            )
    trusted = output / "trusted"
    trusted.mkdir()
    for dest, source in spec["trusted_files"].items():
        target = trusted / dest
        if Path(dest).is_absolute() or ".." in Path(dest).parts:
            raise ValueError("unsafe trusted file path")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.startswith("reference:"):
            target.write_bytes(git("show", fix + ":" + source.split(":", 1)[1]))
        else:
            target.write_bytes((spec_path.parent / source).read_bytes())
    (trusted / "pytest.ini").write_text("[pytest]\n")
    request = (spec_path.parent / spec["public_request"]).read_bytes()
    (output / "public.md").write_bytes(request)
    task = {
        **spec,
        "base_commit": base,
        "reference_fix_commit": fix,
        "public_request_sha256": hashlib.sha256(request).hexdigest(),
    }
    (output / "task.json").write_text(json.dumps(task, indent=2) + "\n")
    capture(output / "base", output / "reference", output / "reference-capture")
    return task


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for key in ["spec", "upstream", "output"]:
        p.add_argument("--" + key, type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.spec, a.upstream, a.output), indent=2))
