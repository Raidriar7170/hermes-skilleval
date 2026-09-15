"""Public derivative consistency in the existing offline pytest CI."""

import json
from pathlib import Path

from hermes_skilleval.maintenance_records import recompute


def test_public_records_match_published_summary(tmp_path):
    root = Path(__file__).resolve().parents[1]
    index = root / "artifacts/repo-portability/records/index.json"
    expected = json.loads(index.with_name("summary.json").read_text())
    actual = recompute(index, tmp_path / "records")
    assert actual["summary"] == expected["summary"]
    assert actual["rows"] == expected["rows"]
