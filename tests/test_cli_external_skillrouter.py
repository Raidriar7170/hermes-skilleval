import json
import shutil
from pathlib import Path

from hermes_skilleval.cli import main


FIXTURE = Path(__file__).parent / "fixtures" / "external" / "skillrouter_tiny"
EVAL_CORE_FIXTURE = (
    Path(__file__).parent / "fixtures" / "external" / "skillrouter_eval_core_tiny"
)


def test_cli_external_validate_writes_manifest_and_validation(tmp_path):
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "external-validate",
            "--benchmark",
            "skillrouter",
            "--data-root",
            str(FIXTURE),
            "--output-dir",
            str(output_dir),
            "--upstream-ref",
            "fixture-ref",
            "--license-note",
            "fixture-only",
            "--acquired-at",
            "2026-06-27",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    validation = json.loads(
        (output_dir / "validation.json").read_text(encoding="utf-8")
    )
    assert manifest["upstream_ref"] == "fixture-ref"
    assert manifest["validation_status"] == "PASS"
    assert validation["status"] == "PASS"
    assert validation["task_count"] == 2


def test_cli_external_validate_accepts_official_eval_core_fixture(tmp_path):
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "external-validate",
            "--benchmark",
            "skillrouter",
            "--data-root",
            str(EVAL_CORE_FIXTURE),
            "--output-dir",
            str(output_dir),
            "--upstream-ref",
            "fixture-ref",
            "--license-note",
            "fixture-only",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    validation = json.loads(
        (output_dir / "validation.json").read_text(encoding="utf-8")
    )
    assert validation["status"] == "PASS"
    assert validation["task_count"] == 3
    assert {record["path"] for record in manifest["files"]} == {
        "tasks.jsonl",
        "relevance.json",
        "manifest.json",
        "easy/shard-000.jsonl.gz",
        "hard/shard-000.jsonl.gz",
    }


def test_cli_external_validate_invalid_data_returns_error_without_traceback(
    tmp_path,
    capsys,
):
    root = tmp_path / "broken"
    shutil.copytree(FIXTURE, root)
    (root / "tasks.jsonl").write_text(
        '{"id":"broken","query":" ","tier":"easy","task_type":"single"}\n',
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    exit_code = main(
        [
            "external-validate",
            "--benchmark",
            "skillrouter",
            "--data-root",
            str(root),
            "--output-dir",
            str(output_dir),
            "--upstream-ref",
            "fixture-ref",
            "--license-note",
            "fixture-only",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "external validation failed" in captured.err
    assert "Traceback" not in captured.err
    validation = json.loads(
        (output_dir / "validation.json").read_text(encoding="utf-8")
    )
    assert validation["status"] == "INVALID"
