from collections import defaultdict
from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from backend.models import CheckReport, Competency, CurriculumPlan, NormativeParam, PlanElement
from backend.modules.plan_builder.calculator import (
    aggregate_by_block,
    aggregate_by_semester,
    aggregate_by_year,
    aggregate_mandatory_percent,
    get_competency_coverage,
)


@dataclass
class CheckResult:
    rule_id: int
    level: str
    message: str
    actual: str | float | int | None = None
    expected: str | float | int | None = None


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _countable_elements(elements: list[PlanElement]) -> list[PlanElement]:
    return [element for element in elements if str(element.block) != "fac"]


def _get_normative_params(db: Session) -> dict[str, float]:
    params = db.query(NormativeParam).all()
    return {item.key: item.value for item in params}


def _get_plan_or_raise(plan_id: int, db: Session) -> CurriculumPlan:
    plan = db.query(CurriculumPlan).filter(CurriculumPlan.id == plan_id).first()
    if plan is None:
        raise ValueError(f"Plan with id={plan_id} was not found")
    return plan


def _check_total_credits(elements: list[PlanElement], params: dict[str, float]) -> CheckResult | None:
    total = sum(element.credits for element in elements)
    expected = params["X_total"]
    if total != expected:
        return CheckResult(
            rule_id=1,
            level="critical",
            message="Общий объем программы не соответствует нормативу.",
            actual=total,
            expected=expected,
        )
    return None


def _check_yearly_credits(elements: list[PlanElement], params: dict[str, float]) -> list[CheckResult]:
    results: list[CheckResult] = []
    expected = params["X_year"]
    for year, total in aggregate_by_year(elements).items():
        if total > expected:
            results.append(
                CheckResult(
                    rule_id=2,
                    level="error",
                    message=f"Объем за {year} год обучения превышает норматив.",
                    actual=total,
                    expected=expected,
                )
            )
    return results


def _check_required_blocks(elements: list[PlanElement]) -> CheckResult | None:
    blocks = {str(element.block) for element in elements}
    required = {"1", "2", "3"}
    if not required.issubset(blocks):
        return CheckResult(
            rule_id=4,
            level="critical",
            message="В учебном плане отсутствуют обязательные блоки 1, 2 или 3.",
            actual=", ".join(sorted(blocks)) if blocks else "none",
            expected="1, 2, 3",
        )
    return None


def _check_block_minimums(elements: list[PlanElement], params: dict[str, float]) -> list[CheckResult]:
    totals = aggregate_by_block(elements)
    rules = [
        (5, "1", params["X_b1"]),
        (6, "2", params["X_b2"]),
        (7, "3", params["X_b3"]),
    ]
    results: list[CheckResult] = []
    for rule_id, block, expected in rules:
        actual = totals.get(block, 0.0)
        if actual < expected:
            results.append(
                CheckResult(
                    rule_id=rule_id,
                    level="error",
                    message=f"Минимальный объем блока {block} не достигнут.",
                    actual=actual,
                    expected=expected,
                )
            )
    return results


def _check_mandatory_percent(elements: list[PlanElement], params: dict[str, float]) -> CheckResult | None:
    actual = aggregate_mandatory_percent(elements)
    expected = params["X_mandatory_percent"]
    if actual < expected:
        return CheckResult(
            rule_id=8,
            level="error",
            message="Доля обязательной части ниже нормативного значения.",
            actual=actual,
            expected=expected,
        )
    return None


def _has_required_discipline(elements: list[PlanElement], tokens: tuple[str, ...]) -> bool:
    discipline_names = [_normalize_name(element.name) for element in elements if str(element.block) == "1"]
    return any(any(token in name for token in tokens) for name in discipline_names)


def _check_required_disciplines(elements: list[PlanElement]) -> CheckResult | None:
    required_groups = {
        "Философия": _has_required_discipline(elements, ("философ",)),
        "История": _has_required_discipline(elements, ("история",)),
        "Иностранный язык": _has_required_discipline(elements, ("иностранный язык",)),
        "Безопасность жизнедеятельности": _has_required_discipline(elements, ("безопасность жизнедеятельности", "бжд")),
    }
    missing = [name for name, exists in required_groups.items() if not exists]
    if missing:
        return CheckResult(
            rule_id=9,
            level="error",
            message="В учебном плане отсутствуют обязательные дисциплины ФГОС.",
            actual=", ".join(missing),
            expected="Философия, История, Иностранный язык, Безопасность жизнедеятельности",
        )
    return None


def _find_physical_education_elements(elements: list[PlanElement]) -> list[PlanElement]:
    return [element for element in elements if "физическая культура" in _normalize_name(element.name)]


def _check_pe_credits(elements: list[PlanElement], params: dict[str, float]) -> CheckResult | None:
    pe_total = sum(element.credits for element in _find_physical_education_elements(elements))
    expected = params["X_pe_ze"]
    if pe_total < expected:
        return CheckResult(
            rule_id=10,
            level="error",
            message="Объем дисциплины по физической культуре в з.е. ниже норматива.",
            actual=pe_total,
            expected=expected,
        )
    return None


def _check_pe_hours(elements: list[PlanElement], params: dict[str, float]) -> CheckResult | None:
    pe_total = sum(float(element.hours or 0) + float(element.extra_hours or 0) for element in _find_physical_education_elements(elements))
    expected = params["X_pe_hours"]
    if pe_total < expected:
        return CheckResult(
            rule_id=11,
            level="error",
            message="Объем дисциплины по физической культуре в часах ниже норматива.",
            actual=pe_total,
            expected=expected,
        )
    return None


def _check_practice_presence(elements: list[PlanElement], rule_id: int, practice_type: str, message: str) -> CheckResult | None:
    practices = [
        element
        for element in elements
        if str(element.block) == "2" and (element.practice_type or "").strip().lower() == practice_type
    ]
    if not practices:
        return CheckResult(
            rule_id=rule_id,
            level="error",
            message=message,
            actual=0,
            expected=1,
        )
    return None


def _check_competency_coverage(elements: list[PlanElement], competencies: list[Competency]) -> CheckResult | None:
    coverage = get_competency_coverage(elements, competencies)
    missing = sorted(code for code, is_covered in coverage.items() if not is_covered)
    if missing:
        return CheckResult(
            rule_id=14,
            level="critical",
            message="Не все компетенции покрыты элементами учебного плана.",
            actual=", ".join(missing),
            expected="Все компетенции должны быть покрыты",
        )
    return None


def _check_competency_types(competencies: list[Competency]) -> CheckResult | None:
    competency_types = {competency.type for competency in competencies}
    has_prof = "ПК" in competency_types or "ПКС" in competency_types
    if not {"УК", "ОПК"}.issubset(competency_types) or not has_prof:
        return CheckResult(
            rule_id=15,
            level="error",
            message="Во входном наборе компетенций отсутствует один из обязательных типов.",
            actual=", ".join(sorted(competency_types)),
            expected="УК, ОПК, ПК/ПКС",
        )
    return None


def _check_hours_match(elements: list[PlanElement], params: dict[str, float]) -> list[CheckResult]:
    expected_ratio = params["CreditHourRatio"]
    results: list[CheckResult] = []
    for element in elements:
        expected_hours = round(element.credits * expected_ratio)
        if element.hours != expected_hours:
            results.append(
                CheckResult(
                    rule_id=16,
                    level="error",
                    message=f"Элемент '{element.name}' имеет некорректное соотношение з.е. и часов.",
                    actual=element.hours,
                    expected=expected_hours,
                )
            )
    return results


def _check_semester_credits(elements: list[PlanElement], params: dict[str, float]) -> list[CheckResult]:
    results: list[CheckResult] = []
    expected = params.get("X_semester_max")
    if expected is None:
        return results

    for semester, total in aggregate_by_semester(elements).items():
        if total > expected:
            results.append(
                CheckResult(
                    rule_id=17,
                    level="warning",
                    message=f"Нагрузка в семестре {semester} превышает рекомендуемый максимум.",
                    actual=total,
                    expected=expected,
                )
            )
    return results


def _check_practice_balance(elements: list[PlanElement]) -> CheckResult | None:
    practices = [element for element in elements if str(element.block) == "2"]
    if len(practices) <= 1:
        return None

    semesters = defaultdict(int)
    for element in practices:
        for semester in element.semesters or []:
            semesters[int(semester)] += 1

    if not semesters:
        return None

    max_in_one_semester = max(semesters.values())
    if max_in_one_semester == len(practices):
        semester = next(key for key, value in semesters.items() if value == max_in_one_semester)
        return CheckResult(
            rule_id=18,
            level="warning",
            message="Практики сосредоточены в одном семестре.",
            actual=f"semester {semester}",
            expected="balanced distribution",
        )
    return None


def _check_competency_balance(elements: list[PlanElement], competencies: list[Competency]) -> CheckResult | None:
    counts: dict[int, int] = defaultdict(int)
    for element in elements:
        for competency_id in element.competency_ids or []:
            counts[int(competency_id)] += 1

    sparse_codes = sorted(competency.code for competency in competencies if counts.get(competency.id, 0) < 2)
    if sparse_codes:
        return CheckResult(
            rule_id=19,
            level="warning",
            message="Часть компетенций формируется менее чем двумя элементами.",
            actual=", ".join(sparse_codes),
            expected="Каждая компетенция формируется минимум двумя элементами",
        )
    return None


def _check_structure_parts(elements: list[PlanElement]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for element in elements:
        block = str(element.block)
        part = str(element.part)
        if block in {"1", "2"} and part not in {"mandatory", "variative"}:
            results.append(
                CheckResult(
                    rule_id=20,
                    level="error",
                    message=f"Элемент '{element.name}' имеет некорректную часть плана.",
                    actual=part,
                    expected="mandatory or variative",
                )
            )
        if block == "3" and part != "mandatory":
            results.append(
                CheckResult(
                    rule_id=20,
                    level="error",
                    message=f"Элемент '{element.name}' из блока ГИА должен относиться к обязательной части.",
                    actual=part,
                    expected="mandatory",
                )
            )
        if block == "2" and not (element.practice_type or "").strip():
            results.append(
                CheckResult(
                    rule_id=20,
                    level="error",
                    message=f"Практика '{element.name}' должна иметь атрибут типа практики.",
                    actual="missing",
                    expected="educational or industrial",
                )
            )
    return results


def run_checks(plan_id: int, db: Session) -> CheckReport:
    plan = _get_plan_or_raise(plan_id, db)
    elements = _countable_elements(list(plan.elements))
    competencies = db.query(Competency).order_by(Competency.code).all()
    params = _get_normative_params(db)

    results: list[CheckResult] = []

    for single_check in [
        _check_total_credits(elements, params),
        _check_required_blocks(elements),
        _check_mandatory_percent(elements, params),
        _check_required_disciplines(elements),
        _check_pe_credits(elements, params),
        _check_pe_hours(elements, params),
        _check_practice_presence(
            elements,
            12,
            "educational",
            "В учебном плане отсутствует учебная практика.",
        ),
        _check_practice_presence(
            elements,
            13,
            "industrial",
            "В учебном плане отсутствует производственная практика.",
        ),
        _check_competency_coverage(elements, competencies),
        _check_competency_types(competencies),
        _check_practice_balance(elements),
        _check_competency_balance(elements, competencies),
    ]:
        if single_check is not None:
            results.append(single_check)

    results.extend(_check_yearly_credits(elements, params))
    results.extend(_check_block_minimums(elements, params))
    results.extend(_check_hours_match(elements, params))
    results.extend(_check_semester_credits(elements, params))
    results.extend(_check_structure_parts(elements))

    report = CheckReport(
        plan_id=plan.id,
        results=[asdict(result) for result in sorted(results, key=lambda item: (item.rule_id, item.level, item.message))],
        llm_recommendations=None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
