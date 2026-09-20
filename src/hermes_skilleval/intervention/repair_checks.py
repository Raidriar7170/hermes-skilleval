"""Small Pro adapter: full candidate reconstruction plus source test selectors."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import shutil
import re
import subprocess
import time
import xml.etree.ElementTree as ET

from .session import dump, inventory

IMAGE = "hermes-repair-knowledge-executor:v1"


def declared_api_absence(meta, errors, cases, rc):
    if rc not in (2, 4) or len(errors) != 1 or len(cases) != 1:
        return False
    signature = meta.get("required_api_absence")
    collector = meta.get("required_api_collector")
    if not signature or errors[0].get("name") != collector:
        return False
    diagnostics = [
        re.sub(r"^E\s+", "", line)
        for line in "".join(errors[0].itertext()).splitlines()
        if re.match(r"^E\s+", line)
    ]
    return len(diagnostics) == 1 and (
        diagnostics[0] == signature or diagnostics[0].startswith(signature + " (")
    )


def frozen_test_paths(patch):
    raw = subprocess.check_output(
        ["git", "apply", "--numstat", "-z", str(patch.resolve())]
    )
    names = []
    for line in raw.split(b"\0"):
        if not line:
            continue
        _, _, name = line.decode().split("\t", 2)
        path = Path(name)
        if (
            not path.parts
            or path.is_absolute()
            or ".." in path.parts
            or path.parts[0] != "test"
        ):
            raise ValueError("unsupported test patch path")
        names.append(name)
    if len(names) != len(set(names)) or not names:
        raise ValueError("invalid test patch path roster")
    return names


def install_test_overlay(candidate, overlay, output, *, expected_patch=None):
    """Install only frozen test-patch files; never follow candidate symlinks."""
    manifest = json.loads((overlay / "manifest.json").read_text())
    if expected_patch is not None:
        if (
            manifest["test_patch_sha256"]
            != hashlib.sha256(expected_patch.read_bytes()).hexdigest()
        ):
            raise ValueError("overlay belongs to a different test patch")
        if set(manifest["files"]) != set(frozen_test_paths(expected_patch)):
            raise ValueError("overlay path roster differs from frozen test patch")
    if inventory(overlay / "files") != manifest["files"]:
        raise ValueError("trusted overlay changed")
    before = inventory(candidate)
    changes = []
    for name, expected in manifest["files"].items():
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] != "test"
        ):
            raise ValueError("unsafe trusted test path")
        source = overlay / "files" / relative
        if source.is_symlink() or not source.is_file():
            raise ValueError("invalid trusted overlay source")
        if source.stat().st_mode & 0o777 != manifest["modes"][name]:
            raise ValueError("trusted overlay permissions changed")
        destination = candidate / relative
        for parent in relative.parents:
            if (candidate / parent).is_symlink():
                raise ValueError("candidate test parent is a symlink")
        if destination.is_symlink():
            destination.unlink()
        if destination.exists() and not destination.is_file():
            raise ValueError("candidate test path has incompatible type")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        changes.append({"path": name, "before": before.get(name), "after": expected})
    after = inventory(candidate)
    changed = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
    if not changed <= set(manifest["files"]):
        raise ValueError("test overlay modified undeclared candidate content")
    dump(
        output / "test-overlay.json",
        {
            "status": "POSTHOC_ACCEPTANCE_REVALIDATION",
            "files": changes,
            "outside_overlay_unchanged": True,
            "manifest_sha256": hashlib.sha256(
                (overlay / "manifest.json").read_bytes()
            ).hexdigest(),
        },
    )


def check_source(
    task, source, output, *, image=IMAGE, timeout=180, trusted_overlay=None
):
    from hermes_skilleval._maintenance.check import isolated

    task, source, output = map(Path, (task, source, output))
    if (output / "checks.json").exists():
        saved = json.loads((output / "checks.json").read_text())
        if set(saved) == {"target", "regression"}:
            return saved
        return {
            k: {"valid": False, "passed": False, "error": "interrupted checks"}
            for k in ("target", "regression")
        }
    output.mkdir(parents=True, exist_ok=False)
    meta = json.loads((task / "task.json").read_text())
    selectors = json.loads((task / "evaluation/selectors.json").read_text())
    selectors = {k: selectors[k] for k in ("target", "regression")}
    if any(not ids for ids in selectors.values()):
        raise ValueError("empty frozen selector set")
    # Keep full candidate immutable; apply trusted evaluation overlay to a copy.
    candidate = output / "evaluated"
    shutil.copytree(source, candidate, symlinks=True)
    overlay_error = None
    if trusted_overlay is not None:
        try:
            install_test_overlay(
                candidate,
                Path(trusted_overlay),
                output,
                expected_patch=task / "evaluation/test.patch",
            )
        except (ValueError, OSError) as exc:
            overlay_error = str(exc)
    else:
        patch = task / "evaluation/test.patch"
        applied = subprocess.run(
            ["git", "apply", str(patch.resolve())],
            cwd=candidate,
            capture_output=True,
            text=True,
        )
        (output / "overlay.stderr").write_text(applied.stderr)
        if applied.returncode:
            overlay_error = "hidden evaluation overlay does not apply"
    if overlay_error:
        result = {
            k: {
                "valid": False,
                "passed": False,
                "error": overlay_error,
            }
            for k in ("target", "regression")
        }
        dump(output / "checks.json", result)
        return result
    results = {}
    for kind, ids in selectors.items():
        out = output / kind
        out.mkdir()
        config = {"ids": ids}
        dump(out / "selectors.json", config)
        # Configuration only, not candidate-writable shell or evaluation code.
        harness = out / "run.py"
        harness.write_text("""import json, os, shutil, sys
shutil.copytree('/candidate','/tmp/repo',symlinks=True)
os.chdir('/tmp/repo')
os.environ['HOME']='/tmp'
os.environ['ANSIBLE_DEVEL_WARNING']='false'
sys.path[:0]=['/tmp/repo/lib','/tmp/repo/test/lib','/tmp/repo']
import pytest
class Capture:
 def pytest_collection_finish(self,session):
  json.dump([i.nodeid for i in session.items],open('/out/collected.json','w'))
ids=json.load(open('/out/selectors.json'))['ids']
raise SystemExit(pytest.main(['-q','-o','addopts=','-p','no:cacheprovider','--junitxml=/out/junit.xml',*ids],plugins=[Capture()]))
""")
        started = time.monotonic()
        try:
            rc, _ = isolated(
                image,
                [(candidate, "/candidate", "ro"), (out, "/out", "rw")],
                ["python", "/out/run.py"],
                out,
                "pytest",
                timeout=timeout,
            )
            junit = out / "junit.xml"
            cases = (
                list(ET.parse(junit).getroot().iter("testcase"))
                if junit.exists()
                else []
            )
            errors = [c for c in cases if c.find("error") is not None]
            skipped = [c for c in cases if c.find("skipped") is not None]
            failed = [c for c in cases if c.find("failure") is not None]
            collected_path = out / "collected.json"
            collected = (
                json.loads(collected_path.read_text())
                if collected_path.exists()
                else []
            )
            complete = sorted(collected) == sorted(ids) and len(cases) == len(ids)
            skip_ids = sorted(
                c.get("classname", "") + "::" + c.get("name", "") for c in skipped
            )
            allowed_skips = (
                sorted(meta.get("allowed_regression_skips", []))
                if kind == "regression"
                else []
            )
            valid = (
                rc in (0, 1)
                and complete
                and not errors
                and skip_ids == allowed_skips
                and len(cases) > len(skipped)
            )
            required_api_absence = kind == "target" and declared_api_absence(
                meta, errors, cases, rc
            )
            valid = valid or required_api_absence
            results[kind] = {
                "required_public_api_absent": required_api_absence,
                "valid": valid,
                "passed": valid and not failed and rc == 0,
                "returncode": rc,
                "cases": len(cases),
                "failures": len(failed),
                "errors": len(errors),
                "skipped": len(skipped),
                "skipped_ids": skip_ids,
                "preexisting_skips": allowed_skips,
                "seconds": time.monotonic() - started,
                "selectors": ids,
                "complete_expected_cases": complete,
            }
        except Exception as exc:
            results[kind] = {
                "valid": False,
                "passed": False,
                "error": str(exc),
                "seconds": time.monotonic() - started,
            }
        dump(output / "checks.json", results)
    return results


def accept_candidate(task, run, output, *, image=IMAGE, trusted_overlay=None):
    from hermes_skilleval.repo_routing.advisory_capture import (
        capture_complete,
        reconstruct,
    )

    task, run, output = map(Path, (task, run, output))
    if (output / "acceptance.json").exists():
        return json.loads((output / "acceptance.json").read_text())
    output.mkdir(parents=True, exist_ok=False)
    capture = capture_complete(task / "base", run / "source", output / "capture")
    reconstruct(
        task / "base",
        output / "capture/candidate.patch",
        output / "reconstructed",
        capture["after"],
    )
    checks = check_source(
        task,
        output / "reconstructed",
        output / "checks",
        image=image,
        trusted_overlay=trusted_overlay,
    )
    checks["policy"] = {
        "valid": True,
        "passed": all(
            p.startswith(("lib/", "test/", "docs/")) for p in capture["changed_files"]
        ),
    }
    result = {"capture": capture, "checks": checks, "integrity": "VERIFIED"}
    dump(output / "acceptance.json", result)
    return result
