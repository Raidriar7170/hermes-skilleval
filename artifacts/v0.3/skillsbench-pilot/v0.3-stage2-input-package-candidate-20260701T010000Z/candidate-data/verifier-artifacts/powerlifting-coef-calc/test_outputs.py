from __future__ import annotations

import json
import math
import os
import re
import traceback
import zipfile
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

OUTPUT_FILE = Path(os.environ.get("POWERLIFTING_OUTPUT", "/root/data/openipf.xlsx"))
GROUND_TRUTH_FILE = Path(os.environ.get("POWERLIFTING_GROUND_TRUTH", "/verifier/cleaned_with_coefficients.xlsx"))
LOG_DIR = Path(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"))

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"s": SHEET_NS, "r": OFFICE_REL_NS}

EXPECTED_DOTS_COLUMNS = [
    "Name",
    "Sex",
    "BodyweightKg",
    "Best3SquatKg",
    "Best3BenchKg",
    "Best3DeadliftKg",
    "TotalKg",
    "Dots",
]

MALE_COEFFICIENTS = (-1.093e-06, 0.0007391293, -0.1918759221, 24.0900756, -307.75076)
FEMALE_COEFFICIENTS = (-1.0706e-06, 0.0005158568, -0.1126655495, 13.6175032, -57.96288)
TOLERANCE = 0.01


class VerifierFailure(AssertionError):
    pass


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("s:si", NS):
        values.append("".join(text.text or "" for text in item.iter(f"{{{SHEET_NS}}}t")))
    return values


def workbook_sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_by_id = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall(f"{{{REL_NS}}}Relationship")
        if rel.attrib.get("Type", "").endswith("/worksheet")
    }
    paths: dict[str, str] = {}
    for sheet in workbook.findall("s:sheets/s:sheet", NS):
        name = sheet.attrib["name"]
        rel_id = sheet.attrib[f"{{{OFFICE_REL_NS}}}id"]
        target = rel_by_id[rel_id]
        paths[name] = "xl/" + target.lstrip("/")
    return paths


def col_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref)
    if not letters:
        raise VerifierFailure(f"Malformed cell reference: {cell_ref}")
    value = 0
    for char in letters.group(0):
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value


def cell_text(cell: ET.Element, shared_strings: list[str]) -> Any:
    formula = cell.find("s:f", NS)
    if formula is not None:
        return "=" + (formula.text or "")
    cell_type = cell.attrib.get("t")
    if cell_type == "s":
        value_node = cell.find("s:v", NS)
        if value_node is None or value_node.text is None:
            return ""
        return shared_strings[int(value_node.text)]
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(f"{{{SHEET_NS}}}t"))
    value_node = cell.find("s:v", NS)
    if value_node is None or value_node.text is None:
        return ""
    text = value_node.text
    try:
        number = float(text)
    except ValueError:
        return text
    if math.isfinite(number) and abs(number - round(number)) < 1e-9:
        return int(round(number))
    return number


def parse_sheet(archive: zipfile.ZipFile, sheet_name: str) -> list[dict[str, Any]]:
    paths = workbook_sheet_paths(archive)
    if sheet_name not in paths:
        raise VerifierFailure(f"Workbook missing sheet: {sheet_name}")
    shared_strings = read_shared_strings(archive)
    root = ET.fromstring(archive.read(paths[sheet_name]))
    rows: list[dict[int, Any]] = []
    for row in root.findall(".//s:sheetData/s:row", NS):
        values: dict[int, Any] = {}
        for cell in row.findall("s:c", NS):
            values[col_index(cell.attrib["r"])] = cell_text(cell, shared_strings)
        rows.append(values)
    if not rows:
        return []
    header = [str(rows[0].get(index, "")) for index in range(1, max(rows[0], default=0) + 1)]
    table: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not row:
            continue
        record = {name: row.get(index, "") for index, name in enumerate(header, start=1) if name}
        table.append(record)
    return table


def raw_sheet_rows(archive: zipfile.ZipFile, sheet_name: str) -> list[dict[str, Any]]:
    paths = workbook_sheet_paths(archive)
    if sheet_name not in paths:
        raise VerifierFailure(f"Workbook missing sheet: {sheet_name}")
    shared_strings = read_shared_strings(archive)
    root = ET.fromstring(archive.read(paths[sheet_name]))
    rows: list[dict[str, Any]] = []
    for row in root.findall(".//s:sheetData/s:row", NS):
        values: dict[str, Any] = {}
        for cell in row.findall("s:c", NS):
            values[cell.attrib["r"]] = cell_text(cell, shared_strings)
        rows.append(values)
    return rows


def calculate_dots(sex: str, bodyweight: float, total: float) -> float:
    if sex == "M":
        bw = max(40, min(210, bodyweight))
        a, b, c, d, e = MALE_COEFFICIENTS
    else:
        bw = max(40, min(150, bodyweight))
        a, b, c, d, e = FEMALE_COEFFICIENTS
    denominator = a * bw**4 + b * bw**3 + c * bw**2 + d * bw + e
    return round(total * (500 / denominator), 3)


def assert_sheet_structure() -> None:
    with zipfile.ZipFile(OUTPUT_FILE) as archive:
        data_rows = parse_sheet(archive, "Data")
        dots_rows = parse_sheet(archive, "Dots")
    if not data_rows:
        raise VerifierFailure("Data sheet must contain lifter rows")
    if not dots_rows:
        raise VerifierFailure("Dots sheet must contain lifter rows")
    if list(dots_rows[0]) != EXPECTED_DOTS_COLUMNS:
        raise VerifierFailure(f"Dots columns mismatch: {list(dots_rows[0])}")
    if len(dots_rows) != len(data_rows):
        raise VerifierFailure(f"Dots row count {len(dots_rows)} does not match Data row count {len(data_rows)}")


def assert_dots_formulas() -> None:
    with zipfile.ZipFile(OUTPUT_FILE) as archive:
        rows = raw_sheet_rows(archive, "Dots")
    if len(rows) < 2:
        raise VerifierFailure("Dots sheet has no data formulas")
    total_formula = str(rows[1].get("G2", ""))
    dots_formula = str(rows[1].get("H2", ""))
    if total_formula != "=D2+E2+F2":
        raise VerifierFailure(f"Expected G2 total formula =D2+E2+F2, got {total_formula!r}")
    required_tokens = ["=ROUND(IF(", "POWER(", "MAX(40,MIN(210,C2))", "MAX(40,MIN(150,C2))"]
    missing = [token for token in required_tokens if token not in dots_formula]
    if missing:
        raise VerifierFailure(f"Dots formula missing tokens {missing}: {dots_formula!r}")


def assert_dots_accuracy() -> None:
    with zipfile.ZipFile(OUTPUT_FILE) as output_archive:
        data_rows = parse_sheet(output_archive, "Data")
    with zipfile.ZipFile(GROUND_TRUTH_FILE) as truth_archive:
        truth_rows = parse_sheet(truth_archive, "Data")
    truth_by_name = {str(row["Name"]): row for row in truth_rows}
    mismatches: list[str] = []
    for row in data_rows:
        name = str(row["Name"])
        if name not in truth_by_name:
            mismatches.append(f"{name}: missing ground truth")
            continue
        total = float(row["Best3SquatKg"]) + float(row["Best3BenchKg"]) + float(row["Best3DeadliftKg"])
        computed = calculate_dots(str(row["Sex"]), float(row["BodyweightKg"]), total)
        expected = float(truth_by_name[name]["Dots"])
        if abs(computed - expected) > TOLERANCE:
            mismatches.append(f"{name}: computed={computed}, expected={expected}")
    if mismatches:
        raise VerifierFailure("Dots mismatches found: " + "; ".join(mismatches))


def write_results(results: list[dict[str, Any]]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for result in results if result["status"] == "passed")
    total = len(results)
    ctrf = {
        "results": {
            "tool": {"name": "stdlib-powerlifting-verifier"},
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
    results: list[dict[str, Any]] = []
    run_test("sheet_structure", assert_sheet_structure, results)
    run_test("dots_formulas", assert_dots_formulas, results)
    run_test("dots_accuracy", assert_dots_accuracy, results)
    write_results(results)


if __name__ == "__main__":
    main()
