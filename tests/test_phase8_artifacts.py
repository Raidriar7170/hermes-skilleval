from pathlib import Path
import re


PHASE8_DASHBOARD = Path("docs/demo/phase8-static-dashboard/dashboard.html")


def test_phase8_dashboard_artifact_is_committed_and_self_contained():
    html = PHASE8_DASHBOARD.read_text(encoding="utf-8")

    assert "Hermes SkillEval Dashboard" in html
    assert "cross-encoder-calibrated-strict-test" in html
    assert "cross-encoder-calibrated-balanced-test" in html
    assert "cross-encoder-rank-only-test" in html
    assert "gated-minilm-contrastive-test" in html
    disallowed_resource_patterns = (
        r"<script\b[^>]*\bsrc\s*=",
        r"<link\b[^>]*\bhref\s*=",
        r"<img\b[^>]*\bsrc\s*=",
        r"<a\b[^>]*\bhref\s*=",
        r"\burl\(",
        r"@import\b",
        r"\bfetch\(",
        r"\bXMLHttpRequest\b",
        r"https?://",
    )
    for pattern in disallowed_resource_patterns:
        assert re.search(pattern, html, flags=re.IGNORECASE) is None
