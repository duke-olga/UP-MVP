from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import CurriculumPlan, NormativeParam, PlanElement
from backend.modules.plan_builder.calculator import (
    aggregate_by_block,
    aggregate_by_semester,
    aggregate_by_year,
    aggregate_mandatory_percent,
    compute_hours,
    get_competency_coverage,
)


def test_compute_hours_uses_default_ratio() -> None:
    assert compute_hours(3.0) == 108


def test_compute_hours_uses_custom_ratio() -> None:
    assert compute_hours(2.5, 40.0) == 100


def test_aggregate_by_block_sums_credits() -> None:
    elements = [
        {"block": 1, "credits": 10},
        {"block": 1, "credits": 5},
        {"block": 2, "credits": 6},
        {"block": "fac", "credits": 2},
    ]

    assert aggregate_by_block(elements) == {"1": 15.0, "2": 6.0, "fac": 2.0}


def test_aggregate_by_year_uses_semester_mapping() -> None:
    elements = [
        {"semester": 1, "credits": 10},
        {"semester": 2, "credits": 8},
        {"semester": 3, "credits": 7},
        {"semester": 4, "credits": 5},
        {"semester": None, "credits": 9},
    ]

    assert aggregate_by_year(elements) == {1: 18.0, 2: 12.0}


def test_aggregate_by_semester_sums_credits() -> None:
    elements = [
        {"semester": 1, "credits": 10},
        {"semester": 1, "credits": 2},
        {"semester": 2, "credits": 5},
        {"semester": None, "credits": 9},
    ]

    assert aggregate_by_semester(elements) == {1: 12.0, 2: 5.0}


def test_aggregate_mandatory_percent_returns_share() -> None:
    elements = [
        {"part": "mandatory", "credits": 10},
        {"part": "mandatory", "credits": 5},
        {"part": "variative", "credits": 15},
    ]

    assert aggregate_mandatory_percent(elements) == 0.5


def test_aggregate_mandatory_percent_handles_zero_total() -> None:
    assert aggregate_mandatory_percent([]) == 0.0


def test_get_competency_coverage_marks_covered_and_missing() -> None:
    elements = [
        {"competency_ids": [1, 2]},
        {"competency_ids": [2]},
    ]
    competencies = [
        {"id": 1, "code": "УК-1"},
        {"id": 2, "code": "ОПК-1"},
        {"id": 3, "code": "ПКС-1"},
    ]

    assert get_competency_coverage(elements, competencies) == {
        "УК-1": True,
        "ОПК-1": True,
        "ПКС-1": False,
    }


def test_plan_element_hours_are_computed_by_sqlalchemy_events() -> None:
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        db.add(NormativeParam(key="CreditHourRatio", value=36.0))
        db.flush()

        plan = CurriculumPlan(name="Test plan", status="draft")
        db.add(plan)
        db.flush()

        element = PlanElement(
            plan_id=plan.id,
            name="Программирование",
            block="1",
            part="mandatory",
            credits=3.0,
            hours=0,
            semester=1,
            competency_ids=[],
        )
        db.add(element)
        db.commit()
        db.refresh(element)
        assert element.hours == 108

        element.credits = 4.0
        db.add(element)
        db.commit()
        db.refresh(element)
        assert element.hours == 144
    finally:
        db.close()
