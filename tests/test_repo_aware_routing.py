"""Behavioral checks use fixtures; these are not algorithm-utility evidence."""

import itertools
import subprocess
import sys

import pytest

from hermes_skilleval.repo_routing.context import extract
from hermes_skilleval.repo_routing.gate import FEATURES, calibrate, decide, fit
from hermes_skilleval.repo_routing.policy import route
from hermes_skilleval.repo_routing.selector import Budget, objective, select


def test_context_dirty_bytes_and_cache(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    config = repo / "pyproject.toml"
    config.write_text('[project.scripts]\nexample="pkg.cli:main"\n')
    (repo / "api.py").write_text("def query(value):\n    return value\n")
    (repo / "reference").mkdir()
    (repo / "reference" / "answer.py").write_text("def hidden_gold(): pass\n")
    cache = tmp_path / "cache.json"
    first = extract(repo, "query CLI", {}, cache=cache)
    assert first["entrypoints"][0]["symbol"] == "pkg.cli:main"
    assert "reference/answer.py" not in first["source_hashes"]
    assert extract(repo, "query CLI", {}, cache=cache)["cost"]["cache_hit"]
    config.write_text('[project.scripts]\nexample="pkg.cli:other"\n')
    second = extract(repo, "query CLI", {}, cache=cache)
    assert not second["cost"]["cache_hit"]
    assert first["snapshot_id"] != second["snapshot_id"]
    assert second["entrypoints"][0]["symbol"] == "pkg.cli:other"


def candidate(name, relevance, support, tokens, compatible=True):
    return {
        "id": name,
        "relevance": relevance,
        "support": support,
        "tokens": tokens,
        "compatible": compatible,
        "support_state": "SUPPORTED_BY_TEXT",
    }


def test_optimizer_matches_independent_small_oracle():
    pool = [
        candidate("a", 0.8, [0.9, 0], 80),
        candidate("b", 0.7, [0, 0.8], 60),
        candidate("c", 0.6, [0.5, 0.5], 50),
    ]
    budget = Budget(tokens=120, max_k=2)
    actual = select(pool, [1, 1], budget)
    best = max(
        objective(s, [1, 1], budget)["score"]
        for n in range(3)
        for s in itertools.combinations(pool, n)
        if sum(v["tokens"] for v in s) <= 120
    )
    assert actual["objective"]["score"] == pytest.approx(best)
    assert actual["potential_load_tokens"] <= 120
    assert actual["skill_ids"] == ["b", "c"]


def test_optimizer_negative_conflict_unknown_and_ties():
    assert select([candidate("a", 0, [0], 10)], [1])["skill_ids"] == []
    assert select([candidate("a", 1, [1], 10, False)], [1])["skill_ids"] == []
    pool = [candidate("b", 1, [1], 10), candidate("a", 1, [1], 10)]
    assert select(pool, [1], Budget(max_k=1))["skill_ids"] == ["a"]
    pool[0]["support_state"] = "UNKNOWN"
    with pytest.raises(ValueError, match="unknown"):
        select(pool, [1])


def fixture_rows(split, families):
    return [
        {
            "split": split,
            "repair_family": f,
            "features": [1.0] * len(FEATURES),
            "action": a,
            "r_version": "r1",
            "source": "real_execution",
            "quality": 1,
            "seconds": 10.0,
            "tokens": 20.0,
        }
        for f in families
        for a in ("N", "F", "R")
    ]


def test_gate_degenerate_and_leakage():
    model = fit(fixture_rows("gate-fit", ["fit1", "fit2"]), "r1")
    assert model["gate_data_signal"] == "INSUFFICIENT"
    with pytest.raises(ValueError, match="leakage"):
        calibrate(fixture_rows("gate-calibration", ["fit1"]), model)
    model = calibrate(fixture_rows("gate-calibration", ["cal1"]), model)
    result = decide([1.0] * len(FEATURES), model, "r1")
    assert result["action"] == "N"
    assert result["fallback_reason"] == "gate_data_signal_insufficient"
    assert (
        decide([1.0] * len(FEATURES), model, "r2")["fallback_reason"]
        == "r_version_mismatch"
    )


def test_gate_unknown_not_failure():
    rows = fixture_rows("gate-fit", ["fit1", "fit2"])
    for r in rows:
        r["quality"] = None
        r["tokens"] = None
    model = fit(rows, "r1")
    assert all(
        v["quality_n"] == 0 and v["tokens"] is None for v in model["actions"].values()
    )


def test_auto_missing_assets_no_heavy_import(tmp_path):
    (tmp_path / "pkg.py").write_text("def example(): pass\n")
    registry = {"registry_id": "test", "skills": [{"id": "one"}]}
    result = route(tmp_path, "fix example", {}, registry, "auto", {})
    assert result["action"] == "N"
    assert not any(result["calls"].values())
    # Fresh process fails on any accidental import from the heavy stacks.
    code = """
import sys
class Guard:
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in ('torch','transformers','peft'):
            raise AssertionError('heavy import: '+fullname)
sys.meta_path.insert(0,Guard())
from pathlib import Path
from hermes_skilleval.repo_routing.policy import route
r=route(Path(sys.argv[1]),'fix example',{}, {'registry_id':'test','skills':[{'id':'one'}]},'auto',{})
assert not any(r['calls'].values())
"""
    subprocess.run([sys.executable, "-c", code, str(tmp_path)], check=True)


def test_current_assist_policy_preflight_missing_config(tmp_path):
    # Parser must expose the explicit policies without importing heavy dependencies.
    result = subprocess.run(
        [sys.executable, "-m", "hermes_skilleval.maintenance_cli", "assist", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert (
        result.returncode == 0
        and "--routing-config" in result.stdout
        and "repo-aware" in result.stdout
    )


def test_all_unknown_calibration_cannot_enable_r():
    rows = fixture_rows("gate-fit", ["a", "b"])
    for r in rows:
        r["quality"] = int(r["repair_family"] == "a")
    model = fit(rows, "r1")
    calibration = fixture_rows("gate-calibration", ["c"])
    for r in calibration:
        r["quality"] = None
    model = calibrate(calibration, model)
    assert not model["calibrated"]
    assert decide([1.0] * len(FEATURES), model, "r1")["action"] == "N"


def test_unknown_relevance_alone_does_not_select():
    row = candidate("x", 0.9, [0], 1)
    row["support_state"] = "UNKNOWN"
    assert select([row], [1])["skill_ids"] == []


def test_explicit_contradiction_preserves_negation():
    from hermes_skilleval.repo_routing.support import requirements, contradictions

    request = "Preserve duplicate rows. Do not modify stored data."
    assert len(requirements(request)) == 2
    assert contradictions(
        request, {"body": "Remove duplicates and overwrite the database."}, {}
    )
    for text in (
        "Never remove duplicates.",
        "This tool does not remove duplicates.",
        "You must not remove duplicates.",
    ):
        assert not contradictions(request, {"body": text}, {})


def test_r_version_changes_with_pool_budget_and_template():
    from hermes_skilleval.repo_routing.policy import routing_version

    config = {"budget": {"max_k": 2}}
    original = routing_version(config, {"registry_id": "one"})
    assert original != routing_version(config, {"registry_id": "two"})
    assert original != routing_version({"budget": {"max_k": 3}}, {"registry_id": "one"})


def test_context_prunes_dependency_tree_and_unknown_layout(tmp_path):
    from hermes_skilleval.repo_routing.context import ContextBudget

    dependencies = tmp_path / "node_modules"
    dependencies.mkdir()
    for i in range(20):
        (dependencies / str(i)).write_text("ignored")
    result = extract(tmp_path, "inspect", {}, ContextBudget(max_entries=3))
    assert result["entries_enumerated"] == 1
    assert not result["supported"]
