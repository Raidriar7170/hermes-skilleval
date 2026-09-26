"""Copy completed source-only outputs; retain factual edits as explicit records."""

import hashlib
import json
from pathlib import Path
import shutil
import yaml

ROOT = Path(__file__).resolve().parents[2]
P = Path("/tmp/hermes-native-gap-phase2-private")
STUDY = "native-gap-phase2-same-library-v1"
OUT = ROOT / "configs" / STUDY
CORRECTIONS = {
    "pyupgrade-percent-string-width": [
        ("without another alignment flag", "with an empty `conversion_flag`")
    ],
    "pyupgrade-invalid-format-fstring": [
        (
            "The final patch was not validated end to end",
            "End-to-end validation is not established by the supplied excerpts",
        )
    ],
}


def main():
    batches = []
    entries = []
    changes = []
    for batch in range(1, 5):
        work = P / f"conversion-{batch}"
        if not (work / "result.json").exists():
            continue
        result = json.loads((work / "result.json").read_text())
        skills = work / "repo/skills"
        provenance = work / "repo/provenance.json"
        batches.append(
            {
                "batch": batch,
                "terminal": result.get("worker", {}).get("terminal"),
                "elapsed_seconds": result["elapsed_seconds"],
                "provenance": json.loads(provenance.read_text())
                if provenance.exists()
                else None,
            }
        )
        for f in sorted(skills.glob("*/SKILL.md")):
            original = f.read_text()
            text = original
            for before, after in CORRECTIONS.get(f.parent.name, []):
                if before in text:
                    text = text.replace(before, after)
                    changes.append(
                        {
                            "skill": f.parent.name,
                            "before": before,
                            "after": after,
                            "reason": "Independent source-only review factual narrowing; no target feedback",
                        }
                    )
            header = yaml.safe_load(text.split("---", 2)[1])
            name = header["name"]
            assert name == f.parent.name and isinstance(header["description"], str)
            target = OUT / "skills" / name
            target.mkdir(parents=True, exist_ok=True)
            (target / "SKILL.md").write_text(text)
            for extra in f.parent.rglob("*"):
                if extra.is_file() and extra.name != "SKILL.md":
                    dest = target / extra.relative_to(f.parent)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(extra, dest)
            entries.append(
                {
                    "name": name,
                    "description": header["description"],
                    "path": f"/home/native/.agents/skills/{name}/SKILL.md",
                    "batch": batch,
                    "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "generated_sha256": hashlib.sha256(original.encode()).hexdigest(),
                }
            )
    assert len({e["name"] for e in entries}) == len(entries), "Duplicate skill names"
    entries.sort(key=lambda e: e["name"])
    catalog = "# Available historical experience\n\nAll entries are optional. Current requirements and actual source take priority. Read the body and references to judge applicability.\n\n"
    catalog += "\n".join(
        f"- **{e['name']}**: {e['description']}\n  Path: `{e['path']}`\n"
        for e in entries
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "catalog.md").write_text(catalog)
    # Same logical catalog path in both arms; mounted with the full library.
    (OUT / "skills/catalog.md").write_text(catalog)
    (OUT / "library-manifest.json").write_text(
        json.dumps(
            {
                "status": "PRE_FREEZE",
                "entries": entries,
                "completed_initial_batches": batches,
                "factual_corrections": changes,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        "completed batches",
        len(batches),
        "skills",
        len(entries),
        "corrections",
        len(changes),
    )


if __name__ == "__main__":
    main()
