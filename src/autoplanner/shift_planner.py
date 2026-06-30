from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
import re

from .models import PlanningItem, ProductionSchedule


TEAM_REASON_PREFIX = "TEAM-OVERNAME-REDEN: "


def _minutes_as_prose(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    if remainder == 0:
        return f"{hours} uur"
    return f"{hours} uur {remainder} min"


@dataclass
class DailyShift:
    position: str
    day: date
    start: datetime
    end: datetime
    items: list[PlanningItem]
    target_minutes: int = 480
    target_fill_minutes: int = 0
    target_fill_after_minutes: int = 0
    flags: list[str] = field(default_factory=list)

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


def _estimated_span_minutes(items: list[PlanningItem], rules: dict) -> int:
    if not items:
        return 0
    shift_rules = rules.get("shift_planning", {})
    start, end, _ = _planned_bounds(items, shift_rules)
    return int((end - start).total_seconds() // 60)


def _at(day: date, clock: str) -> datetime:
    minutes = _clock_minutes(clock)
    return datetime.combine(day, time(minutes // 60, minutes % 60))


def _round_shift_bounds(
    start: datetime, end: datetime, shift_rules: dict
) -> tuple[datetime, datetime]:
    interval = int(shift_rules.get("round_shift_boundaries_minutes", 0))
    if interval <= 0:
        return start, end

    start_minutes = start.hour * 60 + start.minute
    rounded_start_minutes = start_minutes - (start_minutes % interval)
    rounded_start = datetime.combine(start.date(), time()) + timedelta(
        minutes=rounded_start_minutes
    )

    end_day_start = datetime.combine(end.date(), time())
    end_minutes = end.hour * 60 + end.minute
    rounded_end_minutes = ((end_minutes + interval - 1) // interval) * interval
    rounded_end = end_day_start + timedelta(minutes=rounded_end_minutes)
    return rounded_start, rounded_end


def _activity_buffer_minutes(
    item: PlanningItem, shift_rules: dict
) -> tuple[int, int, bool]:
    before = int(shift_rules.get("activity_buffer_before_minutes", 60))
    after = int(shift_rules.get("activity_buffer_after_minutes", 60))
    preserve_after = False
    for rule in shift_rules.get("activity_buffer_rules", []):
        patterns = [str(pattern) for pattern in rule.get("activity_patterns", [])]
        if not patterns or not _matches_patterns(item.activity, patterns):
            continue
        before = int(rule.get("before_minutes", before))
        after = int(rule.get("after_minutes", after))
        preserve_after = bool(rule.get("preserve_after_minutes", False))
        break
    return before, after, preserve_after


def _preserve_required_window(
    items: list[PlanningItem], shift_rules: dict
) -> bool:
    for item in items:
        for rule_group in ("activity_buffer_rules", "special_shift_rules"):
            for rule in shift_rules.get(rule_group, []):
                if not rule.get("preserve_required_window"):
                    continue
                patterns = [str(pattern) for pattern in rule.get("activity_patterns", [])]
                if patterns and _matches_patterns(item.activity, patterns):
                    return True
    return False


def _required_window(
    items: list[PlanningItem], shift_rules: dict
) -> tuple[datetime, datetime, tuple[datetime, datetime] | None]:
    windows = []
    special_base = None
    for item in items:
        item_end = item.end or item.start
        special_window = None
        for rule in shift_rules.get("special_shift_rules", []):
            patterns = [str(pattern) for pattern in rule.get("activity_patterns", [])]
            if not any(
                re.search(pattern, item.activity, flags=re.IGNORECASE)
                for pattern in patterns
            ):
                continue
            weekdays = [int(value) for value in rule.get("weekdays", [])]
            if weekdays and item.day.weekday() not in weekdays:
                continue
            maximum_matching = rule.get("maximum_matching_activities")
            if maximum_matching is not None:
                matching_count = sum(
                    1
                    for candidate in items
                    if _matches_patterns(candidate.activity, patterns)
                )
                if matching_count > int(maximum_matching):
                    continue
            if rule.get("activity_start") and item.start.strftime("%H:%M") != str(
                rule["activity_start"]
            ):
                continue
            if rule.get("require_end_to_cover_activity_buffer") and "end" in rule:
                _, required_after, preserve_after = _activity_buffer_minutes(
                    item, shift_rules
                )
                if item.avm_day_wrap_minutes is not None and not preserve_after:
                    required_after = item.avm_day_wrap_minutes
                fixed_end = _at(item.day, str(rule["end"]))
                if fixed_end < item_end + timedelta(minutes=required_after):
                    continue
            if rule.get("use_avm_call_time") and item.avm_call_time is not None:
                if "end" in rule:
                    planned_end = _at(item.day, str(rule["end"]))
                elif "end_after_activity_minutes" in rule:
                    planned_end = item_end + timedelta(
                        minutes=int(rule["end_after_activity_minutes"])
                    )
                else:
                    planned_end = item.start + timedelta(
                        minutes=int(rule["end_offset_minutes"])
                    )
                candidate = (
                    item.avm_call_time,
                    planned_end,
                )
            elif "start_offset_minutes" in rule and (
                "end_offset_minutes" in rule
                or "end_after_activity_minutes" in rule
            ):
                candidate = (
                    item.start + timedelta(minutes=int(rule["start_offset_minutes"])),
                    (
                        item_end
                        + timedelta(minutes=int(rule["end_after_activity_minutes"]))
                        if "end_after_activity_minutes" in rule
                        else item.start
                        + timedelta(minutes=int(rule["end_offset_minutes"]))
                    ),
                )
            elif "start" in rule and "end_after_activity_minutes" in rule:
                candidate = (
                    _at(item.day, str(rule["start"])),
                    item_end
                    + timedelta(minutes=int(rule["end_after_activity_minutes"])),
                )
            else:
                candidate = (
                    _at(item.day, str(rule["start"])),
                    _at(item.day, str(rule["end"])),
                )
            if (
                item.avm_day_wrap_minutes is not None
                and item.end is not None
                and not rule.get("preserve_end")
            ):
                candidate = (
                    candidate[0],
                    item.end + timedelta(minutes=item.avm_day_wrap_minutes),
                )
            special_window = candidate
            special_base = candidate
            break
        before, after, preserve_after = _activity_buffer_minutes(item, shift_rules)
        if item.avm_day_wrap_minutes is not None and not preserve_after:
            after = item.avm_day_wrap_minutes
        windows.append(
            special_window
            or (
                item.avm_call_time
                if item.avm_call_time is not None
                else item.start - timedelta(minutes=before),
                item_end + timedelta(minutes=after),
            )
        )
    return min(window[0] for window in windows), max(window[1] for window in windows), special_base


def _double_performance_rule(
    items: list[PlanningItem], shift_rules: dict
) -> dict | None:
    rule = shift_rules.get("double_performance_rule")
    if not rule:
        return None
    patterns = [str(pattern) for pattern in rule.get("activity_patterns", [])]
    matching_count = sum(
        1 for item in items if patterns and _matches_patterns(item.activity, patterns)
    )
    return rule if matching_count >= int(rule.get("minimum_count", 2)) else None


def _planned_bounds(
    items: list[PlanningItem], shift_rules: dict
) -> tuple[datetime, datetime, int]:
    day = items[0].day
    required_start, required_end, special_base = _required_window(items, shift_rules)
    if special_base:
        base_start, base_end = special_base
    else:
        base_start = _at(day, str(shift_rules.get("default_shift_start", "09:00")))
        base_end = _at(day, str(shift_rules.get("default_shift_end", "17:00")))
    target_minutes = int(shift_rules.get("target_minutes", 480))

    double_rule = _double_performance_rule(items, shift_rules)
    maximum_minutes = int(shift_rules.get("maximum_shift_minutes", 720))
    required_span = int((required_end - required_start).total_seconds() // 60)
    if (
        double_rule
        and double_rule.get("cap_at_maximum_shift", True)
        and required_span > maximum_minutes
    ):
        _, rounded_end = _round_shift_bounds(required_end, required_end, shift_rules)
        return (
            rounded_end - timedelta(minutes=maximum_minutes),
            rounded_end,
            target_minutes,
        )

    if _preserve_required_window(items, shift_rules):
        start, end = _round_shift_bounds(required_start, required_end, shift_rules)
        return start, end, target_minutes

    if base_start <= required_start and required_end <= base_end:
        start, end = _round_shift_bounds(base_start, base_end, shift_rules)
        return start, end, target_minutes

    if required_span > target_minutes:
        start, end = _round_shift_bounds(required_start, required_end, shift_rules)
        return start, end, target_minutes

    earliest_possible_start = required_end - timedelta(minutes=target_minutes)
    latest_possible_start = required_start
    shifted_start = max(earliest_possible_start, min(base_start, latest_possible_start))
    start, end = _round_shift_bounds(
        shifted_start,
        shifted_start + timedelta(minutes=target_minutes),
        shift_rules,
    )
    return start, end, target_minutes


def _assignment_score(items: list[PlanningItem], rules: dict) -> tuple[int, int, int]:
    shift_rules = rules.get("shift_planning", {})
    maximum = int(shift_rules.get("maximum_shift_minutes", 720))
    start, end, target = _planned_bounds(items, shift_rules)
    span = int((end - start).total_seconds() // 60)
    return max(0, span - maximum), abs(span - target), len(items)


def _matches_patterns(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _team_replacement_flag(shift: DailyShift, overflow: dict) -> str | None:
    label = str(overflow.get("replacement_label", "TEAM-AVM"))
    patterns = [str(pattern) for pattern in overflow.get("replaceable_activity_patterns", [])]
    if not patterns:
        return f"{label} OVERNAME NODIG"

    activity_names = []
    seen = set()
    for item in shift.items:
        if not _matches_patterns(item.activity, patterns):
            continue
        key = item.activity.casefold()
        if key in seen:
            continue
        activity_names.append(item.activity)
        seen.add(key)

    if not activity_names:
        return None
    return f"{label} OVERNAME NODIG VOOR: {', '.join(activity_names)}"


def _team_replacement_reason(position: str, shift: DailyShift) -> str:
    conflicts = [
        flag.removeprefix("CAO-CONFLICT: ").strip()
        for flag in shift.flags
        if flag.startswith("CAO-CONFLICT: ")
    ]
    if conflicts:
        return f"TEAM-overname van {position}: {'; '.join(conflicts)}"
    return (
        f"TEAM-overname van {position}: nodig om een vastgesteld conflict "
        "met dagduur of nachtrust op te lossen"
    )


def _items_on_day(items: list[PlanningItem], day: date) -> list[PlanningItem]:
    return [item for item in items if item.day == day]


def _split_flexible_item(item: PlanningItem) -> tuple[PlanningItem, PlanningItem]:
    if item.end is None:
        return item, item
    midpoint = item.start + (item.end - item.start) / 2
    first = replace(item, id=f"{item.id}#deel1", end=midpoint)
    second = replace(item, id=f"{item.id}#deel2", start=midpoint)
    return first, second


def build_assignments(
    schedule: ProductionSchedule, rules: dict | None = None
) -> dict[str, list[PlanningItem]]:
    rules = rules or {}
    target = int(rules.get("shift_planning", {}).get("target_minutes", 480))
    assignments: dict[str, list[PlanningItem]] = {"AVM1": [], "AVM2": []}
    flexible = []
    optional = []
    soft = []

    for item in schedule.items:
        item.avm_assignment_status = None
        item.avm_omission_reason = None
        if item.avm_planning_level in {"richtlijn", "gebruikelijk"}:
            soft.append(item)
            continue
        if item.avm_required_count >= 2:
            assignments["AVM1"].append(item)
            assignments["AVM2"].append(item)
            item.avm_assignment_status = "ingepland"
        elif item.avm_optional:
            optional.append(item)
        elif item.avm_flexible_positions:
            flexible.append(item)
        elif item.avm_preferred_position in assignments:
            assignments[item.avm_preferred_position].append(item)
            item.avm_assignment_status = "ingepland"
        elif item.avm_default_position in assignments:
            assignments[item.avm_default_position].append(item)
            item.avm_assignment_status = "ingepland"

    for item in sorted(flexible, key=lambda value: (value.day, value.start)):
        positions = sorted(
            {
                position
                for position in item.avm_flexible_positions
                if position in assignments
            }
        )
        if not positions:
            continue
        item_minutes = (
            int((item.end - item.start).total_seconds() // 60) if item.end else 0
        )
        if item.end and item_minutes > target and len(positions) >= 2:
            first, second = _split_flexible_item(item)
            orientations = [(positions[0], first, positions[1], second)]
            orientations.append((positions[1], first, positions[0], second))

            def orientation_score(values):
                first_position, first_part, second_position, second_part = values
                return max(
                    _assignment_score(
                        _items_on_day(assignments[first_position], item.day) + [first_part],
                        rules,
                    ),
                    _assignment_score(
                        _items_on_day(assignments[second_position], item.day) + [second_part],
                        rules,
                    ),
                )

            first_position, first_part, second_position, second_part = min(
                orientations, key=orientation_score
            )
            assignments[first_position].append(first_part)
            assignments[second_position].append(second_part)
            item.avm_assignment_status = "ingepland"
            continue

        def position_score(position: str):
            score = _assignment_score(
                _items_on_day(assignments[position], item.day) + [item], rules
            )
            preference_penalty = 0 if position == item.avm_preferred_position else 1
            return score[0], score[1], preference_penalty, score[2]

        best_position = min(positions, key=position_score)
        assignments[best_position].append(item)
        item.avm_assignment_status = "ingepland"

    level_order = {"richtlijn": 0, "gebruikelijk": 1}
    for item in sorted(
        soft,
        key=lambda value: (
            level_order.get(value.avm_planning_level or "", 99),
            value.day,
            value.start,
        ),
    ):
        if item.end is None:
            item.avm_assignment_status = "niet_ingepland"
            item.avm_omission_reason = "Geen eindtijd beschikbaar"
            continue

        if item.avm_required_count >= 2:
            candidates_by_position = {
                position: assignments[position] + [item]
                for position in ("AVM1", "AVM2")
            }
            if all(
                _cao_conflict_score(
                    _plan_daily_shifts_for_items(position, candidate_items, rules),
                    rules,
                )
                == (0, 0)
                for position, candidate_items in candidates_by_position.items()
            ):
                for position in ("AVM1", "AVM2"):
                    assignments[position].append(item)
                item.avm_assignment_status = "ingepland"
            else:
                item.avm_assignment_status = "niet_ingepland"
                item.avm_omission_reason = (
                    "Niet haalbaar zonder CAO-conflict voor de vereiste bezetting"
                )
            continue

        positions = [
            position
            for position in item.avm_flexible_positions
            if position in assignments
        ]
        for preferred in (
            item.avm_preferred_position,
            item.avm_default_position,
        ):
            if preferred in assignments and preferred not in positions:
                positions.append(preferred)
        if not positions:
            positions = ["AVM1", "AVM2"]

        candidates = []
        for position in positions:
            candidate_items = assignments[position] + [item]
            conflict_score = _cao_conflict_score(
                _plan_daily_shifts_for_items(position, candidate_items, rules),
                rules,
            )
            if conflict_score != (0, 0):
                continue
            assignment_score = _assignment_score(
                _items_on_day(candidate_items, item.day), rules
            )
            preference_penalty = (
                0 if position == item.avm_preferred_position else 1
            )
            candidates.append(
                (assignment_score, preference_penalty, position)
            )
        if candidates:
            *_, position = min(candidates)
            assignments[position].append(item)
            item.avm_assignment_status = "ingepland"
        else:
            item.avm_assignment_status = "niet_ingepland"
            item.avm_omission_reason = "Niet haalbaar zonder CAO-conflict"

    for item in sorted(optional, key=lambda value: (value.day, value.start)):
        if item.end is None:
            continue
        candidates = []
        for position in item.avm_flexible_positions:
            if position not in assignments:
                continue
            day_items = _items_on_day(assignments[position], item.day)
            if not day_items:
                continue
            overlaps = any(
                existing.end is not None
                and item.start < existing.end
                and item.end > existing.start
                for existing in day_items
            )
            if overlaps:
                continue
            base_span = _estimated_span_minutes(day_items, rules)
            extended_span = _estimated_span_minutes(day_items + [item], rules)
            if extended_span <= base_span:
                candidates.append((len(day_items), position))
        if candidates:
            _, position = min(candidates)
            assignments[position].append(item)
            item.avm_assignment_status = "ingepland"
        else:
            item.avm_assignment_status = "niet_ingepland"
            item.avm_omission_reason = "Geen ruimte binnen een bestaande dienst"

    for items in assignments.values():
        items.sort(key=lambda value: (value.day, value.start))
    return assignments


def assigned_items(
    schedule: ProductionSchedule, position: str, rules: dict | None = None
) -> list[PlanningItem]:
    return build_assignments(schedule, rules).get(position, [])


def _items_without_instance(
    items: list[PlanningItem], item_to_remove: PlanningItem
) -> list[PlanningItem]:
    removed = False
    remaining = []
    for item in items:
        if not removed and item is item_to_remove:
            removed = True
            continue
        remaining.append(item)
    if removed:
        return remaining
    return [item for item in items if item.id != item_to_remove.id]


def _source_id(item: PlanningItem) -> str:
    return item.id.split("#", maxsplit=1)[0]


def _is_team_replaceable(item: PlanningItem, rules: dict) -> bool:
    patterns = [
        str(pattern)
        for pattern in rules.get("overflow_policy", {}).get(
            "replaceable_activity_patterns", []
        )
    ]
    return bool(patterns) and _matches_patterns(item.activity, patterns)


def _is_allowed_team_replacement(item: PlanningItem, rules: dict) -> bool:
    overflow = rules.get("overflow_policy", {})
    fixed_patterns = [
        str(pattern)
        for pattern in overflow.get("fixed_primary_activity_patterns", [])
    ]
    if fixed_patterns and _matches_patterns(item.activity, fixed_patterns):
        return False
    if _is_team_replaceable(item, rules):
        return True
    return bool(overflow.get("allow_required_activity_replacement_when_needed", True))


def _team_replacement_priority(item: PlanningItem, rules: dict) -> int:
    overflow = rules.get("overflow_policy", {})
    for priority_rule in overflow.get("replacement_priority_rules", []):
        patterns = [
            str(pattern)
            for pattern in priority_rule.get("activity_patterns", [])
        ]
        if patterns and _matches_patterns(item.activity, patterns):
            return int(priority_rule.get("priority", 100))
    return 100


def _requires_primary_presence(item: PlanningItem, rules: dict) -> bool:
    patterns = [
        str(pattern)
        for pattern in rules.get("overflow_policy", {}).get(
            "primary_presence_activity_patterns", []
        )
    ]
    return bool(patterns) and _matches_patterns(item.activity, patterns)


def _primary_presence_count(
    assignments: dict[str, list[PlanningItem]],
    item: PlanningItem,
    candidate_position: str,
    candidate_items: list[PlanningItem],
    primary_positions: list[str],
) -> int:
    source_id = _source_id(item)
    count = 0
    for position in primary_positions:
        items = candidate_items if position == candidate_position else assignments[position]
        count += sum(1 for candidate in items if _source_id(candidate) == source_id)
    return count


def _plan_daily_shifts_for_items(
    position: str, items: list[PlanningItem], rules: dict | None = None
) -> list[DailyShift]:
    rules = rules or {}
    shift_rules = rules.get("shift_planning", {})
    maximum_minutes = int(shift_rules.get("maximum_shift_minutes", 720))
    minimum_rest_minutes = int(shift_rules.get("minimum_rest_minutes", 660))

    items_by_day: dict[date, list[PlanningItem]] = {}
    for item in items:
        items_by_day.setdefault(item.day, []).append(item)

    shifts = []
    for day, day_items in sorted(items_by_day.items()):
        day_items.sort(key=lambda item: item.start)
        required_start, required_end, _ = _required_window(day_items, shift_rules)
        natural_span = int((required_end - required_start).total_seconds() // 60)
        double_performance_capped = (
            _double_performance_rule(day_items, shift_rules) is not None
            and natural_span > maximum_minutes
        )
        shift_start, shift_end, target_minutes = _planned_bounds(day_items, shift_rules)
        adjusted_start, adjustment_reasons = _apply_start_adjustments(
            shift_start, list(rules.get("call_time_adjustments", []))
        )
        skipped_adjustment_reasons = []
        adjusted_duration = int(
            (shift_end - adjusted_start).total_seconds() // 60
        )
        if adjustment_reasons and adjusted_duration > maximum_minutes:
            skipped_adjustment_reasons = adjustment_reasons
        else:
            shift_start = adjusted_start

        shift = DailyShift(
            position=position,
            day=day,
            start=shift_start,
            end=shift_end,
            items=day_items,
            target_minutes=target_minutes,
        )
        team_reasons = []
        for item in day_items:
            for reason in item.avm_reasons:
                if not reason.startswith(TEAM_REASON_PREFIX):
                    continue
                note = reason.removeprefix(TEAM_REASON_PREFIX)
                if note not in team_reasons:
                    team_reasons.append(note)
        shift.flags.extend(team_reasons)
        shift.flags.extend(f"Startcorrectie: {reason}" for reason in adjustment_reasons)
        if skipped_adjustment_reasons:
            shift.flags = [
                flag
                for flag in shift.flags
                if not flag.startswith("Startcorrectie:")
            ]
            shift.flags.extend(
                "Startcorrectie vervallen om CAO-overschrijding te voorkomen: "
                + reason
                for reason in skipped_adjustment_reasons
            )
        if double_performance_capped:
            shift.flags.append(
                "Voorbereiding vóór de eerste voorstelling ingekort zodat "
                "AVM1 en AVM2 beide voorstellingen binnen de grens van "
                f"{_minutes_as_prose(maximum_minutes)} draaien"
            )
        shifts.append(shift)

    def fill_to_target(
        shift: DailyShift,
        earliest_start: datetime | None = None,
        latest_end: datetime | None = None,
    ) -> None:
        if shift.duration_minutes >= shift.target_minutes:
            return

        # Vul een korte dienst bij voorkeur aan de voorkant aan.
        desired_start = shift.end - timedelta(minutes=shift.target_minutes)
        start_limits = [desired_start]
        target_fill_floor = shift_rules.get("target_fill_earliest_start")
        if target_fill_floor:
            start_limits.append(_at(shift.day, str(target_fill_floor)))
        if earliest_start is not None:
            start_limits.append(earliest_start)
        new_start = max(start_limits)
        added = int((shift.start - new_start).total_seconds() // 60)
        if added > 0:
            shift.start = new_start
            shift.target_fill_minutes += added

        # Als eerder beginnen door nachtrust niet kan, vul dan aan de achterkant.
        if shift.duration_minutes >= shift.target_minutes:
            return
        desired_end = shift.start + timedelta(
            minutes=min(shift.target_minutes, maximum_minutes)
        )
        new_end = (
            min(desired_end, latest_end)
            if latest_end is not None
            else desired_end
        )
        added_after = int((new_end - shift.end).total_seconds() // 60)
        if added_after <= 0:
            return
        shift.end = new_end
        shift.target_fill_minutes += added_after
        shift.target_fill_after_minutes += added_after

    def latest_end_for(index: int) -> datetime | None:
        if index + 1 >= len(shifts):
            return None
        return shifts[index + 1].start - timedelta(minutes=minimum_rest_minutes)

    if shifts:
        fill_to_target(shifts[0], latest_end=latest_end_for(0))

    for index, (previous, current) in enumerate(zip(shifts, shifts[1:]), start=1):
        rest_minutes = int((current.start - previous.end).total_seconds() // 60)
        if rest_minutes < minimum_rest_minutes:
            compliant_start = previous.end + timedelta(minutes=minimum_rest_minutes)
            required_start, _, _ = _required_window(current.items, shift_rules)
            if compliant_start <= required_start:
                current.start = compliant_start
                current.flags.append("Start verschoven om minimaal 11 uur nachtrust te behouden")
            elif compliant_start <= min(item.start for item in current.items):
                current.start = compliant_start
                current.flags.append(
                    "Start verschoven om minimaal 11 uur nachtrust te behouden; "
                    "aanloop voor dienststart is niet in deze dienst opgenomen"
                )
            else:
                current.flags.append(
                    f"CAO-CONFLICT: {rest_minutes // 60}u{rest_minutes % 60:02d} "
                    "rust sinds vorige dienst; minimaal 11 uur vereist"
                )
        fill_to_target(
            current,
            earliest_start=previous.end + timedelta(minutes=minimum_rest_minutes),
            latest_end=latest_end_for(index),
        )

    for shift in shifts:
        if shift.target_fill_minutes:
            target_label = (
                f"{shift.target_minutes // 60}u{shift.target_minutes % 60:02d}"
            )
            before_minutes = (
                shift.target_fill_minutes - shift.target_fill_after_minutes
            )
            if shift.duration_minutes >= shift.target_minutes:
                if before_minutes and shift.target_fill_after_minutes:
                    shift.flags.append(
                        f"Dienst begint {before_minutes} min eerder en eindigt "
                        f"{shift.target_fill_after_minutes} min later om streefduur "
                        f"van {target_label} te halen"
                    )
                elif shift.target_fill_after_minutes:
                    shift.flags.append(
                        f"Dienst eindigt {shift.target_fill_after_minutes} min later "
                        f"om streefduur van {target_label} te halen"
                    )
                else:
                    shift.flags.append(
                        f"Dienst begint {before_minutes} min eerder "
                        f"om streefduur van {target_label} te halen"
                    )
            else:
                shift.flags.append(
                    f"Dienst is waar mogelijk aangevuld; "
                    f"streefduur van {target_label} niet haalbaar door minimale nachtrust"
                )
        elif shift.duration_minutes < shift.target_minutes:
            target_label = (
                f"{shift.target_minutes // 60}u{shift.target_minutes % 60:02d}"
            )
            shift.flags.append(
                f"Streefduur van {target_label} niet haalbaar door minimale nachtrust"
            )
        if shift.duration_minutes > maximum_minutes:
            shift.flags.append(
                f"CAO-CONFLICT: dienst duurt {shift.duration_minutes // 60}u"
                f"{shift.duration_minutes % 60:02d} en overschrijdt "
                f"{_minutes_as_prose(maximum_minutes)}"
            )
        overflow = rules.get("overflow_policy", {})
        if (
            overflow.get("allow_team_replacement")
            and overflow.get("trigger_on_cao_conflict")
            and any("CAO-CONFLICT" in flag for flag in shift.flags)
        ):
            replacement_flag = _team_replacement_flag(shift, overflow)
            if replacement_flag:
                shift.flags.append(replacement_flag)

    return shifts


def _cao_conflict_score(shifts: list[DailyShift], rules: dict) -> tuple[int, int]:
    shift_rules = rules.get("shift_planning", {})
    maximum_minutes = int(shift_rules.get("maximum_shift_minutes", 720))
    minimum_rest_minutes = int(shift_rules.get("minimum_rest_minutes", 660))
    conflicts = 0
    deficit = 0

    for shift in shifts:
        excess = max(0, shift.duration_minutes - maximum_minutes)
        if excess:
            conflicts += 1
            deficit += excess

    for previous, current in zip(shifts, shifts[1:]):
        rest_minutes = int((current.start - previous.end).total_seconds() // 60)
        if rest_minutes >= minimum_rest_minutes:
            continue
        compliant_start = previous.end + timedelta(minutes=minimum_rest_minutes)
        required_start, _, _ = _required_window(current.items, shift_rules)
        if compliant_start <= required_start or compliant_start <= min(
            item.start for item in current.items
        ):
            continue
        conflicts += 1
        deficit += minimum_rest_minutes - rest_minutes

    return conflicts, deficit


def _has_duplicate_slot(items: list[PlanningItem], candidate: PlanningItem) -> bool:
    return any(_source_id(item) == _source_id(candidate) for item in items)


def _assign_team_item(
    team_assignments: dict[str, list[PlanningItem]],
    item: PlanningItem,
    rules: dict,
) -> None:
    for position in sorted(team_assignments):
        if _has_duplicate_slot(team_assignments[position], item):
            continue
        candidate_items = team_assignments[position] + [item]
        if _cao_conflict_score(
            _plan_daily_shifts_for_items(position, candidate_items, rules), rules
        ) == (0, 0):
            team_assignments[position].append(item)
            return

    position = f"TEAM-AVM{len(team_assignments) + 1}"
    team_assignments[position] = [item]


def build_cao_resolved_assignments(
    schedule: ProductionSchedule, rules: dict | None = None
) -> dict[str, list[PlanningItem]]:
    rules = rules or {}
    primary_positions = ["AVM1", "AVM2"]
    assignments = {
        position: list(items)
        for position, items in build_assignments(schedule, rules).items()
        if position in primary_positions
    }
    team_assignments: dict[str, list[PlanningItem]] = {}

    for _ in range(500):
        selected_move = None
        for position in primary_positions:
            shifts = _plan_daily_shifts_for_items(position, assignments[position], rules)
            for shift in shifts:
                if not (
                    _cao_conflict_score([shift], rules)[0] > 0
                    or any("CAO-CONFLICT" in flag for flag in shift.flags)
                ):
                    continue

                scored_candidates = []
                for item in shift.items:
                    if not _is_allowed_team_replacement(item, rules):
                        continue
                    candidate_items = _items_without_instance(assignments[position], item)
                    if _requires_primary_presence(item, rules) and _primary_presence_count(
                        assignments, item, position, candidate_items, primary_positions
                    ) < 1:
                        continue
                    score = _cao_conflict_score(
                        _plan_daily_shifts_for_items(position, candidate_items, rules),
                        rules,
                    )
                    item_minutes = (
                        int((item.end - item.start).total_seconds() // 60)
                        if item.end
                        else 0
                    )
                    replacement_penalty = 0 if _is_team_replaceable(item, rules) else 1
                    scored_candidates.append(
                        (
                            _team_replacement_priority(item, rules),
                            score[0],
                            score[1],
                            replacement_penalty,
                            item_minutes,
                            item.start,
                            item.id,
                            item,
                        )
                    )
                if not scored_candidates:
                    continue
                *_, item_to_move = min(scored_candidates)
                selected_move = (
                    position,
                    item_to_move,
                    _team_replacement_reason(position, shift),
                )
                break
            if selected_move:
                break
        if not selected_move:
            break

        position, item_to_move, replacement_reason = selected_move
        assignments[position] = _items_without_instance(
            assignments[position], item_to_move
        )
        team_item = replace(
            item_to_move,
            id=f"{item_to_move.id}#team-overname-{position}",
            avm_reasons=[
                *item_to_move.avm_reasons,
                TEAM_REASON_PREFIX + replacement_reason,
            ],
        )
        _assign_team_item(team_assignments, team_item, rules)

    for items in assignments.values():
        items.sort(key=lambda value: (value.day, value.start, value.id))
    for items in team_assignments.values():
        items.sort(key=lambda value: (value.day, value.start, value.id))

    return {**assignments, **team_assignments}


def plan_daily_shifts_for_items(
    position: str, items: list[PlanningItem], rules: dict | None = None
) -> list[DailyShift]:
    return _plan_daily_shifts_for_items(position, items, rules)


def _clock_minutes(value: str) -> int:
    hours, minutes = value.split(":", maxsplit=1)
    return int(hours) * 60 + int(minutes)


def _apply_start_adjustments(
    start: datetime, adjustments: list[dict]
) -> tuple[datetime, list[str]]:
    reasons = []
    for adjustment in adjustments:
        if start.hour * 60 + start.minute != _clock_minutes(str(adjustment["from"])):
            continue
        replacement = _clock_minutes(str(adjustment["to"]))
        start = start.replace(hour=replacement // 60, minute=replacement % 60)
        reasons.append(str(adjustment.get("description", adjustment.get("id", "correctie"))))
    return start, reasons


def plan_daily_shifts(
    schedule: ProductionSchedule, position: str, rules: dict | None = None
) -> list[DailyShift]:
    return plan_daily_shifts_for_items(
        position,
        assigned_items(schedule, position, rules),
        rules,
    )


def update_schedule_validation(
    schedule: ProductionSchedule, rules: dict | None = None
) -> dict[str, list[PlanningItem]]:
    """Werk de conceptstatus bij op basis van invoer, dekking en harde CAO-checks."""
    rules = rules or {}
    assignments = build_cao_resolved_assignments(schedule, rules)
    cao_conflicts: list[str] = []
    for position, items in assignments.items():
        for shift in _plan_daily_shifts_for_items(position, items, rules):
            for flag in shift.flags:
                if "CAO-CONFLICT" not in flag:
                    continue
                message = f"{position} {shift.day.isoformat()}: {flag}"
                if message not in cao_conflicts:
                    cao_conflicts.append(message)

    assigned_counts: dict[str, int] = {}
    for items in assignments.values():
        seen_in_position = set()
        for item in items:
            source_id = _source_id(item)
            if source_id in seen_in_position:
                continue
            assigned_counts[source_id] = assigned_counts.get(source_id, 0) + 1
            seen_in_position.add(source_id)

    blocking_reasons = []
    for question in schedule.decision_questions:
        if question.blocking and question.is_open:
            blocking_reasons.append(f"Open vraag: {question.prompt}")
    for requirement in schedule.planning_requirements:
        if requirement.status != "ingepland":
            missing = (
                f" ({', '.join(requirement.missing_fields)} ontbreekt)"
                if requirement.missing_fields
                else ""
            )
            blocking_reasons.append(
                f"Niet ingepland: {requirement.description}{missing}"
            )
    for item in schedule.items:
        level = item.avm_planning_level or (
            "verplicht" if item.avm_required_count else None
        )
        if level != "verplicht" or item.avm_required_count < 1:
            continue
        assigned_count = assigned_counts.get(item.id, 0)
        if assigned_count < item.avm_required_count:
            blocking_reasons.append(
                f"Onvoldoende dekking voor {item.activity} op "
                f"{item.day.isoformat()}: {assigned_count}/"
                f"{item.avm_required_count}"
            )

    schedule.cao_conflicts = cao_conflicts
    schedule.blocking_reasons = blocking_reasons
    schedule.cao_validation_scope = "gedeeltelijk"
    if cao_conflicts:
        schedule.planning_status = "ongeldig_cao"
    elif blocking_reasons:
        schedule.planning_status = "invoer_nodig"
    else:
        schedule.planning_status = "concept_geldig_binnen_deelcontrole"
    return assignments
