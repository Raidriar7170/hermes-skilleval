#!/bin/bash
set -euo pipefail

python3 <<'PY'
from __future__ import annotations

import json
import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

TEMPLATE = Path("/root/offer_letter_template.docx")
DATA_FILE = Path("/root/employee_data.json")
OUTPUT = Path("/root/offer_letter_filled.docx")
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
W_T = f"{{{W_NS}}}t"
W_P = f"{{{W_NS}}}p"


def paragraph_text_nodes(paragraph: ET.Element) -> list[ET.Element]:
    return list(paragraph.iter(W_T))


def replace_paragraph_text(paragraph: ET.Element, data: dict[str, object]) -> bool:
    text_nodes = paragraph_text_nodes(paragraph)
    if not text_nodes:
        return False
    original = "".join(node.text or "" for node in text_nodes)
    replacement = original
    if "{{IF_RELOCATION}}" in replacement:
        if str(data.get("RELOCATION_PACKAGE", "")).lower() == "yes":
            replacement = replacement.replace("{{IF_RELOCATION}}", "")
            replacement = replacement.replace("{{END_IF_RELOCATION}}", "")
        else:
            replacement = ""

    def fill(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in data:
            return str(data[key])
        return match.group(0)

    replacement = re.sub(r"\{\{([A-Z_]+)\}\}", fill, replacement)
    if replacement == original:
        return False

    text_nodes[0].text = replacement
    text_nodes[0].set(f"{{{XML_NS}}}space", "preserve")
    for node in text_nodes[1:]:
        node.text = ""
    return True


def rewrite_word_part(raw: bytes, data: dict[str, object]) -> bytes:
    ET.register_namespace("w", W_NS)
    root = ET.fromstring(raw)
    changed = False
    for paragraph in root.iter(W_P):
        changed = replace_paragraph_text(paragraph, data) or changed
    if not changed:
        return raw
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp_path = Path(tmp.name)

    with zipfile.ZipFile(TEMPLATE, "r") as source, zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            raw = source.read(info.filename)
            if (
                info.filename == "word/document.xml"
                or re.fullmatch(r"word/header\d+\.xml", info.filename)
                or re.fullmatch(r"word/footer\d+\.xml", info.filename)
            ):
                raw = rewrite_word_part(raw, data)
            target.writestr(info, raw)

    tmp_path.replace(OUTPUT)
    print(f"Saved {OUTPUT}")


if __name__ == "__main__":
    main()
PY
