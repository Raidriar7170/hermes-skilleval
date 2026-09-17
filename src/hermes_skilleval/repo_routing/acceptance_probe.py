"""Explicit candidate-only entry dispatch. No expected values or verdicts here."""

import sys

BOOTSTRAP = """import importlib.abc,importlib.machinery,sys,runpy
class Candidate(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in ('sqlite_utils','csvkit'):
   spec=importlib.machinery.PathFinder.find_spec(fullname,['/input'])
   if spec is None: raise ImportError(fullname)
   if not spec.origin.startswith('/input/'): raise ImportError('wrong source')
   return spec
sys.meta_path.insert(0,Candidate())
"""
BODIES = {
    "csv": "from csvkit.utilities.in2csv import launch_new_instance; launch_new_instance()",
    "package": "runpy.run_module('sqlite_utils',run_name='__main__')",
    "submodule": "runpy.run_module('sqlite_utils.cli',run_name='__main__')",
    "console": "from sqlite_utils.cli import cli; cli()",
}


def command(mode, args):
    body = BODIES[mode]
    return [
        "python",
        "-I",
        "-c",
        BOOTSTRAP + "\nsys.argv=" + repr([mode, *args]) + "\n" + body,
    ]


if __name__ == "__main__":
    exec(command(sys.argv[1], sys.argv[2:])[3])
