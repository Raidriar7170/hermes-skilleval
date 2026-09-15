"""Focused controller binding checks; integration probes are saved separately."""

import pytest

from hermes_skilleval._maintenance import check


def test_test_path_escape_rejected(tmp_path):
    with pytest.raises(ValueError, match="filename"):
        check.check(
            tmp_path, tmp_path, tmp_path / "out", "x", test_file="../untrusted.py"
        )
