from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Optional


PLANNING_LEVELS = ("verplicht", "richtlijn", "gebruikelijk", "optioneel")


@dataclass
class PlanningItem:
    id: str
    day: date
    start: datetime
    end: Optional[datetime]
    activity: str
    location: Optional[str]
    page: int
    source_line: int
    kind: str
    details: list[str] = field(default_factory=list)
    avm_status: str = "niet_gemarkeerd"
    avm_required_count: int = 0
    avm_maximum_count: Optional[int] = None
    avm_optional: bool = False
    non_avm_allowed: bool = False
    avm_preferred_position: Optional[str] = None
    avm_default_position: Optional[str] = None
    avm_flexible_positions: list[str] = field(default_factory=list)
    avm_call_time: Optional[datetime] = None
    avm_day_wrap_minutes: Optional[int] = None
    avm_planning_level: Optional[str] = None
    avm_assignment_status: Optional[str] = None
    avm_omission_reason: Optional[str] = None
    generated_by_rule: Optional[str] = None
    avm_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["day"] = self.day.isoformat()
        value["start"] = self.start.isoformat()
        value["end"] = self.end.isoformat() if self.end else None
        value["avm_call_time"] = (
            self.avm_call_time.isoformat() if self.avm_call_time else None
        )
        return value


@dataclass
class DecisionQuestion:
    id: str
    prompt: str
    choices: list[str]
    answer: Optional[str] = None
    answer_source: Optional[str] = None
    blocking: bool = True
    explanation: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self.answer is None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["is_open"] = self.is_open
        return value


@dataclass
class PlanningRequirement:
    id: str
    description: str
    planning_level: str
    status: str
    question_id: Optional[str] = None
    related_item_id: Optional[str] = None
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceAnnotation:
    text: str
    day: date
    page: int
    source_line: int
    related_item_id: Optional[str]
    relation_uncertain: bool = True

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["day"] = self.day.isoformat()
        return value


@dataclass
class ProductionSchedule:
    source_file: str
    title: Optional[str]
    planning_start: Optional[date]
    planning_end: Optional[date]
    accountview_number: Optional[str]
    items: list[PlanningItem]
    annotations: list[SourceAnnotation]
    warnings: list[str] = field(default_factory=list)
    decision_questions: list[DecisionQuestion] = field(default_factory=list)
    planning_requirements: list[PlanningRequirement] = field(default_factory=list)
    planning_status: str = "concept"
    blocking_reasons: list[str] = field(default_factory=list)
    cao_conflicts: list[str] = field(default_factory=list)
    cao_validation_scope: str = "gedeeltelijk"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "source_file": self.source_file,
            "title": self.title,
            "planning_start": (
                self.planning_start.isoformat() if self.planning_start else None
            ),
            "planning_end": self.planning_end.isoformat() if self.planning_end else None,
            "accountview_number": self.accountview_number,
            "items": [item.to_dict() for item in self.items],
            "annotations": [annotation.to_dict() for annotation in self.annotations],
            "warnings": self.warnings,
            "decision_questions": [
                question.to_dict() for question in self.decision_questions
            ],
            "planning_requirements": [
                requirement.to_dict()
                for requirement in self.planning_requirements
            ],
            "planning_status": self.planning_status,
            "blocking_reasons": self.blocking_reasons,
            "cao_conflicts": self.cao_conflicts,
            "cao_validation_scope": self.cao_validation_scope,
        }
