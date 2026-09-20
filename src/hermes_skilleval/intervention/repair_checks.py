"""Small Pro adapter: full candidate reconstruction plus source test selectors."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import re
import subprocess
import time
import xml.etree.ElementTree as ET

from .session import dump

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


def check_source(task, source, output, *, image=IMAGE, timeout=180):
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
    patch = task / "evaluation/test.patch"
    applied = subprocess.run(
        ["git", "apply", str(patch.resolve())],
        cwd=candidate,
        capture_output=True,
        text=True,
    )
    (output / "overlay.stderr").write_text(applied.stderr)
    if applied.returncode:
        result = {
            k: {
                "valid": False,
                "passed": False,
                "error": "hidden evaluation overlay does not apply",
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


def accept_candidate(task, run, output, *, image=IMAGE):
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
        task, output / "reconstructed", output / "checks", image=image
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
