from pathlib import Path


PHASE8_DASHBOARD = Path("docs/demo/phase8-static-dashboard/dashboard.html")


def test_phase8_dashboard_artifact_is_committed_and_self_contained():
    html = PHASE8_DASHBOARD.read_text(encoding="utf-8")

    assert "Hermes SkillEval Dashboard" in html
    assert "cross-encoder-calibrated-strict-test" in html
    assert "cross-encoder-calibrated-balanced-test" in html
    assert "cross-encoder-rank-only-test" in html
    assert "gated-minilm-contrastive-test" in html
    assert "<script src=" not in html
    assert "<link rel=" not in html
    assert "https://" not in html
    assert "http://" not in html
