from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import ProductionSchedule


MANIFEST_NAME = "production.json"
DEFAULT_SOURCE = "input/planning.pdf"
DEFAULT_ANSWERS = "answers/decisions.json"
OUTPUT_FILES = {
    "roster_csv": "concept-rooster.csv",
    "roster_text": "concept-rooster.txt",
    "events": "events.txt",
    "control": "controle.json",
    "issues": "issues.txt",
}


def _production_id(name: str) -> str:
    match = re.match(r"^([A-Za-z0-9]+)(?:-|$)", name)
    return match.group(1) if match else name


def _production_title(name: str) -> str:
    parts = name.split("-", maxsplit=1)
    value = parts[1] if len(parts) == 2 else parts[0]
    return value.replace("-", " ").strip().title()


def _production_path(name: str) -> tuple[str, str]:
    year, separator, production_name = name.partition("-")
    if (
        not separator
        or not year
        or not production_name
        or Path(year).name != year
        or Path(production_name).name != production_name
        or year in {".", ".."}
        or production_name in {".", ".."}
    ):
        raise ValueError(
            "Gebruik jaar-productienaam, bijvoorbeeld 2627-cinderella."
        )
    return year, production_name


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def initialise_production(
    name: str,
    root: str | Path = "producties",
    title: str | None = None,
) -> Path:
    year, production_name = _production_path(name)

    production_dir = Path(root).expanduser().resolve() / year / production_name
    manifest_path = production_dir / MANIFEST_NAME
    if manifest_path.exists():
        raise FileExistsError(f"Productie bestaat al: {production_dir}")

    for directory in ("input", "answers", "output", "archive"):
        (production_dir / directory).mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_version": 1,
        "id": _production_id(name),
        "slug": name,
        "title": title or _production_title(name),
        "source": DEFAULT_SOURCE,
        "answers": DEFAULT_ANSWERS,
        "status": "intake",
    }
    _write_json(manifest_path, manifest)
    return production_dir


def load_manifest(production_dir: str | Path) -> tuple[Path, dict[str, Any]]:
    directory = Path(production_dir).expanduser().resolve()
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Productiebestand niet gevonden: {manifest_path}")

    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError("production.json moet een JSON-object bevatten.")
    if manifest.get("schema_version") != 1:
        raise ValueError("production.json heeft een onbekende schema_version.")
    return directory, manifest


def resolve_production_reference(
    reference: str | Path,
    root: str | Path = "producties",
) -> Path:
    candidate = Path(reference).expanduser()
    if (candidate / MANIFEST_NAME).is_file():
        return candidate.resolve()

    production_root = Path(root).expanduser().resolve()
    value = str(reference)
    if "-" in value and Path(value).name == value:
        year, production_name = _production_path(value)
        candidate = production_root / year / production_name
        if (candidate / MANIFEST_NAME).is_file():
            return candidate

    matches: list[Path] = []
    if Path(value).name == value and value not in {".", ".."}:
        matches = sorted(
            candidate
            for year_dir in production_root.glob("*")
            if year_dir.is_dir()
            for candidate in [year_dir / value]
            if (candidate / MANIFEST_NAME).is_file()
        )
    if not matches:
        raise FileNotFoundError(f"Productie niet gevonden: {value}")
    if len(matches) > 1:
        choices = ", ".join(str(path.relative_to(production_root)) for path in matches)
        raise ValueError(
            f"Meerdere producties heten '{value}': {choices}. "
            "Gebruik jaar-productienaam."
        )
    return matches[0].resolve()


def _safe_dossier_path(directory: Path, relative_value: str, field: str) -> Path:
    candidate = (directory / relative_value).resolve()
    try:
        candidate.relative_to(directory)
    except ValueError as error:
        raise ValueError(f"{field} moet binnen de productiemap liggen.") from error
    return candidate


def resolve_source_pdf(directory: Path, manifest: dict[str, Any]) -> Path:
    pdfs = list((directory / "input").glob("*.pdf"))
    if pdfs:
        def recency(path: Path) -> tuple[int, str]:
            stat = path.stat()
            created_ns = int(getattr(stat, "st_birthtime", 0) * 1_000_000_000)
            return max(created_ns, stat.st_mtime_ns), path.name

        return max(pdfs, key=recency).resolve()
    if not pdfs:
        raise FileNotFoundError(
            f"Geen PDF gevonden. Plaats de planning in {directory / 'input'}."
        )


def resolve_answers_path(directory: Path, manifest: dict[str, Any]) -> Path:
    configured = str(manifest.get("answers") or DEFAULT_ANSWERS)
    return _safe_dossier_path(directory, configured, "answers")


def output_paths(directory: Path) -> dict[str, Path]:
    output_dir = directory / "output"
    return {key: output_dir / filename for key, filename in OUTPUT_FILES.items()}


def concept_status(schedule: ProductionSchedule) -> str:
    if schedule.blocking_reasons:
        return "invoer_nodig"
    if (
        schedule.cao_conflicts
        or schedule.warnings
        or schedule.annotations
        or any(item.avm_status == "controleren" for item in schedule.items)
        or any(
            question.is_open
            for question in schedule.decision_questions
        )
    ):
        return "concept_met_conflicten"
    return "concept"


def write_answers_template(
    path: Path,
    schedule: ProductionSchedule,
) -> bool:
    if path.exists():
        return False
    questions = {
        question.id: {"value": None}
        for question in schedule.decision_questions
        if question.is_open
    }
    if not questions:
        return False
    _write_json(path, questions)
    return True


def update_manifest(
    directory: Path,
    manifest: dict[str, Any],
    source: Path,
    status: str,
) -> None:
    updated = dict(manifest)
    updated["source"] = source.relative_to(directory).as_posix()
    updated["status"] = status
    _write_json(directory / MANIFEST_NAME, updated)
