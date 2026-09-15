"""Keep current report generators from overwriting this project's evidence."""

from pathlib import Path


def protect_historical_output(path: Path | str) -> None:
    target = Path(path).resolve()
    candidates = {Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents}
    for root in candidates:
        if not (root / "src/hermes_skilleval").is_dir():
            continue
        for relative in ["docs/demo", "artifacts/repo-portability"]:
            frozen = (root / relative).resolve()
            if target == frozen or frozen in target.parents:
                raise ValueError(
                    f"Protected historical output: {path}. Choose a new temporary/output directory; historical evidence is read-only."
                )
