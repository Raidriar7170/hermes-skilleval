from __future__ import annotations

import json
import os
import re
import traceback
import zipfile
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

OUTPUT_FILE = Path(os.environ.get("OFFER_LETTER_OUTPUT", "/root/offer_letter_filled.docx"))
DATA_FILE = Path(os.environ.get("OFFER_LETTER_DATA", "/root/employee_data.json"))
LOG_DIR = Path(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"))

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W_T = f"{{{W_NS}}}t"
W_TBL = f"{{{W_NS}}}tbl"

SPLIT_PLACEHOLDER_FIELDS = [
    "DATE",
    "CANDIDATE_FULL_NAME",
    "CITY",
    "STATE",
    "ZIP_CODE",
    "POSITION",
    "DEPARTMENT",
    "RESPONSE_DEADLINE",
    "HR_NAME",
    "PTO_DAYS",
]

NESTED_TABLE_FIELDS = [
    "POSITION",
    "DEPARTMENT",
    "BASE_SALARY",
    "SIGNING_BONUS",
    "EQUITY_SHARES",
    "MANAGER_NAME",
]


class VerifierFailure(AssertionError):
    pass


def load_docx_parts(path: Path) -> dict[str, ET.Element]:
    if not path.exists():
        raise VerifierFailure(f"Output file not found: {path}")
    parts: dict[str, ET.Element] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name == "word/document.xml" or re.fullmatch(r"word/(header|footer)\d+\.xml", name):
                    parts[name] = ET.fromstring(archive.read(name))
    except zipfile.BadZipFile as exc:
        raise VerifierFailure(f"Output is not a valid docx zip: {path}") from exc
    if "word/document.xml" not in parts:
        raise VerifierFailure("docx is missing word/document.xml")
    return parts


def collect_text(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(W_T))


def all_text(parts: dict[str, ET.Element]) -> str:
    return "\n".join(collect_text(root) for _name, root in sorted(parts.items()))


def nested_table_text(parts: dict[str, ET.Element]) -> str:
    nested: list[str] = []

    def walk(element: ET.Element, table_depth: int) -> None:
        next_depth = table_depth + 1 if element.tag == W_TBL else table_depth
        if element.tag == W_TBL and table_depth >= 1:
            nested.append(collect_text(element))
        for child in list(element):
            walk(child, next_depth)

    walk(parts["word/document.xml"], 0)
    return "\n".join(nested)


def load_employee_data() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def assert_no_remaining_placeholders(document_text: str) -> None:
    matches = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", document_text)))
    if matches:
        raise VerifierFailure(f"Unreplaced placeholders: {matches}")


def assert_split_placeholders_replaced(document_text: str, data: dict[str, Any]) -> None:
    missing = [field for field in SPLIT_PLACEHOLDER_FIELDS if str(data[field]) not in document_text]
    if missing:
        raise VerifierFailure(f"Split placeholder values not found in document: {missing}")


def assert_nested_table_values(document_nested_text: str, data: dict[str, Any]) -> None:
    missing = [field for field in NESTED_TABLE_FIELDS if str(data[field]) not in document_nested_text]
    if missing:
        raise VerifierFailure(f"Nested table values not found in nested tables: {missing}")


def assert_conditional_section(document_text: str, data: dict[str, Any]) -> None:
    for marker in ("{{IF_RELOCATION}}", "{{END_IF_RELOCATION}}"):
        if marker in document_text:
            raise VerifierFailure(f"Conditional marker not removed: {marker}")
    for field in ("RELOCATION_AMOUNT", "RELOCATION_DAYS"):
        if str(data[field]) not in document_text:
            raise VerifierFailure(f"Conditional relocation value not found: {field}={data[field]!r}")


def write_results(results: list[dict[str, Any]]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for result in results if result["status"] == "passed")
    total = len(results)
    ctrf = {
        "results": {
            "tool": {"name": "stdlib-offer-letter-verifier"},
            "summary": {"tests": total, "passed": passed, "failed": total - passed},
            "tests": results,
        }
    }
    (LOG_DIR / "ctrf.json").write_text(json.dumps(ctrf, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (LOG_DIR / "reward.txt").write_text("1\n" if passed == total else "0\n", encoding="utf-8")


def run_test(name: str, fn: Callable[[], None], results: list[dict[str, Any]]) -> None:
    try:
        fn()
    except Exception as exc:
        results.append({"name": name, "status": "failed", "message": str(exc), "trace": traceback.format_exc()})
    else:
        results.append({"name": name, "status": "passed"})


def main() -> None:
    parts = load_docx_parts(OUTPUT_FILE)
    data = load_employee_data()
    document_text = all_text(parts)
    document_nested_text = nested_table_text(parts)
    results: list[dict[str, Any]] = []
    run_test("valid_docx_and_no_placeholders", lambda: assert_no_remaining_placeholders(document_text), results)
    run_test("split_placeholder_values", lambda: assert_split_placeholders_replaced(document_text, data), results)
    run_test("nested_table_values", lambda: assert_nested_table_values(document_nested_text, data), results)
    run_test("conditional_section", lambda: assert_conditional_section(document_text, data), results)
    write_results(results)


if __name__ == "__main__":
    main()
