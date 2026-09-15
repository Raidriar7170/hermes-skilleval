"""Focused controller binding checks; integration probes are saved separately."""
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('repo_check',ROOT/'scripts/repo_workflow/check.py')
check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)

def test_test_path_escape_rejected(tmp_path):
    with pytest.raises(ValueError,match='filename'):
        check.check(tmp_path,tmp_path,tmp_path/'out','x',test_file='../untrusted.py')
