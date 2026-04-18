from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models import Competency, CurriculumPlan, PlanElement, RecommendedElement
from backend.modules.seed_ingest import loader


def _build_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    return testing_session_local()


def test_load_seed_data_removes_stale_pk_and_auto_recommendations(monkeypatch) -> None:
    db = _build_session()
    try:
        stale_pk = Competency(code="ПК-1", type="ПК", name="ПК 1", description="legacy")
        stale_recommendation = RecommendedElement(
            name="Старая дисциплина",
            element_type="discipline",
            part="mandatory",
            credits=3.0,
            semesters=[1],
            source="poop",
            competencies=[stale_pk],
        )
        db.add_all([stale_pk, stale_recommendation])
        db.commit()

        payloads = {
            "competencies.json": [
                {"code": "УК-1", "type": "УК", "name": "УК 1", "description": "desc"},
                {"code": "ОПК-1", "type": "ОПК", "name": "ОПК 1", "description": "desc"},
                {"code": "ПКС-1", "type": "ПКС", "name": "ПКС 1", "description": "desc"},
            ],
            "poop_disciplines.json": [
                {
                    "name": "Философия",
                    "element_type": "discipline",
                    "part": "mandatory",
                    "credits": 3.0,
                    "semesters": [1],
                    "source": "poop",
                    "competency_codes": ["УК-1"],
                },
                {
                    "name": "Невалидная рекомендация для ПК",
                    "element_type": "discipline",
                    "part": "mandatory",
                    "credits": 2.0,
                    "semesters": [2],
                    "source": "poop",
                    "competency_codes": ["ПК-1"],
                },
            ],
            "normative_params.json": [
                {"key": "X_total", "value": 240.0},
                {"key": "CreditHourRatio", "value": 36.0},
            ],
        }

        monkeypatch.setattr(loader, "_read_json", lambda filename: payloads[filename])

        loader.load_seed_data(db)

        competency_codes = {item.code for item in db.query(Competency).all()}
        assert "ПК-1" not in competency_codes
        assert competency_codes == {"УК-1", "ОПК-1", "ПКС-1"}

        recommendations = db.query(RecommendedElement).all()
        assert len(recommendations) == 1
        assert recommendations[0].name == "Философия"
        assert recommendations[0].semesters == [1]
    finally:
        db.close()


def test_load_seed_data_removes_stale_competency_ids_from_plan_elements(monkeypatch) -> None:
    db = _build_session()
    try:
        stale_pk = Competency(code="ПК-1", type="ПК", name="ПК 1", description="legacy")
        valid_uk = Competency(code="УК-1", type="УК", name="УК 1", description="desc")
        db.add_all([stale_pk, valid_uk])
        db.flush()

        plan = CurriculumPlan(name="Legacy plan", status="draft")
        db.add(plan)
        db.flush()

        element = PlanElement(
            plan_id=plan.id,
            name="Старая дисциплина",
            block="1",
            part="mandatory",
            credits=3.0,
            hours=108.0,
            semesters=[1],
            competency_ids=[valid_uk.id, stale_pk.id, 999],
            source_element_id=None,
        )
        db.add(element)
        db.commit()

        payloads = {
            "competencies.json": [
                {"code": "УК-1", "type": "УК", "name": "УК 1", "description": "desc"},
                {"code": "ОПК-1", "type": "ОПК", "name": "ОПК 1", "description": "desc"},
            ],
            "poop_disciplines.json": [],
            "normative_params.json": [
                {"key": "X_total", "value": 240.0},
                {"key": "CreditHourRatio", "value": 36.0},
            ],
        }

        monkeypatch.setattr(loader, "_read_json", lambda filename: payloads[filename])

        loader.load_seed_data(db)
        db.refresh(element)

        assert element.competency_ids == [valid_uk.id]
        assert element.semesters == [1]
    finally:
        db.close()
