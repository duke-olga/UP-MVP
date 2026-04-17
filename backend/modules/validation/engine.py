from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from backend.models import CheckReport, Competency, CurriculumPlan, NormativeParam, PlanElement
from backend.modules.plan_builder.calculator import (
    aggregate_by_block,
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


def _check_required_disciplines(elements: list[PlanElement]) -> CheckResult | None:
    discipline_names = {
        _normalize_name(element.name)
        for element in elements
        if element.block == "1" or str(element.block) == "1"
    }
    required_groups = {
        "Философия": any("философ" in name for name in discipline_names),
        "История": any("история" in name for name in discipline_names),
        "Иностранный язык": any("иностранный язык" in name for name in discipline_names),
        "БЖД": any("безопасность жизнедеятельности" in name or "бжд" in name for name in discipline_names),
    }
    missing = [name for name, exists in required_groups.items() if not exists]
    if missing:
        return CheckResult(
            rule_id=9,
            level="error",
            message="В учебном плане отсутствуют обязательные дисциплины.",
            actual=", ".join(missing),
            expected="Философия, История, Иностранный язык, БЖД",
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
    pe_total = sum(element.hours for element in _find_physical_education_elements(elements))
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


def _is_educational_practice(name: str) -> bool:
    normalized = _normalize_name(name)
    return "учеб" in normalized or "ознаком" in normalized or "получение первичных навыков" in normalized


def _is_industrial_practice(name: str) -> bool:
    normalized = _normalize_name(name)
    return any(token in normalized for token in ["производ", "технологичес", "эксплуатацион", "преддиплом"])


def _check_practice_presence(elements: list[PlanElement], rule_id: int, checker, message: str) -> CheckResult | None:
    practices = [
        element for element in elements
        if str(element.block) == "2" and checker(element.name)
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


def run_checks(plan_id: int, db: Session) -> CheckReport:
    plan = _get_plan_or_raise(plan_id, db)
    elements = list(plan.elements)
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
            _is_educational_practice,
            "В учебном плане отсутствует учебная практика.",
        ),
        _check_practice_presence(
            elements,
            13,
            _is_industrial_practice,
            "В учебном плане отсутствует производственная практика.",
        ),
        _check_competency_coverage(elements, competencies),
        _check_competency_types(competencies),
    ]:
        if single_check is not None:
            results.append(single_check)

    results.extend(_check_yearly_credits(elements, params))
    results.extend(_check_block_minimums(elements, params))
    results.extend(_check_hours_match(elements, params))

    report = CheckReport(
        plan_id=plan.id,
        results=[asdict(result) for result in sorted(results, key=lambda item: (item.rule_id, item.level))],
        llm_recommendations=None,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
