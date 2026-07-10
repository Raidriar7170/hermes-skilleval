#!/bin/bash
set -euo pipefail

python3 <<'PY'
from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

WORKBOOK = Path("/root/data/openipf.xlsx")
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", SHEET_NS)

HEADERS = [
    "Name",
    "Sex",
    "BodyweightKg",
    "Best3SquatKg",
    "Best3BenchKg",
    "Best3DeadliftKg",
    "TotalKg",
    "Dots",
]


def row_count(sheet_xml: bytes) -> int:
    root = ET.fromstring(sheet_xml)
    rows = root.findall(f".//{{{SHEET_NS}}}sheetData/{{{SHEET_NS}}}row")
    return max(int(row.attrib["r"]) for row in rows)


def col_name(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def inline_string_cell(ref: str, value: str) -> ET.Element:
    cell = ET.Element(f"{{{SHEET_NS}}}c", {"r": ref, "t": "inlineStr"})
    inline = ET.SubElement(cell, f"{{{SHEET_NS}}}is")
    text = ET.SubElement(inline, f"{{{SHEET_NS}}}t")
    text.text = value
    return cell


def formula_cell(ref: str, formula: str) -> ET.Element:
    cell = ET.Element(f"{{{SHEET_NS}}}c", {"r": ref})
    f = ET.SubElement(cell, f"{{{SHEET_NS}}}f")
    f.text = formula
    ET.SubElement(cell, f"{{{SHEET_NS}}}v").text = "0"
    return cell


def dots_formula(row: int) -> str:
    male_bw = f"MAX(40,MIN(210,C{row}))"
    female_bw = f"MAX(40,MIN(150,C{row}))"
    male_poly = (
        f"(-1.093e-06*POWER({male_bw},4)"
        f"+0.0007391293*POWER({male_bw},3)"
        f"+-0.1918759221*POWER({male_bw},2)"
        f"+24.0900756*{male_bw}"
        f"+-307.75076)"
    )
    female_poly = (
        f"(-1.0706e-06*POWER({female_bw},4)"
        f"+0.0005158568*POWER({female_bw},3)"
        f"+-0.1126655495*POWER({female_bw},2)"
        f"+13.6175032*{female_bw}"
        f"+-57.96288)"
    )
    return f'ROUND(IF(B{row}="M",G{row}*(500/{male_poly}),G{row}*(500/{female_poly})),3)'


def build_dots_sheet(data_rows: int) -> bytes:
    worksheet = ET.Element(f"{{{SHEET_NS}}}worksheet")
    ET.SubElement(worksheet, f"{{{SHEET_NS}}}dimension", {"ref": f"A1:H{data_rows}"})
    sheet_views = ET.SubElement(worksheet, f"{{{SHEET_NS}}}sheetViews")
    ET.SubElement(sheet_views, f"{{{SHEET_NS}}}sheetView", {"workbookViewId": "0"})
    ET.SubElement(worksheet, f"{{{SHEET_NS}}}sheetFormatPr", {"defaultRowHeight": "15"})
    sheet_data = ET.SubElement(worksheet, f"{{{SHEET_NS}}}sheetData")

    header_row = ET.SubElement(sheet_data, f"{{{SHEET_NS}}}row", {"r": "1", "spans": "1:8"})
    for index, header in enumerate(HEADERS, start=1):
        header_row.append(inline_string_cell(f"{col_name(index)}1", header))

    for row in range(2, data_rows + 1):
        row_el = ET.SubElement(sheet_data, f"{{{SHEET_NS}}}row", {"r": str(row), "spans": "1:8"})
        formulas = [
            f"Data!A{row}",
            f"Data!B{row}",
            f"Data!I{row}",
            f"Data!K{row}",
            f"Data!L{row}",
            f"Data!M{row}",
            f"D{row}+E{row}+F{row}",
            dots_formula(row),
        ]
        for col, formula in enumerate(formulas, start=1):
            row_el.append(formula_cell(f"{col_name(col)}{row}", formula))

    ET.SubElement(worksheet, f"{{{SHEET_NS}}}pageMargins", {"left": "0.7", "right": "0.7", "top": "0.75", "bottom": "0.75", "header": "0.3", "footer": "0.3"})
    return ET.tostring(worksheet, encoding="utf-8", xml_declaration=True)


def main() -> None:
    with zipfile.ZipFile(WORKBOOK, "r") as archive:
        data_rows = row_count(archive.read("xl/worksheets/sheet1.xml"))
        if data_rows < 2:
            raise ValueError("Data sheet has no lifter rows")
        new_sheet = build_dots_sheet(data_rows)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp_path = Path(tmp.name)
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for info in archive.infolist():
                raw = archive.read(info.filename)
                if info.filename == "xl/worksheets/sheet2.xml":
                    raw = new_sheet
                target.writestr(info, raw)
    tmp_path.replace(WORKBOOK)
    print(f"Updated {WORKBOOK} Dots sheet for {data_rows - 1} lifters")


if __name__ == "__main__":
    main()
PY
