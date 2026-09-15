"""Trusted isolated bootstrap: candidate root never enters Python search path."""
import hashlib
import importlib.abc
import importlib.machinery
import json
import os
from pathlib import Path
import sqlite3
import sys
import pytest
import runpy

ROOT = Path('/input')
class CandidatePackage(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'sqlite_utils':
            return importlib.machinery.PathFinder.find_spec(fullname, [str(ROOT)])
        return None
sys.meta_path.insert(0, CandidatePackage())
# pytest may prepend only trusted test paths. Candidate top-level pytest.py,
# conftest.py, sitecustomize.py and user pytest config remain outside discovery.
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
import sqlite_utils
from sqlite_utils import cli
assert Path(sqlite_utils.__file__).resolve() == ROOT/'sqlite_utils/__init__.py'
assert Path(cli.__file__).resolve() == ROOT/'sqlite_utils/cli.py'
if sys.argv[1] == 'cli':
    sys.argv=['sqlite-utils',*sys.argv[2:]]
    runpy.run_path('/entrypoint',run_name='__main__')
else:
    identity={'python':sys.executable,'version':sys.version,'sqlite':sqlite3.sqlite_version,'source':sqlite_utils.__file__,'cli_source':cli.__file__,'cli':'trusted -I bootstrap -> sqlite_utils.cli:cli','candidate_root_on_sys_path':str(ROOT) in sys.path}
    Path('/out/identity.json').write_text(json.dumps(identity))
    args=['-c','/trusted/pytest.ini','--rootdir=/trusted','--confcutdir=/trusted','-p','no:cacheprovider','--import-mode=importlib','/trusted/'+sys.argv[2],'-k',sys.argv[3]]
    if sys.argv[1]=='collect':args+=['--collect-only','-q']
    else:args+=['--junitxml=/out/junit.xml','-q']
    class Collection:
        def pytest_collection_finish(self, session):
            ids=[]
            for item in session.items:
                parts=item.nodeid.split('::')
                ids.append(parts[0].replace('.py','').replace('/','.')+'::'+'::'.join(parts[1:]))
            Path('/out/collected.json').write_text(json.dumps(sorted(ids)))
    raise SystemExit(pytest.main(args,plugins=[Collection()] if sys.argv[1]=='collect' else []))
