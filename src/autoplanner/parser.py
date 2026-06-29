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

DAY_RE = re.compile(
    r"^(?:maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag)\s+"
    r"(\d{1,2})\s+([a-zé]+)\s+(\d{4})(?:\s+.*)?$",
    re.IGNORECASE,
)
INTERVAL_RE = re.compile(
    r"^(\d{1,2})[.:](\d{2})\s*-\s*(\d{1,2})[.:](\d{2})\s+(.+)$"
)
POINT_RE = re.compile(r"^(\d{1,2})[.:](\d{2})\s+(.+)$")
PLANNING_PERIOD_RE = re.compile(
    r"Planningsperiode:\s*(\d{1,2})\s+([a-z]{3})\s+(\d{4})\s*-\s*"
    r"(\d{1,2})\s+([a-z]{3})\s+(\d{4})",
    re.IGNORECASE,
)

KNOWN_LOCATIONS = (
    "Hoofdtoneel",
    "Foyer",
    "Grote Studio",
    "Studio",
    "Repetitieruimte",
    "Muziektheater",
    "Montagehal",
)

PRODUCTION_TITLE_RE = re.compile(r"^(?:HNB|DNO)\s+\d+\s+-\s+.+$", re.IGNORECASE)


def _parse_clock(hour: str, minute: str) -> time:
    hour_number = int(hour)
    minute_number = int(minute)
    if not 0 <= hour_number <= 23 or not 0 <= minute_number <= 59:
        raise ValueError(f"Ongeldige tijd: {hour}.{minute}")
    return time(hour_number, minute_number)


def _parse_day(match: re.Match[str]) -> date:
    month_name = match.group(2).lower()
    return date(int(match.group(3)), DUTCH_MONTHS[month_name], int(match.group(1)))


def _parse_period(text: str) -> tuple[date | None, date | None]:
    match = PLANNING_PERIOD_RE.search(text)
    if not match:
        return None, None
    start = date(
        int(match.group(3)), DUTCH_MONTHS_SHORT[match.group(2).lower()], int(match.group(1))
    )
    end = date(
        int(match.group(6)), DUTCH_MONTHS_SHORT[match.group(5).lower()], int(match.group(4))
    )
    return start, end


def _is_header_or_footer(line: str) -> bool:
    return bool(
        line.startswith("Gemaakt door:")
        or line.startswith("Accountview nummer:")
        or line.startswith("Planningsperiode:")
        or line == "Dit schema kan worden gewijzigd"
        or re.match(
            r"^(?:HNB|DNO)/\d{2}-\d{2}(?:\s+(?:HNB|DNO)\s+\d+\s+-\s+.*)?$",
            line,
        )
        or PRODUCTION_TITLE_RE.match(line)
        or re.match(r"^Pagina\s+\d+\s+van\s+\d+$", line)
    )


def _looks_like_location(line: str) -> bool:
    return line.casefold().startswith(
        tuple(location.casefold() for location in KNOWN_LOCATIONS)
    )


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
    account_match = re.search(r"Accountview nummer:\s*(\d+)", first_page)
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

            if _looks_like_location(line):
                current_location = line
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
                current_item = PlanningItem(
                    id=f"p{page_number}-l{line_number}",
                    day=current_day,
                    start=start,
                    end=end,
                    activity=interval_match.group(5).strip(),
                    location=current_location,
                    page=page_number,
                    source_line=line_number,
                    kind=_kind_for(interval_match.group(5), has_end=True),
                )
                items.append(current_item)
                continue

            point_match = POINT_RE.match(line)
            if point_match:
                start_clock = _parse_clock(point_match.group(1), point_match.group(2))
                current_item = PlanningItem(
                    id=f"p{page_number}-l{line_number}",
                    day=current_day,
                    start=datetime.combine(current_day, start_clock),
                    end=None,
                    activity=point_match.group(3).strip(),
                    location=current_location,
                    page=page_number,
                    source_line=line_number,
                    kind=_kind_for(point_match.group(3), has_end=False),
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
