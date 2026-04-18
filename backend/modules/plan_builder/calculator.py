from collections.abc import Iterable
from typing import Any

from sqlalchemy import event, select

from backend.models import NormativeParam, PlanElement


DEFAULT_CREDIT_HOUR_RATIO = 36.0


def _get_value(item: Any, field: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(field, default)
    return getattr(item, field, default)


def _normalize_block(block: Any) -> str:
    return str(block)


def _normalize_semesters(raw_semesters: Any) -> list[int]:
    if raw_semesters is None:
        return []

    if isinstance(raw_semesters, int):
        values = [raw_semesters]
    else:
        values = list(raw_semesters or [])

    semesters = sorted({int(value) for value in values if int(value) > 0})
    return semesters


def _semester_to_year(semester: int | None) -> int | None:
    if semester is None or semester <= 0:
        return None
    return (semester + 1) // 2


def _split_credits(credits: float, semesters: list[int]) -> dict[int, float]:
    if not semesters:
        return {}

    share = credits / len(semesters)
    return {semester: share for semester in semesters}


def compute_hours(credits: float, credit_hour_ratio: float = DEFAULT_CREDIT_HOUR_RATIO) -> int:
    return round(credits * credit_hour_ratio)


def aggregate_by_block(elements: Iterable[Any]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for element in elements:
        block = _normalize_block(_get_value(element, "block"))
        credits = float(_get_value(element, "credits", 0) or 0)
        totals[block] = totals.get(block, 0.0) + credits
    return totals


def aggregate_by_year(elements: Iterable[Any]) -> dict[int, float]:
    totals: dict[int, float] = {}
    for element in elements:
        credits = float(_get_value(element, "credits", 0) or 0)
        semesters = _normalize_semesters(_get_value(element, "semesters", []))
        for semester, share in _split_credits(credits, semesters).items():
            year = _semester_to_year(semester)
            if year is None:
                continue
            totals[year] = totals.get(year, 0.0) + share
    return totals


def aggregate_by_semester(elements: Iterable[Any]) -> dict[int, float]:
    totals: dict[int, float] = {}
    for element in elements:
        credits = float(_get_value(element, "credits", 0) or 0)
        semesters = _normalize_semesters(_get_value(element, "semesters", []))
        for semester, share in _split_credits(credits, semesters).items():
            totals[semester] = totals.get(semester, 0.0) + share
    return totals


def aggregate_mandatory_percent(elements: Iterable[Any]) -> float:
    total_credits = 0.0
    mandatory_credits = 0.0

    for element in elements:
        credits = float(_get_value(element, "credits", 0) or 0)
        total_credits += credits
        if _get_value(element, "part") == "mandatory":
            mandatory_credits += credits

    if total_credits == 0:
        return 0.0

    return mandatory_credits / total_credits


def get_competency_coverage(elements: Iterable[Any], competencies: Iterable[Any]) -> dict[str, bool]:
    covered_ids: set[int] = set()
    for element in elements:
        competency_ids = _get_value(element, "competency_ids", []) or []
        covered_ids.update(int(comp_id) for comp_id in competency_ids)

    coverage: dict[str, bool] = {}
    for competency in competencies:
        code = _get_value(competency, "code")
        comp_id = int(_get_value(competency, "id"))
        coverage[code] = comp_id in covered_ids

    return coverage


def _get_credit_hour_ratio(connection) -> float:
    stmt = select(NormativeParam.value).where(NormativeParam.key == "CreditHourRatio")
    result = connection.execute(stmt).scalar_one_or_none()
    return float(result) if result is not None else DEFAULT_CREDIT_HOUR_RATIO


@event.listens_for(PlanElement, "before_insert")
@event.listens_for(PlanElement, "before_update")
def set_plan_element_hours(_, connection, target: PlanElement) -> None:
    ratio = _get_credit_hour_ratio(connection)
    target.semesters = _normalize_semesters(target.semesters)
    target.hours = compute_hours(target.credits, ratio)
