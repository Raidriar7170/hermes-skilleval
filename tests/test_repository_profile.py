import subprocess
import os
from pathlib import Path
import hermes_skilleval
import sys
import pytest
from hermes_skilleval.repository_profile import RepositoryProfile, CSVKIT
from hermes_skilleval.fixed_baseline import fixed_ids


def test_fixed_has_no_request_input_and_is_stable():
    config = {"repositories": {"repo": ["b", "a"]}}
    registry = {"skills": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
    for request in ["issue-one", "completely different task", "target-label"]:
        assert fixed_ids("repo", config, registry) == ["a", "b"]


def test_fixed_rejects_missing_duplicate_or_wrong_k():
    for ids in [["a", "a"], ["a"], ["a", "missing"]]:
        with pytest.raises(ValueError):
            fixed_ids(
                "repo", {"repositories": {"repo": ids}}, {"skills": [{"id": "a"}]}
            )


def test_profile_prevents_escaping_import_and_cli():
    for change in [
        {"packages": {"csvkit": "../escape"}},
        {"cli_name": "in2csv; id"},
        {"cli_module": "os"},
    ]:
        with pytest.raises(ValueError):
            RepositoryProfile(**{**CSVKIT.to_dict(), **change})


def test_fixed_and_profiles_do_not_import_models():
    code = """import sys
from hermes_skilleval.fixed_baseline import fixed_ids
from hermes_skilleval.repository_profile import CSVKIT
fixed_ids('repo', {'repositories':{'repo':['a','b']}}, {'skills':[{'id':'a'},{'id':'b'}]})
assert not any(n in sys.modules for n in ['torch','transformers','sentence_transformers'])
"""
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(hermes_skilleval.__file__).parent.parent),
    }
    subprocess.run([sys.executable, "-c", code], check=True, env=env)
