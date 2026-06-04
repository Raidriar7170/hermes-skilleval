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
EXTERNAL_SMOKE_PACK = ROOT / "docs" / "demo" / "external-repo-action-smoke-pack"
HOSTED_SMOKE_PACK = ROOT / "docs" / "demo" / "hosted-consumer-action-smoke"
README = ROOT / "README.md"
USAGE = ROOT / "docs" / "usage.md"
HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-reusable-github-action-rc.html"
)
EXTERNAL_SMOKE_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-external-repo-action-smoke-pack.html"
)
HOSTED_SMOKE_HUMAN_BRIEF = (
    ROOT / "docs" / "human-briefs" / "2026-06-04-hosted-consumer-action-smoke.html"
)
LOOP_REPORT = (
    ROOT
    / "docs"
    / "human-briefs"
    / "2026-06-04-autonomous-loop-reusable-github-action-rc.html"
)


def _copy_example_consumer_fixture(consumer: Path) -> None:
    shutil.copytree(EXAMPLE / "skills", consumer / "skills")
    shutil.copytree(EXAMPLE / "benchmark", consumer / "benchmark")


def _action_gate_run_script() -> str:
    action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    for step in action["runs"]["steps"]:
        if step.get("name") == "Run SkillEval gate":
            return step["run"]
    raise AssertionError("Run SkillEval gate step not found")


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
        for path in [
            README,
            USAGE,
            EXAMPLE / "README.md",
            EXTERNAL_SMOKE_PACK / "README.md",
            HOSTED_SMOKE_PACK / "README.md",
            HUMAN_BRIEF,
            EXTERNAL_SMOKE_HUMAN_BRIEF,
            HOSTED_SMOKE_HUMAN_BRIEF,
            LOOP_REPORT,
        ]
    )

    for phrase in [
        "Reusable GitHub Action RC",
        "External Repo Action Smoke Pack",
        "local external-consumer smoke",
        "Hosted Consumer Action Smoke",
        "GitHub-hosted consumer smoke run",
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


def test_github_action_external_consumer_shell_smoke(tmp_path):
    consumer = tmp_path / "consumer-repo"
    consumer.mkdir()
    _copy_example_consumer_fixture(consumer)

    output_dir = consumer / "skilleval-output"
    step_summary = consumer / "step-summary.md"
    smoke = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _action_gate_run_script()],
        cwd=consumer,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env={
            "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin",
            "PYTHONPATH": str(ROOT / "src"),
            "SKILLEVAL_SKILL_PATH": "skills",
            "SKILLEVAL_BENCHMARK_PATH": "benchmark",
            "SKILLEVAL_MIN_RECALL_AT_K": "1.0",
            "SKILLEVAL_MAX_NEGATIVE_HIT_RATE": "0.0",
            "SKILLEVAL_OUTPUT_DIR": "skilleval-output",
            "GITHUB_STEP_SUMMARY": str(step_summary),
        },
    )

    assert smoke.returncode == 0, smoke.stdout
    gate = json.loads((output_dir / "gate-report.json").read_text(encoding="utf-8"))
    summary = json.loads((output_dir / "ci-summary.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "gate-report.md").read_text(encoding="utf-8")
    ci_markdown = (output_dir / "ci-summary.md").read_text(encoding="utf-8")

    assert gate["decision"] == "ALLOW_MERGE"
    assert gate["metrics"]["recall_at_5"] == 1.0
    assert gate["metrics"]["negative_hit_rate"] == 0.0
    assert summary["decision"] == "ALLOW_MERGE"
    assert gate["report_paths"]["gate_report"] == "skilleval-output/gate-report.json"
    assert summary["gate_report"]["ci_markdown"] == "skilleval-output/ci-summary.md"
    assert "Decision: `ALLOW_MERGE`" in ci_markdown
    assert "Decision: `ALLOW_MERGE`" in step_summary.read_text(encoding="utf-8")
    assert "not a Marketplace Action release" in markdown
    assert "not hosted GitHub Actions proof" in markdown
    assert "not GitHub API PR comments" in markdown
    assert "not hosted GitHub Actions proof" in ci_markdown


def test_external_repo_action_smoke_pack_contains_committed_outputs():
    readme = (EXTERNAL_SMOKE_PACK / "README.md").read_text(encoding="utf-8")
    workflow = (
        EXTERNAL_SMOKE_PACK / ".github" / "workflows" / "skilleval.yml"
    ).read_text(encoding="utf-8")
    gate = json.loads(
        (EXTERNAL_SMOKE_PACK / "output" / "gate-report.json").read_text(
            encoding="utf-8"
        )
    )
    summary = json.loads(
        (EXTERNAL_SMOKE_PACK / "output" / "ci-summary.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (EXTERNAL_SMOKE_PACK / "output" / "gate-report.md").read_text(
        encoding="utf-8"
    )
    ci_markdown = (EXTERNAL_SMOKE_PACK / "output" / "ci-summary.md").read_text(
        encoding="utf-8"
    )

    assert "External Repo Action Smoke Pack" in readme
    assert "local external-consumer smoke" in readme
    assert "uses: Raidriar7170/hermes-skilleval@main" in workflow
    assert "skill-path: skills" in workflow
    assert "benchmark-path: benchmark" in workflow
    assert gate["decision"] == "ALLOW_MERGE"
    assert gate["metrics"]["recall_at_5"] == 1.0
    assert gate["metrics"]["negative_hit_rate"] == 0.0
    assert summary["decision"] == "ALLOW_MERGE"
    assert gate["report_paths"]["gate_report"] == "skilleval-output/gate-report.json"
    assert summary["gate_report"]["ci_markdown"] == "skilleval-output/ci-summary.md"
    assert "Decision: `ALLOW_MERGE`" in markdown
    assert "Decision: `ALLOW_MERGE`" in ci_markdown
    assert "not hosted GitHub Actions proof" in markdown
    assert "not hosted GitHub Actions proof" in ci_markdown

    combined = "\n".join([readme, workflow, markdown, ci_markdown])
    for phrase in [
        "not a Marketplace Action release",
        "not hosted GitHub Actions proof",
        "not GitHub API PR comments",
        "not PR annotations",
        "not SaaS",
        "not a runtime MCP router",
        "not production readiness",
        "not release approval",
        "not automatic merge approval",
        "not a v0.2.0 release",
    ]:
        assert phrase in combined

    for risky_claim in [
        "published to the GitHub Marketplace",
        "proves hosted GitHub Actions",
        "posts PR comments",
        "writes PR annotations",
        "production-ready",
        "approves the release",
        "@v0.2.0",
    ]:
        assert risky_claim not in combined


def test_hosted_consumer_action_smoke_pack_contains_committed_run_evidence():
    readme = (HOSTED_SMOKE_PACK / "README.md").read_text(encoding="utf-8")
    workflow = (HOSTED_SMOKE_PACK / "workflow.yml").read_text(encoding="utf-8")
    metadata = json.loads(
        (HOSTED_SMOKE_PACK / "run-metadata.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (HOSTED_SMOKE_PACK / "input-manifest.json").read_text(encoding="utf-8")
    )
    gate = json.loads(
        (HOSTED_SMOKE_PACK / "output" / "gate-report.json").read_text(
            encoding="utf-8"
        )
    )
    summary = json.loads(
        (HOSTED_SMOKE_PACK / "output" / "ci-summary.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (HOSTED_SMOKE_PACK / "output" / "gate-report.md").read_text(
        encoding="utf-8"
    )
    ci_markdown = (HOSTED_SMOKE_PACK / "output" / "ci-summary.md").read_text(
        encoding="utf-8"
    )
    results = (HOSTED_SMOKE_PACK / "output" / "results.jsonl").read_text(
        encoding="utf-8"
    )

    assert "Hosted Consumer Action Smoke" in readme
    assert "GitHub-hosted consumer smoke run" in readme
    assert metadata["consumer_repository"] == (
        "Raidriar7170/hermes-skilleval-action-consumer-smoke"
    )
    assert metadata["producer_action_ref"] == "Raidriar7170/hermes-skilleval@main"
    assert metadata["workflow_name"] == "SkillEval hosted consumer smoke"
    assert metadata["conclusion"] == "success"
    assert metadata["run_url"].startswith(
        "https://github.com/Raidriar7170/hermes-skilleval-action-consumer-smoke/actions/runs/"
    )
    assert metadata["head_sha"]
    assert "skilleval-action-artifacts" in metadata["artifact_names"]
    assert "skilleval hosted consumer smoke" in metadata["evidence_kind"]

    assert "workflow_dispatch:" in workflow
    assert "permissions:" in workflow
    assert "contents: read" in workflow
    assert "actions/setup-python@v5" in workflow
    assert "python-version: \"3.11\"" in workflow
    assert "Raidriar7170/hermes-skilleval@main" in workflow
    assert "skill-path: skills" in workflow
    assert "benchmark-path: benchmark" in workflow
    assert "output-dir: skilleval-output" in workflow
    assert "@v0.2.0" not in workflow
    assert "github-token" not in workflow.lower()

    assert manifest["fixture_source"] == "examples/github-action"
    assert sorted(manifest["skill_ids"]) == [
        "release-note-review",
        "workflow-evidence-audit",
    ]
    assert sorted(manifest["task_ids"]) == [
        "release-note-boundary",
        "workflow-evidence",
    ]
    assert manifest["file_hashes"]

    assert gate["decision"] == "ALLOW_MERGE"
    assert gate["metrics"]["recall_at_5"] == 1.0
    assert gate["metrics"]["negative_hit_rate"] == 0.0
    assert summary["decision"] == "ALLOW_MERGE"
    assert "Decision: `ALLOW_MERGE`" in markdown
    assert "Decision: `ALLOW_MERGE`" in ci_markdown
    assert "release-note-boundary" in results
    assert "workflow-evidence" in results

    combined = "\n".join([readme, workflow, markdown, ci_markdown])
    for phrase in [
        "not a Marketplace Action release",
        "not GitHub API PR comments",
        "not PR annotations",
        "not SaaS",
        "not a runtime MCP router",
        "not production readiness",
        "not release approval",
        "not automatic merge approval",
        "not a v0.2.0 release",
    ]:
        assert phrase in combined

    for forbidden in [
        "gho_",
        "github_pat_",
        "BEGIN OPENSSH",
        "x-access-token",
        "published to the GitHub Marketplace",
        "posts PR comments",
        "writes PR annotations",
        "production-ready",
        "approves the release",
        "@v0.2.0",
    ]:
        assert forbidden not in combined
