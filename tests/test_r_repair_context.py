from hermes_skilleval.repo_routing.context import FragmentBudget, extract_fragments


def test_large_tail_literal_and_hard_budget(tmp_path):
    source = (
        "# padding\n" * 16000
        + 'def delete_where(table):\n    """Commit deletions, but do not change unrelated rows."""\n    return table.commit()\n'
    )
    (tmp_path / "db.py").write_text(source)
    result = extract_fragments(tmp_path, "Fix db.py delete_where commits.", {})
    assert result["state"] == "usable"
    hit = result["matched_symbols"][0]
    assert hit["symbol"] == "delete_where"
    assert source.encode()[slice(*hit["bytes"])].decode() == hit["snippet"]
    assert "do not change" in hit["snippet"]
    limited = extract_fragments(
        tmp_path,
        "Fix db.py delete_where commits.",
        {},
        FragmentBudget(scan_file_bytes=1024),
    )
    assert limited["state"] == "partial"
    assert limited["source_hashes"]["db.py"]["full_file_sha256"] is None
    assert limited["source_hashes"]["db.py"]["unscanned_bytes"][0] == 1024


def test_missing_critical_and_source_never_executed(tmp_path):
    (tmp_path / "setup.py").write_text(
        "raise RuntimeError('never execute')\ndef reproduce():\n    pass\n"
    )
    result = extract_fragments(tmp_path, "Fix reproduce in missing.py", {})
    assert result["state"] == "unavailable"
    assert any(m["critical"] for m in result["missing"])


def test_no_cache_claim_for_unread_changes(tmp_path):
    path = tmp_path / "db.py"
    path.write_text("def apply():\n    pass\n")
    first = extract_fragments(tmp_path, "Fix apply.", {})
    path.write_text("def apply():\n    return 1\n")
    second = extract_fragments(tmp_path, "Fix apply.", {})
    assert first["snapshot_id"] != second["snapshot_id"]
    assert second["cost"]["cache_hit"] is False


def test_repair_native_fixed_and_old_gate_stay_lightweight(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from hermes_skilleval.repo_routing.policy import route
    from hermes_skilleval.repo_routing.reranker import Reranker

    def forbidden(*args, **kwargs):
        raise AssertionError("cheap branch constructed heavy reranker")

    monkeypatch.setattr(Reranker, "__init__", forbidden)
    (tmp_path / "code.py").write_text("def apply():\n    return 1\n")
    registry = json.loads(
        Path("configs/repo-portability/skills-v1/registry.json").read_text()
    )
    config = {"experimental_repair": "r-support-context-v1", "selection_mode": "C2"}
    for policy in ("native", "fixed"):
        result = route(tmp_path, "Fix apply.", {}, registry, policy, config)
        assert result["context"]["schema"] == "repo-context-v2"
        assert result["calls"] == {
            "heavy_constructors": 0,
            "encoder_queries": 0,
            "reranker_forwards": 0,
        }
    # Missing gate also remains cheap; no attempted support scoring is hidden.
    result = route(tmp_path, "Fix apply.", {}, registry, "auto", config)
    assert result["decision"]["fallback_reason"] == "gate_missing"
    assert result["calls"]["heavy_constructors"] == 0
