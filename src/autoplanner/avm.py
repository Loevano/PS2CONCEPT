from __future__ import annotations

import json
import re
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from .models import (
    DecisionQuestion,
    PlanningItem,
    PlanningRequirement,
    ProductionSchedule,
)


def load_rules(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_answers(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Het antwoordenbestand moet een JSON-object bevatten.")
    return value


def _matches_activity(activity: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, activity, flags=re.IGNORECASE) for pattern in patterns)


def _matches_rule_context(schedule: ProductionSchedule, item, rule: dict) -> bool:
    checks = (
        ("activity_patterns", item.activity),
        ("location_patterns", item.location or ""),
        ("production_patterns", schedule.title or ""),
        ("search_patterns", " ".join([item.activity, *item.details])),
    )
    for key, value in checks:
        patterns = [str(pattern) for pattern in rule.get(key, [])]
        if patterns and not _matches_activity(value, patterns):
            return False

    exclusions = (
        ("exclude_activity_patterns", item.activity),
        ("exclude_location_patterns", item.location or ""),
        ("exclude_production_patterns", schedule.title or ""),
        ("exclude_search_patterns", " ".join([item.activity, *item.details])),
    )
    if any(
        patterns and _matches_activity(value, patterns)
        for key, value in exclusions
        if (patterns := [str(pattern) for pattern in rule.get(key, [])])
    ):
        return False

    if rule.get("only_first_matching_day"):
        base_rule = {
            key: value
            for key, value in rule.items()
            if key != "only_first_matching_day"
        }
        first_day = min(
            (
                candidate.day
                for candidate in schedule.items
                if _matches_rule_context(schedule, candidate, base_rule)
            ),
            default=None,
        )
        return item.day == first_day
    return True


def _first_scope_start(schedule: ProductionSchedule, scope: dict) -> datetime | None:
    location_patterns = [
        str(pattern) for pattern in scope.get("start_location_patterns", [])
    ]
    if not location_patterns:
        return None
    starts = [
        item.start
        for item in schedule.items
        if _matches_activity(item.location or "", location_patterns)
    ]
    return min(starts, default=None)


def _parse_clock(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def _normalise_answer(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("value")
    if value is True:
        return "ja"
    if value is False:
        return "nee"
    if value is None:
        return None
    answer = str(value).strip().casefold()
    return answer or None


def _schedule_search_text(schedule: ProductionSchedule) -> str:
    values = [schedule.title or ""]
    for item in schedule.items:
        values.extend([item.activity, item.location or "", *item.details])
    return " ".join(values)


def _question_applies(schedule: ProductionSchedule, question: dict) -> bool:
    production_patterns = [
        str(pattern) for pattern in question.get("production_patterns", [])
    ]
    return not production_patterns or _matches_activity(
        schedule.title or "", production_patterns
    )


def _resolve_questions(
    schedule: ProductionSchedule,
    rules: dict,
    answers: dict[str, Any],
) -> dict[str, str | None]:
    resolved: dict[str, str | None] = {}
    searchable = _schedule_search_text(schedule)
    schedule.decision_questions.clear()

    for definition in rules.get("conditional_questions", []):
        if not _question_applies(schedule, definition):
            continue
        question_id = str(definition["id"])
        raw_answer = answers.get(question_id)
        answer = _normalise_answer(raw_answer)
        answer_source = "antwoordbestand" if answer is not None else None
        if answer is None:
            evidence_patterns = [
                str(pattern)
                for pattern in definition.get("infer_yes_patterns", [])
            ]
            if evidence_patterns and _matches_activity(searchable, evidence_patterns):
                answer = "ja"
                answer_source = "productieplanning"

        choices = [str(choice).casefold() for choice in definition.get("choices", [])]
        if answer is not None and choices and answer not in choices:
            schedule.warnings.append(
                f"Ongeldig antwoord voor {question_id}: {answer!r}; "
                f"verwacht {', '.join(choices)}."
            )
            answer = None
            answer_source = None

        schedule.decision_questions.append(
            DecisionQuestion(
                id=question_id,
                prompt=str(definition["prompt"]),
                choices=choices,
                answer=answer,
                answer_source=answer_source,
                blocking=bool(definition.get("blocking", True)),
                explanation=definition.get("description"),
            )
        )
        resolved[question_id] = answer
    return resolved


def _answer_conditions_match(
    rule: dict, resolved_answers: dict[str, str | None]
) -> bool:
    return all(
        resolved_answers.get(str(question_id)) == _normalise_answer(expected)
        for question_id, expected in rule.get("answer_conditions", {}).items()
    )


def _datetime_from_answer(
    day_value: Any, clock_value: Any
) -> datetime | None:
    if day_value is None or clock_value is None:
        return None
    try:
        return datetime.combine(
            datetime.strptime(str(day_value), "%Y-%m-%d").date(),
            _parse_clock(str(clock_value)),
        )
    except ValueError:
        return None


def _apply_conditional_requirements(
    schedule: ProductionSchedule,
    rules: dict,
    answers: dict[str, Any],
    resolved_answers: dict[str, str | None],
) -> None:
    schedule.planning_requirements.clear()
    for rule in rules.get("conditional_requirements", []):
        if not _question_applies(schedule, rule):
            continue
        question_id = str(rule["question_id"])
        expected = _normalise_answer(rule.get("when", "ja"))
        if resolved_answers.get(question_id) != expected:
            continue

        existing = next(
            (
                item
                for item in schedule.items
                if _matches_rule_context(schedule, item, rule.get("existing_item", {}))
            ),
            None,
        )
        requirement_id = str(rule["id"])
        if existing is not None:
            schedule.planning_requirements.append(
                PlanningRequirement(
                    id=requirement_id,
                    description=str(rule["description"]),
                    planning_level=str(rule.get("planning_level", "verplicht")),
                    status="ingepland",
                    question_id=question_id,
                    related_item_id=existing.id,
                )
            )
            continue

        raw_answer = answers.get(question_id)
        details = raw_answer if isinstance(raw_answer, dict) else {}
        start = _datetime_from_answer(details.get("day"), details.get("start"))
        end = _datetime_from_answer(details.get("day"), details.get("end"))
        missing_fields = [
            field_name
            for field_name in ("day", "start", "end")
            if details.get(field_name) in (None, "")
        ]
        if start is None or end is None or end <= start:
            if not missing_fields:
                missing_fields = ["geldige day/start/end"]
            schedule.planning_requirements.append(
                PlanningRequirement(
                    id=requirement_id,
                    description=str(rule["description"]),
                    planning_level=str(rule.get("planning_level", "verplicht")),
                    status="planninggegevens_nodig",
                    question_id=question_id,
                    missing_fields=missing_fields,
                )
            )
            continue

        generated = rule.get("generated_item", {})
        item = PlanningItem(
            id=f"generated-{requirement_id}",
            day=start.date(),
            start=start,
            end=end,
            activity=str(generated.get("activity", rule["description"])),
            location=str(generated.get("location", "locatie NTB")),
            page=0,
            source_line=0,
            kind="activiteit",
            details=[str(generated.get("detail", "Conditioneel ingepland moment"))],
            generated_by_rule=requirement_id,
        )
        schedule.items.append(item)
        schedule.items.sort(key=lambda value: (value.day, value.start, value.id))
        schedule.planning_requirements.append(
            PlanningRequirement(
                id=requirement_id,
                description=str(rule["description"]),
                planning_level=str(rule.get("planning_level", "verplicht")),
                status="ingepland",
                question_id=question_id,
                related_item_id=item.id,
            )
        )


_PLANNING_LEVEL_STRENGTH = {
    "optioneel": 0,
    "gebruikelijk": 1,
    "richtlijn": 2,
    "verplicht": 3,
}


def _apply_planning_level(item, rule: dict) -> None:
    level = str(
        rule.get(
            "planning_level",
            "optioneel" if rule.get("optional_avm") else "verplicht",
        )
    )
    if level not in _PLANNING_LEVEL_STRENGTH:
        raise ValueError(f"Onbekend planning_level: {level}")
    current_strength = _PLANNING_LEVEL_STRENGTH.get(
        item.avm_planning_level or "", -1
    )
    if _PLANNING_LEVEL_STRENGTH[level] > current_strength:
        item.avm_planning_level = level


def _call_time_excluding_breaks(
    schedule: ProductionSchedule, item, working_minutes: int, break_minutes: dict
) -> datetime:
    call_time = item.start - timedelta(minutes=working_minutes)
    applicable_breaks = []
    for candidate in schedule.items:
        if candidate.day != item.day or candidate.kind != "pauze":
            continue
        duration = break_minutes.get(candidate.activity.casefold())
        if duration is not None:
            applicable_breaks.append((candidate.start, int(duration)))

    included = set()
    changed = True
    while changed:
        changed = False
        for break_start, duration in applicable_breaks:
            key = (break_start, duration)
            if key in included:
                continue
            if call_time <= break_start < item.start:
                call_time -= timedelta(minutes=duration)
                included.add(key)
                changed = True
    return call_time


def apply_avm_rules(
    schedule: ProductionSchedule,
    rules: dict,
    answers: dict[str, Any] | None = None,
) -> None:
    answers = answers or {}
    resolved_answers = _resolve_questions(schedule, rules, answers)
    _apply_conditional_requirements(
        schedule, rules, answers, resolved_answers
    )
    required_terms = [str(term).casefold() for term in rules.get("required_text", [])]
    review_terms = [str(term).casefold() for term in rules.get("review_text", [])]
    ignore_review_terms = [
        str(term).casefold() for term in rules.get("ignore_review_text", [])
    ]
    annotation_item_ids = {
        annotation.related_item_id
        for annotation in schedule.annotations
        if annotation.text.casefold() == "avm" and annotation.related_item_id
    }
    scope = rules.get("planning_scope", {})
    scope_start = _first_scope_start(schedule, scope)
    closing_rules = rules.get("shift_planning", {}).get("day_closing_rules", [])
    for day in {item.day for item in schedule.items}:
        day_items = [item for item in schedule.items if item.day == day]
        for closing_rule in closing_rules:
            marker = next(
                (
                    item
                    for item in day_items
                    if _matches_rule_context(schedule, item, closing_rule)
                ),
                None,
            )
            if marker is None:
                continue
            wrap_minutes = int(closing_rule["minutes_after_last_activity"])
            for item in day_items:
                item.avm_day_wrap_minutes = wrap_minutes
            break

    for item in schedule.items:
        searchable = " ".join([item.activity, *item.details]).casefold()
        required_hits = sorted({term for term in required_terms if term in searchable})
        review_hits = sorted({term for term in review_terms if term in searchable})
        ignore_review_hits = sorted(
            {term for term in ignore_review_terms if term in searchable}
        )
        scope_exception = _matches_activity(
            item.activity,
            [str(pattern) for pattern in scope.get("before_start_activity_patterns", [])],
        ) or _matches_activity(
            item.location or "",
            [str(pattern) for pattern in scope.get("before_start_location_patterns", [])],
        )
        outside_scope = (
            scope_start is not None
            and item.day < scope_start.date()
            and not scope_exception
        )
        exclusion = next(
            (
                rule
                for rule in rules.get("exclusion_rules", [])
                if _matches_rule_context(schedule, item, rule)
            ),
            None,
        )
        if outside_scope:
            item.avm_reasons.append(
                "Buiten AVM-roosterperiode: vóór de dag van de eerste Hoofdtoneel-activiteit"
            )
            continue
        if exclusion is not None:
            item.avm_reasons.append(
                "Geen AVM volgens uitsluiting: "
                + str(exclusion.get("id", "zonder-id"))
            )
            continue

        for staffing_rule in rules.get("staffing_rules", []):
            if (
                _answer_conditions_match(staffing_rule, resolved_answers)
                and _matches_rule_context(schedule, item, staffing_rule)
            ):
                item.avm_required_count = max(
                    item.avm_required_count, int(staffing_rule["required_count"])
                )
                _apply_planning_level(item, staffing_rule)
                if staffing_rule.get("maximum_count") is not None:
                    item.avm_maximum_count = int(staffing_rule["maximum_count"])
                item.avm_optional = bool(staffing_rule.get("optional_avm", False))
                item.non_avm_allowed = bool(
                    staffing_rule.get("non_avm_allowed", False)
                )
                if staffing_rule.get("preferred_position"):
                    item.avm_preferred_position = str(
                        staffing_rule["preferred_position"]
                    )
                if staffing_rule.get("default_position"):
                    item.avm_default_position = str(staffing_rule["default_position"])
                if staffing_rule.get("flexible_positions"):
                    item.avm_flexible_positions = [
                        str(position) for position in staffing_rule["flexible_positions"]
                    ]
                item.avm_reasons.append(
                    "Bezettingsregel: " + str(staffing_rule.get("id", "zonder-id"))
                )
                if staffing_rule.get("manual_check"):
                    item.avm_reasons.append(
                        "Handmatig controleren: " + str(staffing_rule["manual_check"])
                    )

        for location_rule in rules.get("location_staffing_rules", []):
            location = item.location or ""
            if not _matches_activity(
                location,
                [str(value) for value in location_rule.get("location_patterns", [])],
            ):
                continue
            if location_rule.get("apply_when_avm_required") and item.avm_required_count < 1:
                continue
            excluded = _matches_activity(
                item.activity,
                [
                    str(value)
                    for value in location_rule.get("exclude_activity_patterns", [])
                ],
            )
            if excluded:
                continue
            item.avm_required_count = max(
                item.avm_required_count, int(location_rule["required_count"])
            )
            item.avm_reasons.append(
                "Locatiebezettingsregel: "
                + str(location_rule.get("id", "zonder-id"))
            )

        for call_rule in rules.get("call_time_rules", []):
            if not _matches_rule_context(schedule, item, call_rule):
                continue
            if "working_minutes_before" in call_rule:
                item.avm_call_time = _call_time_excluding_breaks(
                    schedule,
                    item,
                    int(call_rule["working_minutes_before"]),
                    {
                        str(name).casefold(): int(minutes)
                        for name, minutes in call_rule.get(
                            "excluded_break_minutes", {}
                        ).items()
                    },
                )
            elif "minutes_before" in call_rule:
                item.avm_call_time = item.start - timedelta(
                    minutes=int(call_rule["minutes_before"])
                )
            else:
                if item.start.time() != _parse_clock(str(call_rule["activity_start"])):
                    continue
                item.avm_call_time = datetime.combine(
                    item.day, _parse_clock(str(call_rule["call_time"]))
                )
            item.avm_reasons.append(
                "Aanwezigheidsregel: " + str(call_rule.get("id", "zonder-id"))
            )

        for adjustment in rules.get("call_time_adjustments", []):
            if item.avm_call_time is None:
                continue
            if item.avm_call_time.time() != _parse_clock(str(adjustment["from"])):
                continue
            item.avm_call_time = datetime.combine(
                item.avm_call_time.date(), _parse_clock(str(adjustment["to"]))
            )
            item.avm_reasons.append(
                "Dienststartcorrectie: " + str(adjustment.get("id", "zonder-id"))
            )

        if item.avm_required_count > 0:
            item.avm_status = {
                "verplicht": "vereist",
                "richtlijn": "richtlijn",
                "gebruikelijk": "gebruikelijk",
                "optioneel": "optioneel",
            }.get(item.avm_planning_level or "verplicht", "vereist")
        elif item.avm_optional:
            item.avm_status = "optioneel"
            item.avm_planning_level = item.avm_planning_level or "optioneel"
        elif required_hits:
            item.avm_status = "vereist"
            item.avm_required_count = 1
            item.avm_planning_level = "verplicht"
            item.avm_reasons.append(
                "Expliciete AVM-regel: " + ", ".join(required_hits)
            )
        elif review_hits and not ignore_review_hits:
            item.avm_status = "controleren"
            item.avm_reasons.append(
                "Mogelijke AVM-term: " + ", ".join(review_hits)
            )
        elif review_hits and ignore_review_hits:
            item.avm_reasons.append(
                "Geen AVM nodig volgens uitsluiting: " + ", ".join(ignore_review_hits)
            )

        if item.id in annotation_item_ids and item.avm_status != "vereist":
            item.avm_status = "controleren"
            item.avm_reasons.append(
                "Losse AVM-notitie staat nabij dit item; relatie is door PDF-opmaak onzeker."
            )
