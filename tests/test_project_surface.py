from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "validate.yml"
DASHBOARD_SCREENSHOT = ROOT / "docs" / "assets" / "dashboard-screenshot.png"
MIGRATION_PROTOCOL = ROOT / "docs" / "skill-library-migration-protocol.md"
EXPERIMENT_TIMELINE = ROOT / "docs" / "experiment-timeline.md"
USAGE = ROOT / "docs" / "usage.md"
RELEASE_NOTES = ROOT / "docs" / "release-notes" / "v0.1.0.md"


def test_ci_workflow_runs_lightweight_pytest_validation():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert 'python -m pip install -e ".[dev]"' in workflow
    assert "pytest -q" in workflow


def test_readme_surfaces_live_dashboard_and_screenshot_near_key_results():
    readme = README.read_text(encoding="utf-8")
    key_results = readme.index("## Key Results")
    architecture = readme.index("## Architecture")
    limitations = readme.index("## Limitations / Boundaries")
    live_dashboard = readme.index("### Live Dashboard")
    screenshot = readme.index("docs/assets/dashboard-screenshot.png")

    assert key_results < live_dashboard < architecture
    assert key_results < screenshot < architecture
    assert key_results < limitations < architecture
    assert "actions/workflows/validate.yml/badge.svg" in readme
    assert "run filtering" in readme
    assert "failure inspection" in readme
    assert "raw JSON audit" in readme
    assert "### Example Failure Caught by the Release Gate" in readme
    assert "blind-claude-mcp-routing" in readme
    assert "This is a self-built Hermes-style benchmark" in readme
    assert "docs/experiment-timeline.md" in readme


def test_dashboard_screenshot_asset_exists():
    assert DASHBOARD_SCREENSHOT.is_file()
    assert DASHBOARD_SCREENSHOT.stat().st_size > 20_000


def test_skill_library_migration_protocol_is_actionable():
    protocol = MIGRATION_PROTOCOL.read_text(encoding="utf-8")

    required_phrases = (
        "Superpowers skills",
        "Codex skills",
        "Claude Code style skills",
        "browser-use-vision / gui-agent-benchmark",
        "10-20",
        "task success",
        "tool adaptation",
        "instruction fidelity",
        "failure recoverability",
        "evidence completeness",
        "summary JSON",
        "failure taxonomy",
        "dashboard comparison",
    )
    for phrase in required_phrases:
        assert phrase in protocol


def test_experiment_timeline_keeps_phase_history_outside_readme():
    readme = README.read_text(encoding="utf-8")
    timeline = EXPERIMENT_TIMELINE.read_text(encoding="utf-8")

    assert "| Phase 18 | CI-backed release reproducibility pack |" not in readme
    assert "| Phase 18 | CI-backed release reproducibility pack |" in timeline
    assert "| Phase 2 | Router comparison baseline |" in timeline


def test_readme_keeps_quick_start_short_and_links_full_usage():
    readme = README.read_text(encoding="utf-8")
    usage = USAGE.read_text(encoding="utf-8")

    assert "For full CLI usage, see [`docs/usage.md`](docs/usage.md)." in readme
    assert "skilleval release-check" in readme
    assert "### 1. Index a Hermes-style Skill Library" not in readme
    assert "## 1. Index a Hermes-style Skill Library" in usage
    assert "## 17. Run Tests" in usage


def test_release_notes_are_reviewer_ready_and_conservative():
    notes = RELEASE_NOTES.read_text(encoding="utf-8")

    assert "# v0.1.0 - CI-backed Skill Routing Evaluation Harness" in notes
    assert "KEEP_BASELINE" in notes
    assert "baseline-minilm" in notes
    assert "SOTA" not in notes
