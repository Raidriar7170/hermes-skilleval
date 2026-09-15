"""Trusted isolated bootstrap: candidate root never enters Python search path."""

import importlib
import importlib.abc
import importlib.machinery
import json
import os
from pathlib import Path
import sqlite3
import sys
import pytest
import runpy

ROOT = Path("/input")
PROFILE = json.loads(Path("/profile.json").read_text())


class CandidatePackage(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in PROFILE["packages"]:
            spec = importlib.machinery.PathFinder.find_spec(
                fullname, [str(ROOT / PROFILE["packages"][fullname])]
            )
            if spec is None:
                raise ImportError("candidate package missing: " + fullname)
            return spec
        return None


sys.meta_path.insert(0, CandidatePackage())
# pytest may prepend only trusted test paths. Candidate top-level pytest.py,
# conftest.py, sitecustomize.py and user pytest config remain outside discovery.
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

package_sources = {}
for name, location in PROFILE["packages"].items():
    module = importlib.import_module(name)
    expected = (ROOT / location / name).resolve()
    origins = [Path(p).resolve() for p in module.__path__]
    assert origins == [expected], (name, origins, expected)
    package_sources[name] = str(expected)
cli = importlib.import_module(PROFILE["cli_module"])
assert cli.__file__ is not None
assert Path(cli.__file__).resolve().is_relative_to(ROOT)
if sys.argv[1] == "cli":
    sys.argv = [PROFILE["cli_name"], *sys.argv[2:]]
    runpy.run_path("/entrypoint", run_name="__main__")
else:
    identity = {
        "python": sys.executable,
        "version": sys.version,
        "sqlite": sqlite3.sqlite_version,
        "source": package_sources,
        "cli_source": cli.__file__,
        "cli": PROFILE["cli_module"] + ":" + PROFILE["cli_callable"],
        "candidate_root_on_sys_path": str(ROOT) in sys.path,
    }
    Path("/out/identity.json").write_text(json.dumps(identity))
    args = [
        "-c",
        "/trusted/pytest.ini",
        "--rootdir=/trusted",
        "--confcutdir=/trusted",
        "-p",
        "no:cacheprovider",
        "--import-mode=importlib",
        "/trusted/" + sys.argv[2],
        "-k",
        sys.argv[3],
    ]
    if sys.argv[1] == "collect":
        args += ["--collect-only", "-q"]
    else:
        args += ["--junitxml=/out/junit.xml", "-q"]

    class Collection:
        def pytest_collection_finish(self, session):
            ids = []
            for item in session.items:
                ids.append(runpy.run_path("/test_ids.py")["case_id"](item.nodeid))
            Path("/out/collected.json").write_text(json.dumps(sorted(ids)))

    raise SystemExit(
        pytest.main(args, plugins=[Collection()] if sys.argv[1] == "collect" else [])
    )
