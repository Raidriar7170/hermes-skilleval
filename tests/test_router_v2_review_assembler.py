from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import hermes_skilleval.router_v2_review_assembler as review_assembler
from hermes_skilleval.router_v2_review_assembler import (
    ADJUDICATION_PROMPT_ID,
    MODEL_ID,
    MODEL_PROVIDER,
    MODEL_SNAPSHOT,
    REVIEW_PROMPT_ID,
    RUBRIC_ID,
    RUBRIC_PATH,
    assemble_adjudication_review,
    assemble_pass_review,
)
from hermes_skilleval.router_v2_training_pilot import with_row_sha256


ROOT = Path(__file__).parents[1]
CANDIDATES_PATH = ROOT / (
    "artifacts/router-v2-v4/internal-training-pilot/"
    "router-v2-v4-confusion-mined-pilot-001/candidates/round-1/candidates.jsonl"
)
SCRIPT_PATH = ROOT / "scripts/assemble_router_v2_review.py"
SUPPORTED = "HARD_NEGATIVE_ROLE_SUPPORTED"
DISPUTED = "HARD_NEGATIVE_ROLE_DISPUTED"
UNCERTAIN = "MODEL_UNCERTAIN"


def _candidate_rows() -> list[dict[str, Any]]:
    return [json.loads(line) for line in CANDIDATES_PATH.read_text().splitlines()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"".join(
            (
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode()
            for row in rows
        )
    )


def _decisions(
    *, opinion: str = SUPPORTED, rationale: str = "  Plausible confuser only.  "
) -> list[dict[str, str]]:
    return [
        {
            "candidate_id": row["candidate_id"],
            "model_opinion": opinion,
            "rationale": rationale,
        }
        for row in _candidate_rows()
    ]


def _adjudicator_decisions() -> list[dict[str, str]]:
    return [
        {
            "candidate_id": row["candidate_id"],
            "adjudicated_model_opinion": SUPPORTED,
            "rationale": "Bound resolution under the stable rubric.",
        }
        for row in _candidate_rows()
    ]


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = path.read_bytes()
    assert payload.endswith(b"\n")
    rows: list[dict[str, Any]] = []
    for line in payload.splitlines(keepends=True):
        row = json.loads(line)
        assert (
            line
            == (
                json.dumps(
                    row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                + "\n"
            ).encode()
        )
        rows.append(row)
    return rows


def _assemble_pass(
    tmp_path: Path,
    *,
    pass_id: str,
    run_id: str,
    decisions: list[dict[str, str]] | None = None,
) -> Path:
    decisions_path = tmp_path / f"{pass_id}.decisions.jsonl"
    _write_jsonl(decisions_path, decisions or _decisions())
    output = tmp_path / f"{pass_id}.model-opinions.jsonl"
    assemble_pass_review(
        repository_root=ROOT,
        pass_id=pass_id,
        pass_run_id=run_id,
        decisions_path=decisions_path,
        output_path=output,
    )
    return output


def test_pass_assembler_binds_exact_candidates_model_and_stable_rubric(
    tmp_path: Path,
) -> None:
    decisions = tmp_path / "pass-1.decisions.jsonl"
    _write_jsonl(decisions, _decisions())
    output = tmp_path / "pass-1.model-opinions.jsonl"

    result = assemble_pass_review(
        repository_root=ROOT,
        pass_id="MODEL_PASS_1",
        pass_run_id="isolated-pass-1-run",
        decisions_path=decisions,
        output_path=output,
    )

    candidates = _candidate_rows()
    rows = _load_rows(output)
    rubric = json.loads((ROOT / RUBRIC_PATH).read_text())
    assert result["candidate_count"] == len(rows) == len(candidates) == 59
    assert [row["candidate_id"] for row in rows] == [
        row["candidate_id"] for row in candidates
    ]
    assert [row["candidate_sha256"] for row in rows] == [
        row["candidate_sha256"] for row in candidates
    ]
    assert all(row["rationale"] == "Plausible confuser only." for row in rows)
    assert all(
        row["model_provider"] == MODEL_PROVIDER == "OpenAI"
        and row["model_id"] == MODEL_ID == "GPT-5"
        and row["model_snapshot"] == MODEL_SNAPSHOT == "UNAVAILABLE"
        and row["review_prompt_id"] == REVIEW_PROMPT_ID
        and row["rubric_id"] == RUBRIC_ID
        and row["pass_isolation"] == "OTHER_PASS_OUTPUT_NOT_PROVIDED"
        for row in rows
    )
    assert rubric["rubric_id"] == RUBRIC_ID
    assert rubric["review_prompt_id"] == REVIEW_PROMPT_ID
    assert rubric["adjudication_prompt_id"] == ADJUDICATION_PROMPT_ID
    assert rubric["pass_decision_fields"] == [
        "candidate_id",
        "model_opinion",
        "rationale",
    ]
    assert rubric["adjudication_decision_fields"] == [
        "candidate_id",
        "adjudicated_model_opinion",
        "rationale",
    ]
    assert "decision_fields" not in rubric
    assert not hasattr(review_assembler, "PASS_DECISION_FIELDS")
    assert not hasattr(review_assembler, "ADJUDICATION_DECISION_FIELDS")
    assert "strip" in rubric["review_prompt"].lower()
    assert "1..500" in rubric["review_prompt"]
    assert "strip" in rubric["adjudication_prompt"].lower()
    assert "1..500" in rubric["adjudication_prompt"]
    rubric_text = json.dumps(rubric, ensure_ascii=False).lower()
    for phrase in (
        "primary",
        "plausible confuser",
        "ambiguous",
        "multi-primary",
        "count",
        "held_out_eval_only",
        "human",
        "not a third review pass",
    ):
        assert phrase in rubric_text


def test_pass_assembler_rejects_coverage_order_decision_and_rationale_drift(
    tmp_path: Path,
) -> None:
    valid = _decisions()
    cases: list[tuple[list[dict[str, Any]], str]] = [
        (valid[:-1], "coverage"),
        ([*valid, deepcopy(valid[-1])], "coverage"),
        ([valid[1], valid[0], *valid[2:]], "order"),
        ([{**valid[0], "extra": True}, *valid[1:]], "exact fields"),
        ([{**valid[0], "model_opinion": "ACCEPT"}, *valid[1:]], "opinion"),
        ([{**valid[0], "rationale": "   "}, *valid[1:]], "rationale"),
        ([{**valid[0], "rationale": "x" * 501}, *valid[1:]], "rationale"),
        (
            [{**valid[0], "rationale": "This is human-reviewed."}, *valid[1:]],
            "forbidden claim",
        ),
    ]
    for index, (rows, message) in enumerate(cases):
        decisions = tmp_path / f"invalid-{index}.jsonl"
        _write_jsonl(decisions, rows)
        output = tmp_path / f"invalid-{index}.output.jsonl"
        with pytest.raises(ValueError, match=message):
            assemble_pass_review(
                repository_root=ROOT,
                pass_id="MODEL_PASS_1",
                pass_run_id="isolated-pass-1-run",
                decisions_path=decisions,
                output_path=output,
            )
        assert not output.exists()


def test_pass_assembler_cannot_receive_or_read_other_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert list(inspect.signature(assemble_pass_review).parameters) == [
        "repository_root",
        "pass_id",
        "pass_run_id",
        "decisions_path",
        "output_path",
    ]
    other_pass = tmp_path / "pass-2.model-opinions.jsonl"
    other_pass.write_text("forbidden")
    decisions = tmp_path / "pass-1.decisions.jsonl"
    _write_jsonl(decisions, _decisions())
    reads: list[Path] = []
    original_read_bytes = Path.read_bytes

    def observed_read(path: Path) -> bytes:
        reads.append(path.resolve(strict=False))
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", observed_read)
    assemble_pass_review(
        repository_root=ROOT,
        pass_id="MODEL_PASS_1",
        pass_run_id="isolated-pass-1-run",
        decisions_path=decisions,
        output_path=tmp_path / "pass-1.output.jsonl",
    )
    assert other_pass.resolve() not in reads
    allowed_reads = {
        CANDIDATES_PATH.resolve(),
        CANDIDATES_PATH.with_name("candidate-manifest.json").resolve(),
        (ROOT / RUBRIC_PATH).resolve(),
        decisions.resolve(),
    }
    assert set(reads) == allowed_reads


def test_adjudication_assembler_binds_both_passes_and_is_not_third_pass(
    tmp_path: Path,
) -> None:
    pass_1 = _assemble_pass(
        tmp_path, pass_id="MODEL_PASS_1", run_id="isolated-pass-1-run"
    )
    pass_2_decisions = _decisions()
    pass_2_decisions[0]["model_opinion"] = DISPUTED
    pass_2 = _assemble_pass(
        tmp_path,
        pass_id="MODEL_PASS_2",
        run_id="isolated-pass-2-run",
        decisions=pass_2_decisions,
    )
    adjudicator_decisions = _adjudicator_decisions()
    adjudicator_decisions[0]["adjudicated_model_opinion"] = UNCERTAIN
    decisions = tmp_path / "adjudicator.decisions.jsonl"
    _write_jsonl(decisions, adjudicator_decisions)
    output = tmp_path / "adjudication.model-opinions.jsonl"

    result = assemble_adjudication_review(
        repository_root=ROOT,
        pass_1_path=pass_1,
        pass_2_path=pass_2,
        decisions_path=decisions,
        output_path=output,
    )

    first_pass = _load_rows(pass_1)
    second_pass = _load_rows(pass_2)
    rows = _load_rows(output)
    assert result["candidate_count"] == len(rows) == 59
    assert rows[0]["pass_1_row_sha256"] == first_pass[0]["row_sha256"]
    assert rows[0]["pass_2_row_sha256"] == second_pass[0]["row_sha256"]
    assert rows[0]["pass_1_model_opinion"] == SUPPORTED
    assert rows[0]["pass_2_model_opinion"] == DISPUTED
    assert rows[0]["opinions_agree"] is False
    assert rows[0]["adjudicated_model_opinion"] == UNCERTAIN
    assert rows[0]["adjudicator_model_provider"] == "OpenAI"
    assert rows[0]["adjudicator_model_id"] == "GPT-5"
    assert rows[0]["adjudicator_model_snapshot"] == "UNAVAILABLE"
    assert rows[0]["adjudication_prompt_id"] == ADJUDICATION_PROMPT_ID
    assert rows[0]["model_review_pass_count"] == 2
    assert rows[0]["model_adjudication_enabled"] is True
    assert "pass_id" not in rows[0]

    drifted_pass = deepcopy(first_pass)
    drifted_pass[0]["candidate_sha256"] = "f" * 64
    drifted_pass[0] = with_row_sha256(drifted_pass[0])
    _write_jsonl(pass_1, drifted_pass)
    with pytest.raises(ValueError, match="candidate bundle"):
        assemble_adjudication_review(
            repository_root=ROOT,
            pass_1_path=pass_1,
            pass_2_path=pass_2,
            decisions_path=decisions,
            output_path=tmp_path / "drifted-adjudication.jsonl",
        )


def test_review_cli_has_bounded_subcommands_and_refuses_existing_or_partial_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    help_result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        text=True,
    )
    assert "assemble-pass" in help_result.stdout
    assert "assemble-adjudication" in help_result.stdout

    decisions = tmp_path / "pass.decisions.jsonl"
    _write_jsonl(decisions, _decisions())
    output = tmp_path / "existing.jsonl"
    output.write_text("keep")
    with pytest.raises(ValueError, match="must not exist"):
        assemble_pass_review(
            repository_root=ROOT,
            pass_id="MODEL_PASS_1",
            pass_run_id="isolated-pass-1-run",
            decisions_path=decisions,
            output_path=output,
        )
    assert output.read_text() == "keep"

    original_write_bytes = Path.write_bytes
    staged_writes = 0

    def fail_second_staged_file(path: Path, payload: bytes) -> int:
        nonlocal staged_writes
        if path.parent.name.startswith(".atomic-"):
            staged_writes += 1
            if staged_writes == 2:
                raise OSError("second staged output failure")
        return original_write_bytes(path, payload)

    monkeypatch.setattr(Path, "write_bytes", fail_second_staged_file)
    first_atomic = tmp_path / "atomic-first.jsonl"
    second_atomic = tmp_path / "atomic-second.jsonl"
    assemble_pass_review(
        repository_root=ROOT,
        pass_id="MODEL_PASS_1",
        pass_run_id="atomic-pass-1-run",
        decisions_path=decisions,
        output_path=first_atomic,
    )
    with pytest.raises(OSError, match="second staged output"):
        assemble_pass_review(
            repository_root=ROOT,
            pass_id="MODEL_PASS_2",
            pass_run_id="atomic-pass-2-run",
            decisions_path=decisions,
            output_path=second_atomic,
        )
    assert first_atomic.exists()
    assert not second_atomic.exists()
    assert list(tmp_path.glob(".atomic-second.jsonl.staging-*")) == []
