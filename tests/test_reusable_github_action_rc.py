import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from hermes_skilleval.cli import main


ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "action.yml"
EXAMPLE = ROOT / "examples" / "github-action"
EXAMPLE_WORKFLOW = EXAMPLE / ".github" / "workflows" / "skilleval.yml"
README = ROOT / "README.md"
USAGE = ROOT / "docs" / "usage.md"
HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-reusable-github-action-rc.html"
)
LOOP_REPORT = (
    ROOT
    / "docs"
    / "human-briefs"
    / "2026-06-04-autonomous-loop-reusable-github-action-rc.html"
)


def test_action_metadata_declares_composite_rc_inputs_and_safe_steps():
    action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))

    assert action["name"] == "Hermes SkillEval Reusable Action RC"
    assert action["runs"]["using"] == "composite"
    assert set(action["inputs"]) >= {
        "skill-path",
        "benchmark-path",
        "min-recall-at-k",
        "max-negative-hit-rate",
        "upload-artifacts",
    }
    assert action["inputs"]["skill-path"]["required"] is True
    assert action["inputs"]["benchmark-path"]["required"] is True
    assert action["inputs"]["upload-artifacts"]["default"] == "false"
    run_step = action["runs"]["steps"][1]
    assert run_step["env"] == {
        "SKILLEVAL_BENCHMARK_PATH": "${{ inputs.benchmark-path }}",
        "SKILLEVAL_MAX_NEGATIVE_HIT_RATE": "${{ inputs.max-negative-hit-rate }}",
        "SKILLEVAL_MIN_RECALL_AT_K": "${{ inputs.min-recall-at-k }}",
        "SKILLEVAL_OUTPUT_DIR": "${{ inputs.output-dir }}",
        "SKILLEVAL_SKILL_PATH": "${{ inputs.skill-path }}",
    }
    run_script = run_step["run"]

    action_text = ACTION.read_text(encoding="utf-8")
    for snippet in [
        "skilleval github-action-gate",
        "GITHUB_STEP_SUMMARY",
        "actions/upload-artifact@v4",
        "${{ inputs.upload-artifacts == 'true' }}",
        "set +e",
        "status=$?",
        'exit "$status"',
        '"$SKILLEVAL_SKILL_PATH"',
        '"$SKILLEVAL_OUTPUT_DIR"',
    ]:
        assert snippet in action_text
    assert '${{ inputs.skill-path }}' not in run_script
    assert '${{ inputs.benchmark-path }}' not in run_script
    assert '${{ inputs.output-dir }}' not in run_script
    assert "[dev]" not in action_text

    for forbidden in [
        "github-token",
        "pulls/comments",
        "issues/comments",
        "create-release",
        "gh release",
        "git tag",
        "v0.2.0",
        "mcp",
        "saas",
    ]:
        assert forbidden not in action_text.lower()


def test_github_action_example_contains_public_safe_external_fixture():
    assert EXAMPLE_WORKFLOW.is_file()
    workflow = EXAMPLE_WORKFLOW.read_text(encoding="utf-8")

    assert "Raidriar7170/hermes-skilleval@main" in workflow
    assert "skill-path: examples/github-action/skills" in workflow
    assert "benchmark-path: examples/github-action/benchmark" in workflow
    assert "upload-artifacts: 'true'" in workflow
    assert "@v0.2.0" not in workflow
    assert "github-token" not in workflow.lower()
    assert 'python -m pip install -e "."' in (EXAMPLE / "README.md").read_text(
        encoding="utf-8"
    )

    skill_ids = {path.parent.name for path in (EXAMPLE / "skills").rglob("SKILL.md")}
    assert skill_ids == {"release-note-review", "workflow-evidence-audit"}

    task_dirs = sorted((EXAMPLE / "benchmark").glob("*/"))
    assert len(task_dirs) == 2
    for task_dir in task_dirs:
        metadata = yaml.safe_load((task_dir / "task.yaml").read_text(encoding="utf-8"))
        assert set(metadata["gold_skills"]).issubset(skill_ids)
        assert set(metadata["negative_skills"]).issubset(skill_ids)
        assert (task_dir / "prompt.md").read_text(encoding="utf-8").strip()


def test_github_action_gate_writes_summary_artifacts_and_blocks_regressions(tmp_path):
    output_dir = tmp_path / "gate"

    assert (
        main(
            [
                "github-action-gate",
                "--skill-path",
                str(EXAMPLE / "skills"),
                "--benchmark-path",
                str(EXAMPLE / "benchmark"),
                "--min-recall-at-k",
                "1.0",
                "--max-negative-hit-rate",
                "0.0",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    gate = json.loads((output_dir / "gate-report.json").read_text(encoding="utf-8"))
    summary = json.loads((output_dir / "ci-summary.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "gate-report.md").read_text(encoding="utf-8")
    ci_markdown = (output_dir / "ci-summary.md").read_text(encoding="utf-8")

    assert gate["artifact_type"] == "github_action_gate"
    assert gate["decision"] == "ALLOW_MERGE"
    assert gate["metrics"]["recall_at_5"] == 1.0
    assert gate["metrics"]["negative_hit_rate"] == 0.0
    assert summary["decision"] == "ALLOW_MERGE"
    assert "Decision: `ALLOW_MERGE`" in ci_markdown
    assert "not a Marketplace Action release" in markdown
    assert "not GitHub API PR comments" in markdown

    blocked_benchmark = tmp_path / "blocked-benchmark"
    shutil.copytree(EXAMPLE / "benchmark", blocked_benchmark)
    blocked_task_path = blocked_benchmark / "release-note-boundary" / "task.yaml"
    blocked_task = yaml.safe_load(blocked_task_path.read_text(encoding="utf-8"))
    blocked_task["gold_skills"] = ["missing-skill"]
    blocked_task_path.write_text(yaml.safe_dump(blocked_task, sort_keys=False), encoding="utf-8")

    blocked_dir = tmp_path / "blocked"
    assert (
        main(
            [
                "github-action-gate",
                "--skill-path",
                str(EXAMPLE / "skills"),
                "--benchmark-path",
                str(blocked_benchmark),
                "--min-recall-at-k",
                "1.0",
                "--max-negative-hit-rate",
                "0.0",
                "--output-dir",
                str(blocked_dir),
            ]
        )
        == 2
    )
    blocked = json.loads((blocked_dir / "gate-report.json").read_text(encoding="utf-8"))
    assert blocked["decision"] == "BLOCK_MERGE"
    assert "recall_at_5 below threshold" in blocked["failed_policies"]

    negative_benchmark = tmp_path / "negative-benchmark"
    shutil.copytree(EXAMPLE / "benchmark", negative_benchmark)
    negative_task_path = negative_benchmark / "release-note-boundary" / "task.yaml"
    negative_task = yaml.safe_load(negative_task_path.read_text(encoding="utf-8"))
    negative_task["negative_skills"] = ["release-note-review"]
    negative_task_path.write_text(yaml.safe_dump(negative_task, sort_keys=False), encoding="utf-8")

    negative_dir = tmp_path / "negative-blocked"
    assert (
        main(
            [
                "github-action-gate",
                "--skill-path",
                str(EXAMPLE / "skills"),
                "--benchmark-path",
                str(negative_benchmark),
                "--min-recall-at-k",
                "0.0",
                "--max-negative-hit-rate",
                "0.0",
                "--output-dir",
                str(negative_dir),
            ]
        )
        == 2
    )
    negative_blocked = json.loads(
        (negative_dir / "gate-report.json").read_text(encoding="utf-8")
    )
    assert negative_blocked["decision"] == "BLOCK_MERGE"
    assert "negative_hit_rate above threshold" in negative_blocked["failed_policies"]

    invalid_dir = tmp_path / "invalid-threshold"
    assert (
        main(
            [
                "github-action-gate",
                "--skill-path",
                str(EXAMPLE / "skills"),
                "--benchmark-path",
                str(EXAMPLE / "benchmark"),
                "--min-recall-at-k",
                "1.0",
                "--max-negative-hit-rate",
                "2.0",
                "--output-dir",
                str(invalid_dir),
            ]
        )
        == 2
    )


def test_reusable_action_docs_and_briefs_are_bounded():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [README, USAGE, EXAMPLE / "README.md", HUMAN_BRIEF, LOOP_REPORT]
    )

    for phrase in [
        "Reusable GitHub Action RC",
        "skilleval github-action-gate",
        "not a Marketplace Action release",
        "not GitHub API PR comments",
        "not PR annotations",
        "not SaaS",
        "not a runtime MCP router",
        "not a SOTA claim",
        "not benchmark status",
        "not production readiness",
        "not release approval",
        "not automatic merge approval",
        "not a v0.2.0 release",
    ]:
        assert phrase in combined

    for risky_claim in [
        "uses: Raidriar7170/hermes-skilleval@v0.2.0",
        "published to the GitHub Marketplace",
        "posts PR comments",
        "writes PR annotations",
        "hosted SaaS dashboard",
        "runtime MCP router for agents",
        "production-ready",
        "approves the release",
    ]:
        assert risky_claim not in combined


def test_github_action_example_fresh_clone_smoke(tmp_path):
    clone = tmp_path / "fresh"
    ignore = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
    }
    shutil.copytree(ROOT, clone, ignore=shutil.ignore_patterns(*ignore))

    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        cwd=clone,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert install.returncode == 0, install.stdout

    output_dir = tmp_path / "fresh-output"
    smoke = subprocess.run(
        [
            sys.executable,
            "-m",
            "hermes_skilleval.cli",
            "github-action-gate",
            "--skill-path",
            "examples/github-action/skills",
            "--benchmark-path",
            "examples/github-action/benchmark",
            "--min-recall-at-k",
            "1.0",
            "--max-negative-hit-rate",
            "0.0",
            "--output-dir",
            str(output_dir),
        ],
        cwd=clone,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert smoke.returncode == 0, smoke.stdout
    assert (output_dir / "gate-report.json").is_file()
    assert (output_dir / "ci-summary.md").is_file()
