"""Load exactly the dataset author's small pytest parser, without heavy harness deps."""

import ast
from enum import Enum
from pathlib import Path


def parse(log: str, harness: Path) -> dict:
    source = (harness / "swebench/harness/log_parsers/python.py").read_text()
    node = next(
        n
        for n in ast.parse(source).body
        if isinstance(n, ast.FunctionDef) and n.name == "parse_log_pytest"
    )
    function = ast.get_source_segment(source, node)
    assert function is not None
    statuses = Enum(
        "TestStatus", {s: s for s in ["PASSED", "FAILED", "SKIPPED", "ERROR"]}
    )
    namespace = {"TestStatus": statuses, "TestSpec": object}
    exec(compile(function, "<pinned-author-pytest-parser>", "exec"), namespace)
    return namespace["parse_log_pytest"](log, None)
