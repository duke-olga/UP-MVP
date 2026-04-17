from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Competency, CurriculumPlan, NormativeParam, PlanElement
from backend.modules.validation.engine import run_checks


def _prepare_db():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    return db


def _add_normative_params(db):
    params = [
        ("X_total", 240.0),
        ("X_year", 70.0),
        ("X_b1", 150.0),
        ("X_b2", 21.0),
        ("X_b3", 9.0),
        ("X_mandatory_percent", 0.4),
        ("X_pe_ze", 2.0),
        ("X_pe_hours", 72.0),
        ("CreditHourRatio", 36.0),
    ]
    for key, value in params:
        db.add(NormativeParam(key=key, value=value))


def _add_competencies(db):
    competencies = [
        Competency(code="УК-1", type="УК", name="УК 1", description="desc"),
        Competency(code="ОПК-1", type="ОПК", name="ОПК 1", description="desc"),
        Competency(code="ПКС-1", type="ПКС", name="ПКС 1", description="desc"),
    ]
    db.add_all(competencies)
    db.flush()
    return competencies


def test_run_checks_returns_expected_violations_for_invalid_plan() -> None:
    db = _prepare_db()
    try:
        _add_normative_params(db)
        competencies = _add_competencies(db)

        plan = CurriculumPlan(name="Invalid plan", status="draft")
        db.add(plan)
        db.flush()

        db.add_all(
            [
                PlanElement(
                    plan_id=plan.id,
                    name="Философия",
                    block="1",
                    part="mandatory",
                    credits=10.0,
                    hours=0,
                    semester=1,
                    competency_ids=[competencies[0].id],
                ),
                PlanElement(
                    plan_id=plan.id,
                    name="Учебная практика",
                    block="2",
                    part="mandatory",
                    credits=3.0,
                    hours=0,
                    semester=2,
                    competency_ids=[competencies[1].id],
                ),
            ]
        )
        db.commit()

        report = run_checks(plan.id, db)
        rule_ids = {item["rule_id"] for item in report.results}

        assert report.plan_id == plan.id
        assert 1 in rule_ids
        assert 4 in rule_ids
        assert 14 in rule_ids
        assert 9 in rule_ids
        assert 13 in rule_ids
        assert 15 not in rule_ids
    finally:
        db.close()


def test_run_checks_detects_invalid_hours_ratio() -> None:
    db = _prepare_db()
    try:
        _add_normative_params(db)
        competencies = _add_competencies(db)

        plan = CurriculumPlan(name="Hours mismatch", status="draft")
        db.add(plan)
        db.flush()

        element = PlanElement(
            plan_id=plan.id,
            name="Иностранный язык",
            block="1",
            part="mandatory",
            credits=2.0,
            hours=999.0,
            semester=1,
            competency_ids=[competencies[0].id, competencies[1].id, competencies[2].id],
        )
        db.add(element)
        db.commit()

        db.execute(
            text("UPDATE plan_elements SET hours = :hours WHERE id = :element_id"),
            {"hours": 999.0, "element_id": element.id},
        )
        db.commit()
        db.expire_all()

        report = run_checks(plan.id, db)
        rule_ids = {item["rule_id"] for item in report.results}

        assert 16 in rule_ids
    finally:
        db.close()
