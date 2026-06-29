from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .avm import apply_avm_rules, load_answers, load_rules
from .export import (
    write_avm_events_text,
    write_csv,
    write_issues_text,
    write_json,
    write_roster_csv,
    write_text,
)
from .parser import extract_schedule
from .production import (
    concept_status,
    initialise_production,
    load_manifest,
    output_paths,
    resolve_answers_path,
    resolve_source_pdf,
    update_manifest,
    write_answers_template,
)
from .shift_planner import plan_daily_shifts_for_items, update_schedule_validation


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES = PROJECT_ROOT / "config" / "avm_rules.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auto-planner",
        description="Lees lokaal een productieplanning uit PDF en maak controle-uitvoer.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    extract = subparsers.add_parser("extract", help="PDF omzetten naar JSON en CSV")
    extract.add_argument("pdf", type=Path, help="Pad naar de productieplanning-PDF")
    extract.add_argument(
        "--rules",
        type=Path,
        default=DEFAULT_RULES,
        help="AVM-regelbestand in JSON-formaat",
    )
    extract.add_argument("--json", type=Path, required=True, help="JSON-uitvoerpad")
    extract.add_argument("--csv", type=Path, required=True, help="CSV-uitvoerpad")
    extract.add_argument("--text", type=Path, help="Optioneel leesbaar tekstrooster")
    extract.add_argument(
        "--events-text", type=Path, help="Optioneel tekstoverzicht van alle AVM-events"
    )
    extract.add_argument(
        "--answers",
        type=Path,
        help="Optioneel JSON-bestand met antwoorden op conditionele vragen",
    )
    initialise = subparsers.add_parser(
        "init", help="Maak een nieuw productiedossier"
    )
    initialise.add_argument(
        "name", help="Mapnaam, bijvoorbeeld 2627-cinderella"
    )
    initialise.add_argument(
        "--root",
        type=Path,
        default=Path("productions"),
        help="Bovenliggende productiemap",
    )
    initialise.add_argument("--title", help="Leesbare productietitel")

    generate = subparsers.add_parser(
        "generate", help="Genereer alle conceptuitvoer van een productiedossier"
    )
    generate.add_argument("production", type=Path, help="Pad naar productiedossier")
    generate.add_argument(
        "--rules",
        type=Path,
        default=DEFAULT_RULES,
        help="AVM-regelbestand in JSON-formaat",
    )
    return parser


def run_extract(args: argparse.Namespace) -> int:
    if not args.pdf.is_file():
        raise SystemExit(f"PDF niet gevonden: {args.pdf}")
    if not args.rules.is_file():
        raise SystemExit(f"Regelbestand niet gevonden: {args.rules}")

    schedule = extract_schedule(args.pdf)
    rules = load_rules(args.rules)
    answers = load_answers(args.answers) if args.answers else {}
    apply_avm_rules(schedule, rules, answers)
    update_schedule_validation(schedule, rules)
    write_json(schedule, args.json)
    write_csv(schedule, args.csv)
    if args.text:
        write_text(schedule, args.text, rules)
    if args.events_text:
        write_avm_events_text(schedule, args.events_text)

    counts = Counter(item.avm_status for item in schedule.items)
    required_people = sum(item.avm_required_count for item in schedule.items)
    print(f"Bron: {schedule.source_file}")
    print(f"Titel: {schedule.title or 'onbekend'}")
    print(f"Planningregels: {len(schedule.items)}")
    print(f"AVM-activiteiten vereist: {counts['vereist']}")
    print(f"Totaal vereiste AVM-plaatsen: {required_people}")
    print(f"AVM controleren: {counts['controleren']}")
    print(f"Roosterstatus: {schedule.planning_status}")
    print(
        "Open vragen: "
        f"{sum(question.is_open for question in schedule.decision_questions)}"
    )
    for question in schedule.decision_questions:
        if question.is_open:
            print(f"VRAAG [{question.id}]: {question.prompt}")
    if any(question.is_open for question in schedule.decision_questions):
        print("Beantwoord deze via --answers <json-bestand>.")
    print(f"Losse bronannotaties: {len(schedule.annotations)}")
    print(f"JSON: {args.json}")
    print(f"CSV: {args.csv}")
    if args.text:
        print(f"Tekst: {args.text}")
    if args.events_text:
        print(f"AVM-events: {args.events_text}")
    for warning in schedule.warnings:
        print(f"WAARSCHUWING: {warning}")
    return 0


def run_init(args: argparse.Namespace) -> int:
    try:
        production_dir = initialise_production(args.name, args.root, args.title)
    except (ValueError, FileExistsError) as error:
        raise SystemExit(str(error)) from error
    print(f"Productiedossier aangemaakt: {production_dir}")
    print(f"Plaats de planning-PDF in: {production_dir / 'input'}")
    print(
        "Genereer daarna met: "
        f"auto-planner generate {production_dir}"
    )
    return 0


def run_generate(args: argparse.Namespace) -> int:
    try:
        production_dir, manifest = load_manifest(args.production)
        pdf = resolve_source_pdf(production_dir, manifest)
        answers_path = resolve_answers_path(production_dir, manifest)
    except (FileNotFoundError, ValueError, OSError) as error:
        raise SystemExit(str(error)) from error

    rules_path = args.rules.expanduser().resolve()
    if not rules_path.is_file():
        raise SystemExit(f"Regelbestand niet gevonden: {rules_path}")

    schedule = extract_schedule(pdf)
    if not schedule.title and manifest.get("title"):
        schedule.title = str(manifest["title"])
    rules = load_rules(rules_path)
    try:
        answers = load_answers(answers_path) if answers_path.is_file() else {}
    except (ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"Ongeldig antwoordenbestand: {error}") from error

    apply_avm_rules(schedule, rules, answers)
    update_schedule_validation(schedule, rules)
    status = concept_status(schedule)
    template_created = write_answers_template(answers_path, schedule)
    paths = output_paths(production_dir)

    write_roster_csv(schedule, paths["roster_csv"], rules)
    write_text(schedule, paths["roster_text"], rules)
    write_avm_events_text(schedule, paths["events"])
    write_issues_text(schedule, paths["issues"], status)
    schedule.planning_status = status
    write_json(schedule, paths["control"])
    update_manifest(production_dir, manifest, pdf, status)

    assignments = update_schedule_validation(schedule, rules)
    shift_count = sum(
        len(plan_daily_shifts_for_items(position, items, rules))
        for position, items in assignments.items()
    )
    review_count = sum(item.avm_status == "controleren" for item in schedule.items)
    open_question_count = sum(
        question.is_open for question in schedule.decision_questions
    )
    other_blocking_count = sum(
        not reason.startswith("Open vraag:")
        for reason in schedule.blocking_reasons
    )
    issue_count = (
        other_blocking_count
        + len(schedule.cao_conflicts)
        + len(schedule.warnings)
        + review_count
        + len(schedule.annotations)
        + open_question_count
    )
    print(f"Productie: {manifest.get('id', '-')} - {schedule.title or manifest.get('title', 'onbekend')}")
    print(f"Status: {status}")
    print(f"Activiteiten: {len(schedule.items)}")
    print(
        "AVM-events: "
        f"{sum(item.avm_required_count >= 1 for item in schedule.items)}"
    )
    print(f"Voorgestelde diensten: {shift_count}")
    print(
        "Open vragen: "
        f"{open_question_count}"
    )
    print(f"Aandachtspunten: {issue_count}")
    if template_created:
        print(f"Antwoordenbestand aangemaakt: {answers_path}")
    print(f"Output: {production_dir / 'output'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "extract":
        return run_extract(args)
    if args.command == "init":
        return run_init(args)
    if args.command == "generate":
        return run_generate(args)
    raise SystemExit(f"Onbekend commando: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
