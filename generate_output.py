#!/usr/bin/env python3
"""Genereer alle controle-uitvoer vanuit één productieplanning-PDF."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_DIR = PROJECT_ROOT / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from autoplanner.avm import apply_avm_rules, load_answers, load_rules  # noqa: E402
from autoplanner.export import (  # noqa: E402
    write_avm_events_text,
    write_csv,
    write_daily_summary_text,
    write_json,
    write_text,
)
from autoplanner.parser import extract_schedule  # noqa: E402
from autoplanner.rules_report import write_rules_text  # noqa: E402
from autoplanner.shift_planner import update_schedule_validation  # noqa: E402


DEFAULT_PDF = (
    PROJECT_ROOT / "Documentation" / "PSB 2627 HNB3 Cinderella v02032026.pdf"
)
DEFAULT_RULES = PROJECT_ROOT / "config" / "avm_rules.json"
DEFAULT_CAO_RULES = PROJECT_ROOT / "config" / "cao_rules.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Genereer JSON, CSV en een tekstrooster vanuit de productie-PDF."
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=DEFAULT_PDF,
        help=f"Input-PDF (standaard: {DEFAULT_PDF.name})",
    )
    parser.add_argument(
        "--rules",
        type=Path,
        default=DEFAULT_RULES,
        help="AVM-regelbestand",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Map voor de gegenereerde bestanden",
    )
    parser.add_argument(
        "--name",
        default="cinderella",
        help="Bestandsnaam zonder extensie",
    )
    parser.add_argument(
        "--answers",
        type=Path,
        help="Optioneel JSON-bestand met antwoorden op conditionele vragen",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pdf = args.pdf.expanduser().resolve()
    rules_path = args.rules.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()

    if not pdf.is_file():
        raise SystemExit(f"Input-PDF niet gevonden: {pdf}")
    if not rules_path.is_file():
        raise SystemExit(f"AVM-regelbestand niet gevonden: {rules_path}")

    schedule = extract_schedule(pdf)
    rules = load_rules(rules_path)
    answers = load_answers(args.answers) if args.answers else {}
    apply_avm_rules(schedule, rules, answers)
    update_schedule_validation(schedule, rules)

    json_path = output_dir / f"{args.name}.json"
    csv_path = output_dir / f"{args.name}.csv"
    text_path = output_dir / f"{args.name}.txt"
    roster_text_path = output_dir / f"{args.name}_avm_rooster.txt"
    events_text_path = output_dir / f"{args.name}_avm_events.txt"
    rules_text_path = output_dir / "roosterregels.txt"
    write_json(schedule, json_path)
    write_csv(schedule, csv_path)
    write_daily_summary_text(schedule, text_path)
    write_text(schedule, roster_text_path, rules)
    write_avm_events_text(schedule, events_text_path)
    cao_rules = load_rules(DEFAULT_CAO_RULES)
    write_rules_text(rules, cao_rules, rules_text_path)

    counts = Counter(item.avm_status for item in schedule.items)
    required_places = sum(item.avm_required_count for item in schedule.items)
    print(f"Input: {pdf}")
    print(f"Planningregels: {len(schedule.items)}")
    print(f"AVM-activiteiten vereist: {counts['vereist']}")
    print(f"Totaal vereiste AVM-plaatsen: {required_places}")
    print(f"AVM controleren: {counts['controleren']}")
    print(f"Roosterstatus: {schedule.planning_status}")
    for question in schedule.decision_questions:
        if question.is_open:
            print(f"VRAAG [{question.id}]: {question.prompt}")
    if any(question.is_open for question in schedule.decision_questions):
        print("Beantwoord deze via --answers <json-bestand>.")
    print("Gegenereerd:")
    print(f"  {json_path}")
    print(f"  {csv_path}")
    print(f"  {text_path}")
    print(f"  {roster_text_path}")
    print(f"  {events_text_path}")
    print(f"  {rules_text_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
