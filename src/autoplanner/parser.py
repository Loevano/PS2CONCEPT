from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

from .models import PlanningItem, ProductionSchedule, SourceAnnotation


DUTCH_MONTHS = {
    "januari": 1,
    "februari": 2,
    "maart": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "augustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}

DUTCH_MONTHS_SHORT = {
    "jan": 1,
    "feb": 2,
    "mrt": 3,
    "apr": 4,
    "mei": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "okt": 10,
    "nov": 11,
    "dec": 12,
}

ENGLISH_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

ENGLISH_MONTHS_SHORT = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

MONTHS = {**DUTCH_MONTHS, **ENGLISH_MONTHS}
MONTHS_SHORT = {**DUTCH_MONTHS_SHORT, **ENGLISH_MONTHS_SHORT}

DAY_RE = re.compile(
    r"^(?:maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+"
    r"(\d{1,2})\s+([a-zé]+)\s+(\d{4})(?:\s+.*)?$",
    re.IGNORECASE,
)
INTERVAL_RE = re.compile(
    r"^(\d{1,2})[.:](\d{2})\s*-\s*(\d{1,2})[.:](\d{2})\s+(.+)$"
)
POINT_RE = re.compile(r"^(\d{1,2})[.:](\d{2})\s+(.+)$")
TRAILING_POINT_RE = re.compile(
    r"^(Lunch break|Dinner break)\s*(\d{1,2})[.:](\d{2})$",
    re.IGNORECASE,
)
PLANNING_PERIOD_RE = re.compile(
    r"(?:Planningsperiode|Schedule period):\s*"
    r"(\d{1,2})\s+([a-z]{3})\s+(\d{4})\s*-\s*"
    r"(\d{1,2})\s+([a-z]{3})\s+(\d{4})",
    re.IGNORECASE,
)

LOCATION_PATTERNS = (
    (r"Main Stage", "Hoofdtoneel"),
    (r"Hoofdtoneel", "Hoofdtoneel"),
    (r"Grote Studio", "Grote Studio"),
    (r"Operastudio(?:\s+\d+)?", None),
    (r"STUDIO EXTERN,?", None),
    (r"Repetitieruimte(?:\s+.+)?", None),
    (r"Vergaderruimte\s+.+", None),
    (r"Stemkamer\s+\d+", None),
    (r"Dress room\s+\d+", None),
    (r"Construction Stage", None),
    (r"Orchestra pit", None),
    (r"Het Concertgebouw,?", None),
    (r"Bouwruimte\s+.+", None),
    (r"KLIMAATKAMER", None),
    (r"Muziektheater", None),
    (r"Montagehal", None),
    (r"Vip Room", None),
    (r"Souterrain", None),
    (r"Atrium", None),
    (r"Foyer", None),
    (r"Studio", None),
)

PRODUCTION_TITLE_RE = re.compile(
    r"^(?:HNB|DNO)\s+\d+(?:\s+-)?\s+.+$",
    re.IGNORECASE,
)

ACTIVITY_TRANSLATIONS = (
    (r"Final dress rehearsal", "Generale repetitie"),
    (r"Orchestra dress rehearsal", "Voorgenerale orkest"),
    (r"Piano dress rehearsal", "Piano toneelrepetitie"),
    (r"Piano stage\s*rehearsal", "Piano toneelrepetitie"),
    (r"Cd stage\s*rehearsal", "Cd toneelrepetitie"),
    (r"Stage and orchestra rehearsal", "Orkesttoneelrepetitie"),
    (r"Orchestra stage rehearsal", "Orkesttoneelrepetitie"),
    (r"Orchestra rehearsal", "Orkestrepetitie"),
    (r"Soloists rehearsal", "Solistenrepetitie"),
    (r"Music rehearsal principals", "Solistenrepetitie"),
    (r"Production rehearsal", "Regierepetitie"),
    (r"Technical rehearsal", "Technische repetitie"),
    (r"Techn time", "Technische tijd"),
    (r"School performance", "Schoolvoorstelling"),
    (r"Performance", "Voorstelling"),
    (r"Presentation to cast\s*&\s*house", "Presentatie cast & huis"),
    (r"Pre-set up of scenes and lights", "Opbouwen/voorbereiden belichten"),
    (r"Pre-set up", "Opbouwen/voorbereiden"),
    (r"Focussing|Focusing", "Richten licht"),
    (r"Break down", "Afbouw"),
    (r"Bauprobe", "Proefbouw"),
    (r"Lights", "Belichten"),
    (r"Lunch break", "Lunchpauze"),
    (r"Dinner break", "Dinerpauze"),
    (r"Close", "Afsluiten"),
)


def _parse_clock(hour: str, minute: str) -> time:
    hour_number = int(hour)
    minute_number = int(minute)
    if not 0 <= hour_number <= 23 or not 0 <= minute_number <= 59:
        raise ValueError(f"Ongeldige tijd: {hour}.{minute}")
    return time(hour_number, minute_number)


def _parse_day(match: re.Match[str]) -> date:
    month_name = match.group(2).lower()
    return date(int(match.group(3)), MONTHS[month_name], int(match.group(1)))


def _parse_period(text: str) -> tuple[date | None, date | None]:
    match = PLANNING_PERIOD_RE.search(text)
    if not match:
        return None, None
    start = date(
        int(match.group(3)), MONTHS_SHORT[match.group(2).lower()], int(match.group(1))
    )
    end = date(
        int(match.group(6)), MONTHS_SHORT[match.group(5).lower()], int(match.group(4))
    )
    return start, end


def _is_header_or_footer(line: str) -> bool:
    return bool(
        line.startswith("Gemaakt door:")
        or line.startswith("Created by:")
        or line.startswith("Accountview nummer:")
        or line.startswith("Accounting ID:")
        or line.startswith("Planningsperiode:")
        or line.startswith("Schedule period:")
        or line == "Dit schema kan worden gewijzigd"
        or line == "This schedule can be subject to change"
        or re.match(
            r"^(?:HNB|DNO)/\d{2}-\d{2}"
            r"(?:\s+(?:HNB|DNO)\s+\d+(?:\s+-)?\s+.*)?$",
            line,
        )
        or PRODUCTION_TITLE_RE.match(line)
        or re.match(r"^Pagina\s+\d+\s+van\s+\d+$", line)
        or re.match(r"^Page\s+\d+\s+of\s+\d+$", line)
    )


def _location(line: str) -> str | None:
    availability_match = re.fullmatch(
        r"(.+?)\s+Not Available:",
        line,
        flags=re.IGNORECASE,
    )
    if availability_match:
        return _location(availability_match.group(1))
    for pattern, canonical in LOCATION_PATTERNS:
        if re.fullmatch(pattern, line, flags=re.IGNORECASE):
            return canonical or line.rstrip(",")
    return None


def _split_trailing_location(value: str) -> tuple[str, str | None]:
    for pattern, canonical in LOCATION_PATTERNS:
        if pattern == r"Studio":
            continue
        match = re.search(
            rf"^(?P<activity>.+?)\s+(?P<location>{pattern})$",
            value,
            flags=re.IGNORECASE,
        )
        if match:
            location = canonical or match.group("location").rstrip(",")
            return match.group("activity").strip(), location
    return value, None


def _normalise_activity(value: str) -> str:
    for pattern, replacement in ACTIVITY_TRANSLATIONS:
        match = re.match(
            rf"^(?:{pattern})(?P<suffix>(?:\s+.*)?)$",
            value,
            flags=re.IGNORECASE,
        )
        if match:
            return replacement + match.group("suffix")
    return value


def _kind_for(activity: str, has_end: bool) -> str:
    lowered = activity.casefold()
    if "pauze" in lowered:
        return "pauze"
    if not has_end:
        return "tijdmarkering"
    return "activiteit"


def _metadata(page_texts: list[str]) -> tuple[str | None, date | None, date | None, str | None]:
    first_page = page_texts[0] if page_texts else ""
    lines = [line.strip() for line in first_page.splitlines() if line.strip()]
    title = next((line for line in lines if PRODUCTION_TITLE_RE.match(line)), None)
    account_match = re.search(
        r"(?:Accountview nummer|Accounting ID):\s*(\d+)",
        first_page,
        flags=re.IGNORECASE,
    )
    start, end = _parse_period(first_page)
    return title, start, end, account_match.group(1) if account_match else None


def parse_page_texts(page_texts: Iterable[str], source_file: str = "<memory>") -> ProductionSchedule:
    pages = list(page_texts)
    title, planning_start, planning_end, accountview_number = _metadata(pages)
    items: list[PlanningItem] = []
    annotations: list[SourceAnnotation] = []
    warnings: list[str] = []
    current_day: date | None = None
    current_location: str | None = None
    current_item: PlanningItem | None = None

    for page_number, page_text in enumerate(pages, start=1):
        current_location = None
        current_item = None
        for line_number, raw_line in enumerate(page_text.splitlines(), start=1):
            line = " ".join(raw_line.split())
            if not line or _is_header_or_footer(line):
                continue

            day_match = DAY_RE.match(line)
            if day_match:
                current_day = _parse_day(day_match)
                current_location = None
                current_item = None
                continue

            if current_day is None:
                continue

            location = _location(line)
            if location:
                if current_item is not None and current_item.location is None:
                    current_item.location = location
                    current_location = None
                else:
                    current_location = location
                    current_item = None
                continue

            interval_match = INTERVAL_RE.match(line)
            if interval_match:
                start_clock = _parse_clock(interval_match.group(1), interval_match.group(2))
                end_clock = _parse_clock(interval_match.group(3), interval_match.group(4))
                start = datetime.combine(current_day, start_clock)
                end = datetime.combine(current_day, end_clock)
                if end <= start:
                    end += timedelta(days=1)
                activity, inline_location = _split_trailing_location(
                    interval_match.group(5).strip()
                )
                activity = _normalise_activity(activity)
                current_item = PlanningItem(
                    id=f"p{page_number}-l{line_number}",
                    day=current_day,
                    start=start,
                    end=end,
                    activity=activity,
                    location=inline_location or current_location,
                    page=page_number,
                    source_line=line_number,
                    kind=_kind_for(activity, has_end=True),
                )
                items.append(current_item)
                continue

            point_match = POINT_RE.match(line)
            if point_match:
                start_clock = _parse_clock(point_match.group(1), point_match.group(2))
                activity, inline_location = _split_trailing_location(
                    point_match.group(3).strip()
                )
                activity = _normalise_activity(activity)
                current_item = PlanningItem(
                    id=f"p{page_number}-l{line_number}",
                    day=current_day,
                    start=datetime.combine(current_day, start_clock),
                    end=None,
                    activity=activity,
                    location=inline_location or current_location,
                    page=page_number,
                    source_line=line_number,
                    kind=_kind_for(activity, has_end=False),
                )
                items.append(current_item)
                continue

            trailing_point_match = TRAILING_POINT_RE.match(line)
            if trailing_point_match:
                start_clock = _parse_clock(
                    trailing_point_match.group(2),
                    trailing_point_match.group(3),
                )
                activity = _normalise_activity(trailing_point_match.group(1))
                current_item = PlanningItem(
                    id=f"p{page_number}-l{line_number}",
                    day=current_day,
                    start=datetime.combine(current_day, start_clock),
                    end=None,
                    activity=activity,
                    location=current_location,
                    page=page_number,
                    source_line=line_number,
                    kind=_kind_for(activity, has_end=False),
                )
                items.append(current_item)
                continue

            if line == "AVM":
                annotations.append(
                    SourceAnnotation(
                        text=line,
                        day=current_day,
                        page=page_number,
                        source_line=line_number,
                        related_item_id=current_item.id if current_item else None,
                    )
                )
                continue

            if current_item is not None:
                current_item.details.append(line)

    if not items:
        warnings.append("Geen tijdgebonden planningregels gevonden.")
    if annotations:
        warnings.append(
            "Losse AVM-bronannotaties zijn niet automatisch aan een activiteit toegewezen; "
            "controleer de PDF-opmaak."
        )

    return ProductionSchedule(
        source_file=source_file,
        title=title,
        planning_start=planning_start,
        planning_end=planning_end,
        accountview_number=accountview_number,
        items=items,
        annotations=annotations,
        warnings=warnings,
    )


def extract_schedule(pdf_path: str | Path) -> ProductionSchedule:
    path = Path(pdf_path)
    reader = PdfReader(path)
    page_texts = [page.extract_text() or "" for page in reader.pages]
    return parse_page_texts(page_texts, source_file=str(path))
