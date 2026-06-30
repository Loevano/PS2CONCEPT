from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from .models import ProductionSchedule
from .shift_planner import (
    assigned_items,
    plan_daily_shifts_for_items,
    update_schedule_validation,
)


DUTCH_DAYS = [
    "maandag",
    "dinsdag",
    "woensdag",
    "donderdag",
    "vrijdag",
    "zaterdag",
    "zondag",
]
DUTCH_DAYS_SHORT = ["ma", "di", "wo", "do", "vr", "za", "zo"]
DUTCH_MONTHS = [
    "",
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
]
ACTIVITY_LEGEND_LINES = [
    "  BEL = Belichten           CD  = Cd-toneelrepetitie",
    "  GEN = Generale            OR  = Orkestrepetitie",
    "  OTR = Orkesttoneelrep.    ZIT = Zit/Sitzprobe",
    "  PTR = Pianotoneelrepetitie",
    "  PB  = Proefbouw           PRES = Presentatie cast & huis",
    "  PVG = Pianovoorgenerale   SR  = Solistenrepetitie",
    "  RR  = Regierepetitie",
    "  SV  = Schoolvoorstelling  TR  = Technische repetitie",
    "  V   = Voorstelling        VGO = Voorgenerale orkest",
]
COMPACT_ACTIVITY_LEGEND_LINES = [
    "  BEL = Belichten           CD  = Cd-toneelrepetitie",
    "  GEN = Generale            OR  = Orkestrepetitie",
    "  OTR = Orkesttoneelrep.    ZIT = Zit/Sitzprobe",
    "  PTR = Pianotoneelrepetitie",
    "  PB  = Proefbouw           PRES = Presentatie cast & huis",
    "  PVG = Pianovoorgenerale   SR  = Solistenrepetitie",
    "  RR  = Regierepetitie",
    "  SV  = Schoolvoorstelling  TR  = Technische repetitie",
    "  VGO = Voorgenerale orkest  V1/V2/... = Voorstelling",
]
EVENT_ORDER = {
    "V": 0,
    "SV": 0,
    "GEN": 1,
    "VGO": 2,
    "OTR": 3,
    "ZIT": 3,
    "OR": 4,
    "TR": 5,
    "RR": 5,
    "PTR": 6,
    "SR": 7,
    "CD": 8,
    "BEL": 9,
    "PB": 10,
    "PRES": 11,
}


def write_json(schedule: ProductionSchedule, target: str | Path) -> None:
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(schedule.to_dict(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_csv(schedule: ProductionSchedule, target: str | Path) -> None:
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "id",
        "datum",
        "start",
        "einde",
        "soort",
        "activiteit",
        "toelichting",
        "locatie",
        "avm_status",
        "avm_aantal",
        "avm_maximum_aantal",
        "avm_optioneel",
        "niet_avm_toegestaan",
        "avm_voorkeurspositie",
        "avm_standaardpositie",
        "avm_flexibele_posities",
        "avm_aanwezig_vanaf",
        "avm_daguitloop_minuten",
        "avm_planniveau",
        "avm_toewijzingsstatus",
        "avm_reden_niet_ingepland",
        "gegenereerd_door_regel",
        "avm_redenen",
        "bronpagina",
        "bronregel",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for item in schedule.items:
            writer.writerow(
                {
                    "id": item.id,
                    "datum": item.day.isoformat(),
                    "start": item.start.strftime("%H:%M"),
                    "einde": item.end.strftime("%Y-%m-%d %H:%M") if item.end else "",
                    "soort": item.kind,
                    "activiteit": item.activity,
                    "toelichting": " | ".join(item.details),
                    "locatie": item.location or "",
                    "avm_status": item.avm_status,
                    "avm_aantal": item.avm_required_count or "",
                    "avm_maximum_aantal": item.avm_maximum_count or "",
                    "avm_optioneel": "ja" if item.avm_optional else "nee",
                    "niet_avm_toegestaan": "ja" if item.non_avm_allowed else "nee",
                    "avm_voorkeurspositie": item.avm_preferred_position or "",
                    "avm_standaardpositie": item.avm_default_position or "",
                    "avm_flexibele_posities": ",".join(item.avm_flexible_positions),
                    "avm_aanwezig_vanaf": (
                        item.avm_call_time.strftime("%Y-%m-%d %H:%M")
                        if item.avm_call_time
                        else ""
                    ),
                    "avm_daguitloop_minuten": (
                        item.avm_day_wrap_minutes
                        if item.avm_day_wrap_minutes is not None
                        else ""
                    ),
                    "avm_planniveau": item.avm_planning_level or "",
                    "avm_toewijzingsstatus": item.avm_assignment_status or "",
                    "avm_reden_niet_ingepland": item.avm_omission_reason or "",
                    "gegenereerd_door_regel": item.generated_by_rule or "",
                    "avm_redenen": " | ".join(item.avm_reasons),
                    "bronpagina": item.page,
                    "bronregel": item.source_line,
                }
            )


def write_roster_csv(
    schedule: ProductionSchedule,
    target: str | Path,
    rules: dict | None = None,
) -> None:
    """Schrijf één Excel-vriendelijke regel per voorgestelde AVM-dienst."""
    rules = rules or {}
    assignments = update_schedule_validation(schedule, rules)
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "medewerker",
        "datum",
        "start",
        "einde",
        "duur",
        "events",
        "chronologisch",
        "overstaan",
        "opmerking",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for position, items in assignments.items():
            for shift in plan_daily_shifts_for_items(position, items, rules):
                coded_items = [
                    (item, _compact_activity_code(item.activity))
                    for item in shift.items
                ]
                event_codes = [
                    code
                    for item, code in sorted(
                        coded_items,
                        key=lambda value: _event_sort_key(value[0], value[1]),
                    )
                ]
                chronological = "; ".join(
                    f"{code} {_activity_time(item)}"
                    for item, code in coded_items
                )
                writer.writerow(
                    {
                        "medewerker": position,
                        "datum": shift.day.isoformat(),
                        "start": shift.start.strftime("%H:%M"),
                        "einde": shift.end.strftime("%H:%M"),
                        "duur": _duration_text(shift.duration_minutes),
                        "events": ", ".join(event_codes),
                        "chronologisch": chronological,
                        "overstaan": (
                            "x"
                            if any(
                                item.avm_day_wrap_minutes == 30
                                for item in shift.items
                            )
                            else ""
                        ),
                        "opmerking": " / ".join(shift.flags),
                    }
                )


def _format_day(value: date) -> str:
    return (
        f"{DUTCH_DAYS[value.weekday()]} {value.day} "
        f"{DUTCH_MONTHS[value.month]} {value.year}"
    )


def _activity_time(item) -> str:
    if not item.end:
        return item.start.strftime("%H:%M")
    end_text = item.end.strftime("%H:%M")
    if item.end.date() != item.day:
        end_text += " (+1 dag)"
    return f"{item.start:%H:%M}-{end_text}"


def _activity_label(activity: str) -> str:
    if re.search(r"^orkest\s*toneelrepetitie", activity, flags=re.IGNORECASE):
        return "OTR — Orkest toneel repetitie"
    if re.search(r"^voorgenerale\s+orkest", activity, flags=re.IGNORECASE):
        return "VGO — Voor Generale Orkest"
    if re.search(r"^piano\s+voorgenerale", activity, flags=re.IGNORECASE):
        return "PVG — Piano Voorgenerale"
    return activity


def _short_production_name(title: str | None) -> str:
    if not title:
        return "onbekend"
    return re.sub(
        r"^(?:HNB|DNO)\s+\d+\s*-\s*", "", title, flags=re.IGNORECASE
    ).strip()


def _schedule_activity_code(activity: str) -> str:
    mappings = [
        (r"^orkest\s*toneelrepetitie", "OTR"),
        (r"^(?:zit|sitzprobe)(?:\s+.*)?$", "ZIT"),
        (r"^voorgenerale\s+orkest", "VGO"),
        (r"^piano\s+voorgenerale", "PVG"),
        (r"^piano\s+toneelrepetitie", "PTR"),
        (r"^technische\s+repetitie", "TR"),
        (r"^cd\s+toneelrepetitie", "CD"),
        (r"^orkestrepetitie", "OR"),
        (r"^solistenrepetitie", "SR"),
        (r"^generale(?:\s+repetitie)?$", "GEN"),
        (r"^schoolvoorstelling$", "SV"),
        (r"^proefbouw(?:\s+.*)?$", "PB"),
        (
            r"^(?:presentatie\s+)?cast\s*(?:&|en)\s*huis(?:\s+presentatie)?$",
            "PRES",
        ),
        (r"^regie\s*repetitie(?:\s+.*)?$", "RR"),
    ]
    for pattern, code in mappings:
        if re.search(pattern, activity, flags=re.IGNORECASE):
            return code
    performance = re.search(r"^voorstelling(?:\s+(\d+))?$", activity, re.IGNORECASE)
    if performance:
        return f"V {performance.group(1)}" if performance.group(1) else "V"
    if re.search(r"\bbelichten\b", activity, flags=re.IGNORECASE):
        return "BEL"
    return activity


def _event_activity_code(activity: str) -> str:
    code = _schedule_activity_code(activity)
    return code if code != activity else "-"


def _compact_activity_code(activity: str) -> str:
    performance = re.search(r"^voorstelling(?:\s+(\d+))?$", activity, re.IGNORECASE)
    if performance:
        number = performance.group(1)
        return f"V{number}" if number else "V"
    return _event_activity_code(activity)


def _is_performance_code(code: str) -> bool:
    return bool(re.fullmatch(r"V\d+", code)) or code in {"V", "SV"}


def _event_sort_key(item, code: str):
    order_code = "V" if _is_performance_code(code) else code
    return (EVENT_ORDER.get(order_code, 99), item.start, code)


def _duration_text(minutes: int) -> str:
    return f"{minutes // 60:02d}u{minutes % 60:02d}"


def _activity_with_details(item) -> str:
    if not item.details:
        return item.activity
    return f"{item.activity} — {'; '.join(item.details)}"


def _table_row(values: list[str], widths: list[int]) -> str:
    return " | ".join(value.ljust(widths[index]) for index, value in enumerate(values))


def _append_table(lines: list[str], headers: list[str], rows: list[list[str]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    lines.append(_table_row(headers, widths))
    lines.append("-+-".join("-" * width for width in widths))
    lines.extend(_table_row(row, widths) for row in rows)


def _append_person_roster(
    lines: list[str],
    schedule: ProductionSchedule,
    position: str,
    rules: dict,
    items: list | None = None,
) -> None:
    assigned = items if items is not None else assigned_items(schedule, position, rules)
    shifts = plan_daily_shifts_for_items(position, assigned, rules)
    if position == "AVM1":
        role = "productieleiding"
    elif position == "AVM2":
        role = "tweede AVM'er"
    else:
        role = "teamovername voor CAO-oplossing"
    lines.extend(
        [
            f"ROOSTER {position}",
            f"Rol: {role}",
            f"Diensten: {len(shifts)} | Toegewezen activiteiten: {len(assigned)}",
        ]
    )
    rows: list[list[str]] = []
    for shift in shifts:
        day_text = f"{DUTCH_DAYS_SHORT[shift.day.weekday()]} {shift.day:%d-%m-%Y}"
        duration = _duration_text(shift.duration_minutes)
        coded_items = [(item, _compact_activity_code(item.activity)) for item in shift.items]
        event_codes = [
            code
            for item, code in sorted(
                coded_items,
                key=lambda value: _event_sort_key(value[0], value[1]),
            )
        ]
        chronological = "; ".join(
            f"{code} {_activity_time(item)}" for item, code in coded_items
        )
        staying_on_stage = (
            "x"
            if any(item.avm_day_wrap_minutes == 30 for item in shift.items)
            else ""
        )
        remarks = " / ".join(shift.flags) if shift.flags else "-"
        end_text = shift.end.strftime("%H:%M")
        rows.append(
            [
                day_text,
                f"{shift.start:%H:%M}-{end_text}",
                duration,
                ", ".join(event_codes),
                chronological,
                staying_on_stage,
                remarks,
            ]
        )
    _append_table(
        lines,
        [
            "Datum",
            "Tijd",
            "Duur",
            "events",
            "Chronologisch",
            "Overstaan",
            "Opmerking",
        ],
        rows,
    )
    lines.append("")


def render_text(schedule: ProductionSchedule, rules: dict | None = None) -> str:
    rules = rules or {}
    required_items = [
        item
        for item in schedule.items
        if item.avm_required_count >= 1
        and (item.avm_planning_level or "verplicht") == "verplicht"
    ]
    resolved_assignments = update_schedule_validation(schedule, rules)
    assigned_ids = {item.id for items in resolved_assignments.values() for item in items}
    assigned_source_ids = {item_id.split("#", maxsplit=1)[0] for item_id in assigned_ids}
    unassigned_items = [
        item for item in required_items if item.id not in assigned_source_ids
    ]

    display_status = schedule.planning_status
    if schedule.blocking_reasons:
        display_status = "invoer_nodig"
    elif (
        schedule.cao_conflicts
        or schedule.warnings
        or schedule.annotations
        or any(item.avm_status == "controleren" for item in schedule.items)
        or any(question.is_open for question in schedule.decision_questions)
    ):
        display_status = "concept_met_conflicten"
    else:
        display_status = "concept"
    status_text = {
        "ongeldig_cao": "CONCEPT — BEKENDE CAO-CONFLICTEN",
        "concept_met_conflicten": "CONCEPT — BEKENDE CONFLICTEN",
        "invoer_nodig": "CONCEPT — INVOER NODIG",
        "concept": "CONCEPT — HANDMATIGE CONTROLE NODIG",
        "concept_geldig_binnen_deelcontrole": (
            "CONCEPT — GELDIG BINNEN DE CONTROLEERBARE CAO-REGELS"
        ),
    }.get(display_status, "CONCEPT")
    lines = [
        "GEGENEREERDE AVM-PLANNING",
        f"Naam van de productie: {_short_production_name(schedule.title)}",
        f"Status: {status_text}",
        "CAO-controle: gedeeltelijk; een volledig persoonlijk rooster blijft vereist.",
        "Verdeling: AVM1 leidt; TEAM-AVM diensten lossen CAO-conflicten op.",
        "Belichten vereist één AVM'er en wordt flexibel over AVM1/AVM2 verdeeld.",
        "Dienstregel: standaard 09:00-17:00; uitloop wordt vanaf de werkelijke eindtijd berekend; uitzonderingen staan in de actieve regels.",
        "Legenda:",
        *COMPACT_ACTIVITY_LEGEND_LINES,
    ]
    if schedule.planning_start and schedule.planning_end:
        lines.append(
            f"Planningsperiode: {_format_day(schedule.planning_start)} t/m "
            f"{_format_day(schedule.planning_end)}"
        )
    if schedule.accountview_number:
        lines.append(f"Accountview nummer: {schedule.accountview_number}")
    lines.extend([f"Bron: {schedule.source_file}", ""])

    if schedule.blocking_reasons:
        lines.append("BLOKKERENDE PUNTEN")
        lines.extend(f"- {reason}" for reason in schedule.blocking_reasons)
        lines.append("")
    if schedule.cao_conflicts:
        lines.append("HARDE CAO-CONFLICTEN")
        lines.extend(f"- {conflict}" for conflict in schedule.cao_conflicts)
        lines.append("")

    for position in ("AVM1", "AVM2"):
        _append_person_roster(
            lines, schedule, position, rules, resolved_assignments.get(position, [])
        )
    for position, items in resolved_assignments.items():
        if position not in {"AVM1", "AVM2"} and items:
            _append_person_roster(lines, schedule, position, rules, items)

    if unassigned_items:
        lines.append("NOG TOE TE WIJZEN — AVM 1 OF AVM 2")
        for item in sorted(unassigned_items, key=lambda value: (value.day, value.start)):
            lines.append(
                f"{item.day:%d-%m-%Y} | {_activity_time(item)} | "
                f"{schedule.title or 'onbekend'} | {_activity_label(item.activity)}"
            )
        lines.append("")

    omitted_soft = [
        item
        for item in schedule.items
        if item.avm_planning_level in {"richtlijn", "gebruikelijk"}
        and item.avm_assignment_status == "niet_ingepland"
    ]
    if omitted_soft:
        lines.append("RICHTLIJNEN/GEBRUIKELIJKE MOMENTEN NIET INGEPLAND")
        for item in omitted_soft:
            lines.append(
                f"- {item.day:%d-%m-%Y} {item.activity}: "
                f"{item.avm_omission_reason or 'reden onbekend'}"
            )
        lines.append("")

    review_count = sum(item.avm_status == "controleren" for item in schedule.items)
    if review_count:
        lines.append("Niet in dit rooster opgenomen")
        lines.append(
            f"  {review_count} mogelijke AVM-activiteiten moeten nog worden beoordeeld; "
            "zie JSON/CSV."
        )
        lines.append("")

    return "\n".join(lines)


def write_text(
    schedule: ProductionSchedule, target: str | Path, rules: dict | None = None
) -> None:
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_text(schedule, rules), encoding="utf-8")


def render_daily_summary_text(schedule: ProductionSchedule) -> str:
    required_items = sorted(
        [item for item in schedule.items if item.avm_required_count >= 1],
        key=lambda value: (value.day, value.start),
    )
    items_by_day = defaultdict(list)
    for item in required_items:
        items_by_day[item.day].append(item)

    rows: list[list[str]] = []
    for day in sorted(items_by_day):
        day_items = sorted(items_by_day[day], key=lambda value: value.start)
        first_start = min(item.start for item in day_items)
        last_end = max(item.end or item.start for item in day_items)
        end_text = last_end.strftime("%H:%M")
        if last_end.date() != first_start.date():
            end_text += " (+1 dag)"
        duration_minutes = int((last_end - first_start).total_seconds() // 60)

        coded_items = [(item, _compact_activity_code(item.activity)) for item in day_items]
        summary_codes = [
            code
            for item, code in sorted(
                coded_items,
                key=lambda value: _event_sort_key(value[0], value[1]),
            )
        ]
        chronological = "; ".join(
            f"{code} {_activity_time(item)}" for item, code in coded_items
        )

        rows.append(
            [
                f"{DUTCH_DAYS_SHORT[day.weekday()]} {day:%d-%m-%Y}",
                f"{first_start:%H:%M}-{end_text}",
                _duration_text(duration_minutes),
                ", ".join(summary_codes),
                chronological,
            ]
        )

    lines = [_short_production_name(schedule.title), ""]
    _append_table(
        lines,
        ["Datum", "Tijd", "Duur", "events", "Chronologisch"],
        rows,
    )
    lines.append("")
    return "\n".join(lines)


def write_daily_summary_text(schedule: ProductionSchedule, target: str | Path) -> None:
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_daily_summary_text(schedule), encoding="utf-8")


def _staffing_text(item) -> str:
    if item.avm_optional and item.non_avm_allowed:
        return "0-1 AVM'er — niet-AVM-dekking toegestaan; maximaal 1 AVM tegelijk"
    if item.avm_required_count >= 2:
        return "2 AVM'ers — AVM1 + AVM2"
    if item.avm_preferred_position == "AVM1" and item.avm_flexible_positions:
        return "1 AVM'er — voorkeur AVM1, flexibel te verdelen"
    if item.avm_preferred_position == "AVM1":
        return "1 AVM'er — voorkeur AVM1"
    if item.avm_default_position == "AVM2":
        return "1 AVM'er — voorlopig AVM2"
    if item.avm_flexible_positions:
        maximum = (
            ", maximaal 1 tegelijk" if item.avm_maximum_count == 1 else ""
        )
        return f"1 AVM'er — flexibel te verdelen over AVM1/AVM2{maximum}"
    return "1 AVM'er — nog toe te wijzen"


def render_avm_events_text(schedule: ProductionSchedule) -> str:
    required = [
        item
        for item in schedule.items
        if item.avm_required_count >= 1
        and (item.avm_planning_level or "verplicht") == "verplicht"
    ]
    guidelines = [
        item for item in schedule.items if item.avm_planning_level == "richtlijn"
    ]
    customary = [
        item for item in schedule.items if item.avm_planning_level == "gebruikelijk"
    ]
    optional = [item for item in schedule.items if item.avm_status == "optioneel"]
    review = [item for item in schedule.items if item.avm_status == "controleren"]
    not_needed = [
        item
        for item in schedule.items
        if item.avm_required_count == 0
        and item.avm_status == "niet_gemarkeerd"
        and item.kind == "activiteit"
    ]
    production_name = _short_production_name(schedule.title)
    lines = [
        "ALLE EVENTS DIE VOOR AVM VAN TOEPASSING ZIJN",
        f"Naam van de productie: {production_name}",
        f"Bron: {schedule.source_file}",
        "Legenda:",
        *ACTIVITY_LEGEND_LINES,
        "",
        f"VERPLICHTE AVM-EVENTS ({len(required)})",
    ]
    _append_table(
        lines,
        ["Datum", "Tijd", "Locatie", "Activiteit", "Code", "Bezetting"],
        [
            [
                f"{DUTCH_DAYS_SHORT[item.day.weekday()]} {item.day:%d-%m-%Y}",
                _activity_time(item),
                item.location or "locatie NTB",
                item.activity,
                _event_activity_code(item.activity),
                _staffing_text(item),
            ]
            for item in sorted(required, key=lambda value: (value.day, value.start))
        ],
    )

    for heading, items in (
        ("RICHTLIJNEN — INPLANNEN ZOLANG HET KAN", guidelines),
        ("GEBRUIKELIJKE ROOSTERMOMENTEN", customary),
    ):
        lines.extend(["", f"{heading} ({len(items)})"])
        _append_table(
            lines,
            [
                "Datum",
                "Tijd",
                "Locatie",
                "Activiteit",
                "Status",
                "Reden",
            ],
            [
                [
                    f"{DUTCH_DAYS_SHORT[item.day.weekday()]} {item.day:%d-%m-%Y}",
                    _activity_time(item),
                    item.location or "locatie NTB",
                    item.activity,
                    item.avm_assignment_status or "nog niet berekend",
                    item.avm_omission_reason or "-",
                ]
                for item in sorted(items, key=lambda value: (value.day, value.start))
            ],
        )

    lines.extend(
        [
            "",
            f"OPTIONELE AVM-DEKKING / NIET-AVM TOEGESTAAN ({len(optional)})",
        ]
    )
    _append_table(
        lines,
        ["Datum", "Tijd", "Locatie", "Activiteit", "Code", "Dekking"],
        [
            [
                f"{DUTCH_DAYS_SHORT[item.day.weekday()]} {item.day:%d-%m-%Y}",
                _activity_time(item),
                item.location or "locatie NTB",
                item.activity,
                _event_activity_code(item.activity),
                _staffing_text(item),
            ]
            for item in sorted(optional, key=lambda value: (value.day, value.start))
        ],
    )

    lines.extend(
        [
            "",
            f"NOG TE BEOORDELEN AVM-KANDIDATEN ({len(review)})",
        ]
    )
    _append_table(
        lines,
        ["Datum", "Tijd", "Locatie", "Activiteit", "Code", "Reden"],
        [
            [
                f"{DUTCH_DAYS_SHORT[item.day.weekday()]} {item.day:%d-%m-%Y}",
                _activity_time(item),
                item.location or "locatie NTB",
                item.activity,
                _event_activity_code(item.activity),
                "; ".join(item.avm_reasons) or "AVM-relatie controleren",
            ]
            for item in sorted(review, key=lambda value: (value.day, value.start))
        ],
    )

    if schedule.annotations:
        lines.extend(["", "LOSSE AVM-BRONNOTITIES"])
        _append_table(
            lines,
            ["Datum", "Pagina", "Notitie", "Actie"],
            [
                [
                    f"{DUTCH_DAYS_SHORT[annotation.day.weekday()]} {annotation.day:%d-%m-%Y}",
                    str(annotation.page),
                    annotation.text,
                    "relatie met activiteit controleren",
                ]
                for annotation in schedule.annotations
            ],
        )

    if schedule.decision_questions:
        lines.extend(["", "CONDITIONELE VRAGEN"])
        _append_table(
            lines,
            ["Vraag-id", "Vraag", "Antwoord", "Bron", "Status"],
            [
                [
                    question.id,
                    question.prompt,
                    question.answer or "onbekend",
                    question.answer_source or "-",
                    "OPEN" if question.is_open else "beantwoord",
                ]
                for question in schedule.decision_questions
            ],
        )
    if schedule.planning_requirements:
        lines.extend(["", "CONDITIONELE PLANNINGVEREISTEN"])
        _append_table(
            lines,
            ["Vereiste", "Niveau", "Status", "Ontbreekt"],
            [
                [
                    requirement.description,
                    requirement.planning_level,
                    requirement.status,
                    ", ".join(requirement.missing_fields) or "-",
                ]
                for requirement in schedule.planning_requirements
            ],
        )

    lines.extend(
        [
            "",
            f"GEEN AVM NODIG ({len(not_needed)})",
        ]
    )
    _append_table(
        lines,
        ["Datum", "Tijd", "Locatie", "Activiteit", "Code", "Reden"],
        [
            [
                f"{DUTCH_DAYS_SHORT[item.day.weekday()]} {item.day:%d-%m-%Y}",
                _activity_time(item),
                item.location or "locatie NTB",
                _activity_with_details(item),
                _event_activity_code(item.activity),
                "; ".join(item.avm_reasons) or "Geen AVM-regel van toepassing",
            ]
            for item in sorted(not_needed, key=lambda value: (value.day, value.start))
        ],
    )
    lines.append("")
    return "\n".join(lines)


def write_avm_events_text(schedule: ProductionSchedule, target: str | Path) -> None:
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_avm_events_text(schedule), encoding="utf-8")


def render_issues_text(
    schedule: ProductionSchedule,
    status: str,
) -> str:
    lines = [
        "AANDACHTSPUNTEN CONCEPTROOSTER",
        f"Status: {status}",
        "Dit rooster is een concept en moet handmatig worden gecontroleerd "
        "voordat het in Excel wordt overgenomen.",
        "",
    ]
    sections: list[tuple[str, list[str]]] = [
        ("BLOKKERENDE INVOER", list(schedule.blocking_reasons)),
        ("CAO-CONFLICTEN", list(schedule.cao_conflicts)),
        ("WAARSCHUWINGEN", list(schedule.warnings)),
        (
            "OPEN VRAGEN",
            [
                f"[{question.id}] {question.prompt}"
                for question in schedule.decision_questions
                if question.is_open
            ],
        ),
        (
            "EVENTS NOG TE BEOORDELEN",
            [
                f"{item.day.isoformat()} {item.start:%H:%M} — {item.activity}"
                for item in schedule.items
                if item.avm_status == "controleren"
            ],
        ),
        (
            "LOSSE BRONNOTITIES",
            [
                f"{annotation.day.isoformat()} pagina {annotation.page} — "
                f"{annotation.text}"
                for annotation in schedule.annotations
            ],
        ),
    ]
    populated = False
    for heading, values in sections:
        if not values:
            continue
        populated = True
        lines.append(heading)
        lines.extend(f"- {value}" for value in values)
        lines.append("")
    if not populated:
        lines.extend(
            [
                "Geen bekende aandachtspunten.",
                "De controle blijft gedeeltelijk omdat het definitieve "
                "personeelsrooster buiten deze tool wordt gemaakt.",
                "",
            ]
        )
    return "\n".join(lines)


def write_issues_text(
    schedule: ProductionSchedule,
    target: str | Path,
    status: str,
) -> None:
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_issues_text(schedule, status), encoding="utf-8")
