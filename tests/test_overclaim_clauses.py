from pathlib import Path

import pytest

from hermes_skilleval.release_checks import find_overclaim_matches, run_release_checks


@pytest.mark.parametrize(
    ("text", "status"),
    [
        ("这不是公开标准 benchmark、排行榜或 SOTA 证据。", None),
        ("This does not establish SOTA.", None),
        ("This is not a\nstandard external benchmark.", None),
        ('Negative disclaimers such as "does not establish SOTA".', None),
        ("This does not establish SOTA and this is production-ready.", "FAIL"),
        ("本项目已经达到 SOTA。", "FAIL"),
        ("这不是玩具项目，已经超过所有 SOTA 系统。", "FAIL"),
        ("This does not establish SOTA, but this is production-ready.", "FAIL"),
        ("This is not only SOTA but better.", "FAIL"),
        ("引用：“我们达到 SOTA”。", "REVIEW_REQUIRED"),
        ("难道这不是 SOTA？", "REVIEW_REQUIRED"),
        ("If this were production-ready.", "REVIEW_REQUIRED"),
        ("不能说不是 SOTA。", "REVIEW_REQUIRED"),
    ],
)
def test_claim_negation_is_local(tmp_path: Path, text, status):
    path = tmp_path / "README.md"
    path.write_text(text)
    matches = find_overclaim_matches([path])
    assert [m.status for m in matches] == ([status] if status else [])
    assert run_release_checks([path], [path])["status"] == (status or "PASS")
