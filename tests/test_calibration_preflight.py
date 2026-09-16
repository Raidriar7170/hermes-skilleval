import pytest

from hermes_skilleval.repo_routing.applicability_data import read_json, read_rows
from hermes_skilleval.repo_routing.calibration_preflight import (
    structural,
    feasibility,
    report,
    eligibility,
    extract_repaired,
)
from hermes_skilleval.repo_routing.context import FragmentBudget
from hermes_skilleval.repo_routing.decision_cli import DEFAULT, REGISTRY, RULE


def data():
    tasks = [t for t in read_json(DEFAULT / "tasks.json") if t["split"] == "cal"]
    skills = read_json(REGISTRY)["skills"]
    labels = [r for r in read_rows(DEFAULT / "labels.jsonl") if r["split"] == "cal"]
    return tasks, skills, labels, read_json(RULE)


def test_real_two_group_upper_bound_without_scores(monkeypatch):
    from hermes_skilleval.repo_routing import reranker

    monkeypatch.setattr(
        reranker, "Reranker", lambda *a, **k: pytest.fail("constructed model")
    )
    tasks, skills, labels, rule = data()
    result = report(tasks, skills, rule, labels=labels)
    c = result["calibration"]
    assert c["context_known_group_upper_bound"] == 2
    assert c["status"] == "BLOCKED"
    assert c["axes"]["0"]["necessary_conditions_met"]
    assert c["axes"]["1"]["classes"] == {"0": 8, "1": 2}
    assert not c["axes"]["1"]["required"]
    assert result["scorer_calls"] == result["model_constructions"] == 0


def test_groups_not_rows_and_structural_not_precision():
    tasks, skills, labels, rule = data()
    for t in tasks:
        t["context"]["state"] = "usable"
        t["context"]["missing"] = []
    tokens = {r["row_id"]: {"visible": True} for r in labels}
    public = structural(tasks, skills, tokens=tokens, environment_known=True)
    c = feasibility(public, labels, rule)
    assert c["status"] == "NECESSARY_CONDITIONS_MET"
    assert c["supported_operating_point"] == "NOT_ESTABLISHED"
    assert not c["axes"]["1"]["necessary_conditions_met"]
    assert (
        feasibility(public, labels, rule, required_axes=(0, 1))["status"] == "BLOCKED"
    )
    for r in public:
        r["repair_group_id"] = "one"
    for r in labels:
        r["repair_group_id"] = "one"
    c = feasibility(public, labels, rule)
    assert c["eligible_known_rows"] >= 6 and c["status"] == "BLOCKED"


def test_shared_eligibility_unknown_tokens_and_environment():
    for state in ("usable", "partial", "unavailable"):
        tasks, skills, _, _ = data()
        tasks = tasks[:1]
        tasks[0]["context"]["state"] = state
        rows = structural(tasks, skills[:1])
        expected = eligibility(
            context_state=state, token_visible=None, environment_known=False
        )
        assert rows[0]["eligible"] == expected["eligible"]
        assert "TOKENIZATION_UNCHECKED" in rows[0]["reasons"]


def test_prose_repair_preserves_genuine_calls_and_budget(tmp_path):
    (tmp_path / "module.py").write_text('def display():\n    return "lines"\n')
    for text in (
        "display new lines, or (the easier way) escape them",
        "display should raise a warning (maybe allowing a choice)",
    ):
        result = extract_repaired(tmp_path, text, {"network": "disabled"})
        assert result["state"] == "usable"
        assert len(result["prose_call_corrections"]) == 1
    for text in (
        "display and missing_call()",
        "display and warning (value)",
        "display and `warning (maybe allowing)`",
    ):
        result = extract_repaired(tmp_path, text, {})
        assert result["state"] != "usable"
    result = extract_repaired(tmp_path, "display and missing.py", {})
    assert result["state"] == "unavailable"
    result = extract_repaired(
        tmp_path, "display", {}, FragmentBudget(scan_file_bytes=8)
    )
    assert result["state"] != "usable"


def test_escape_symlink_unauthorized_still_rejected(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    outside = tmp_path / "secret.py"
    outside.write_text("def secret():\n    pass\n")
    (root / "link.py").symlink_to(outside)
    for text in ("read ../secret.py and secret()", "read link.py and secret()"):
        result = extract_repaired(root, text, {})
        assert result["state"] == "unavailable"
    tasks, skills, _, _ = data()
    tasks[0]["context"]["matched_symbols"][0]["path"] = "../secret.py"
    assert "UNAUTHORIZED_PATH" in structural(tasks[:1], skills[:1])[0]["reasons"]


def test_structure_never_reads_scores_or_hidden_labels():
    tasks, skills, _, _ = data()
    before = structural(tasks, skills)
    for t in tasks:
        t["probability"] = 0.999
        t["reference_patch"] = "hidden"
        t["label"] = "APPLICABLE"
    assert structural(tasks, skills) == before


def test_advisory_not_blocked_by_support_environment():
    tasks, skills, labels, rule = data()
    tokens = {r["row_id"]: {"visible": True} for r in labels}
    result = report(tasks, skills, rule, tokens=tokens, requested_operation="advisory")
    assert result["status"] == "NECESSARY_CONDITIONS_MET"
    assert all(not r["eligible"] for r in result["rows"])


def test_snapshot_validation_precedes_read(tmp_path):
    from hermes_skilleval.repo_routing.calibration_preflight import safe_snapshot_path

    (tmp_path / "link").symlink_to(tmp_path.parent)
    for rel in ("../private", "/tmp/private", "link/private", "trusted/test.py"):
        with pytest.raises(ValueError, match="UNAUTHORIZED"):
            safe_snapshot_path(tmp_path, rel)


def test_training_preflight_uses_actual_config_sources(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from hermes_skilleval.repo_routing import decision_cli

    tasks, skills, _, _ = data()
    tasks[0]["split"] = "fit"
    tasks[1]["split"] = "model-dev"
    for name, obj in [("tasks.json", tasks), ("registry.json", {"skills": skills})]:
        (tmp_path / name).write_text(json.dumps(obj))
    (tmp_path / "labels.jsonl").write_text("")
    config = {
        "tasks": str(tmp_path / "tasks.json"),
        "registry": str(tmp_path / "registry.json"),
        "labels": str(tmp_path / "labels.jsonl"),
    }
    (tmp_path / "config.json").write_text(json.dumps(config))
    monkeypatch.setattr(
        decision_cli,
        "tokenize",
        lambda *a, **kw: pytest.fail("tokenizer before fit validation"),
    )
    args = SimpleNamespace(
        operation="train-structure",
        command="aligned-train",
        config=tmp_path / "config.json",
        snapshots=None,
    )
    with pytest.raises(ValueError, match="training label"):
        decision_cli.run_preflight(args)


def test_installed_style_cli_blocks_before_tokenizer_or_model(tmp_path, monkeypatch):
    from hermes_skilleval.repo_routing import decision_cli, reranker

    selected = decision_cli.selection(DEFAULT)
    import json

    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps(selected["targets"]["applicability"]["contract"]))
    monkeypatch.setattr(
        decision_cli,
        "tokenize",
        lambda *a, **kw: pytest.fail(
            "tokenizer for structurally impossible calibration"
        ),
    )
    monkeypatch.setattr(
        reranker, "Reranker", lambda *a, **kw: pytest.fail("heavy constructor")
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "hermes-applicability",
            "aligned-score",
            "--config",
            str(tmp_path / "does-not-exist.json"),
            "--contract",
            str(contract),
            "--split",
            "cal",
            "--output",
            str(tmp_path / "report.json"),
        ],
    )
    with pytest.raises(SystemExit) as e:
        decision_cli.main()
    assert e.value.code == 2
    assert read_json(tmp_path / "report.json")["model_constructions"] == 0


@pytest.mark.parametrize(
    "code",
    [
        "`warning (maybe + value)`",
        "``warning (maybe + `value`)``",
        "```python\nwarning (maybe + value)\n```",
        "~~~~python\r\nwarning (maybe + value)\r\n~~~~",
        "    warning (maybe + value)",
        "\twarning (maybe + value)",
        "warning(value)",
        "warning (value)",
        "`warning (maybe + value)",
        "```\nwarning (maybe + value)",
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_same_name_full_chain(tmp_path, code, reverse):
    from hermes_skilleval.repo_routing.context import extract_fragments

    (tmp_path / "module.py").write_text('def display():\n    return "lines"\n')
    parts = [
        "检查 display 的错误提示：\r\ndisplay should raise a warning (maybe allowing a choice).",
        code,
    ]
    request = "\r\n".join(reversed(parts) if reverse else parts)
    original = extract_fragments(tmp_path, request, {})
    result = extract_repaired(tmp_path, request, {})
    missing = {
        "path": ".",
        "symbol": "warning",
        "reason": "explicit_call_unlocated",
        "critical": True,
    }
    assert missing in original["missing"]
    assert missing in result["missing"]
    assert result["state"] != "usable"
    assert not result["prose_call_corrections"]


def test_repeated_plain_asides_and_uncertainty(tmp_path):
    (tmp_path / "module.py").write_text("def display():\n    pass\n")
    prose = "display warning (maybe allowing a choice). warning (the easier way)."
    assert extract_repaired(tmp_path, prose, {})["state"] == "usable"
    for prefix in ["> ", "- ", "<div> ", "`unclosed "]:
        result = extract_repaired(tmp_path, prefix + prose, {})
        assert result["prose_span_analysis"]["uncertainty"]
        assert result["state"] != "usable"


@pytest.mark.parametrize(
    "code",
    [
        " \twarning (maybe + value)",
        "  \twarning (maybe + value)",
        "Text <code>warning (maybe + value)</code>",
    ],
)
def test_conservative_column_indentation_and_inline_html(tmp_path, code):
    (tmp_path / "module.py").write_text("def display():\n    pass\n")
    result = extract_repaired(
        tmp_path, "display warning (maybe allowing a choice).\n\n" + code, {}
    )
    assert result["state"] != "usable"
    assert any(m.get("symbol") == "warning" for m in result["missing"])


@pytest.mark.parametrize(
    "expression", ["warning (maybe + value)", "warning (a if value else b)"]
)
def test_valid_expression_without_markup_is_still_ambiguous(tmp_path, expression):
    (tmp_path / "module.py").write_text("def display():\n    pass\n")
    request = "display warning (maybe allowing a choice).\n" + expression
    result = extract_repaired(tmp_path, request, {})
    assert result["state"] != "usable"
    assert not result["prose_call_corrections"]
