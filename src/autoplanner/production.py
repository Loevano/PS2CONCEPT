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


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def initialise_production(
    name: str,
    root: str | Path = "productions",
    title: str | None = None,
) -> Path:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("Gebruik één mapnaam, bijvoorbeeld 2627-cinderella.")

    production_dir = Path(root).expanduser().resolve() / name
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


def _safe_dossier_path(directory: Path, relative_value: str, field: str) -> Path:
    candidate = (directory / relative_value).resolve()
    try:
        candidate.relative_to(directory)
    except ValueError as error:
        raise ValueError(f"{field} moet binnen de productiemap liggen.") from error
    return candidate


def resolve_source_pdf(directory: Path, manifest: dict[str, Any]) -> Path:
    configured = str(manifest.get("source") or DEFAULT_SOURCE)
    configured_path = _safe_dossier_path(directory, configured, "source")
    if configured_path.is_file():
        return configured_path

    pdfs = sorted((directory / "input").glob("*.pdf"))
    if len(pdfs) == 1:
        return pdfs[0].resolve()
    if not pdfs:
        raise FileNotFoundError(
            f"Geen PDF gevonden. Plaats de planning in {directory / 'input'}."
        )
    raise ValueError(
        "Meerdere PDF-bestanden gevonden; stel 'source' in production.json in."
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
