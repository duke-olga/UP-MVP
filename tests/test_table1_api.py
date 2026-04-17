from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.models import Competency, CurriculumPlan, RecommendedElement
from backend.routers import table1, table2


def _build_test_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(table1.router)
    app.include_router(table2.router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    try:
        uk = Competency(code="УК-1", type="УК", name="УК 1", description="desc")
        opk = Competency(code="ОПК-1", type="ОПК", name="ОПК 1", description="desc")
        pks = Competency(code="ПКС-1", type="ПКС", name="ПКС 1", description="desc")
        db.add_all([uk, opk, pks])
        db.flush()

        mandatory_discipline = RecommendedElement(
            name="Философия",
            element_type="discipline",
            part="mandatory",
            credits=3.0,
            semester=1,
            source="poop",
        )
        mandatory_discipline.competencies = [uk]

        variative_discipline = RecommendedElement(
            name="Политология",
            element_type="discipline",
            part="variative",
            credits=2.0,
            semester=2,
            source="poop",
        )
        variative_discipline.competencies = [uk, opk]

        mandatory_practice = RecommendedElement(
            name="Учебная практика",
            element_type="practice",
            part="mandatory",
            credits=3.0,
            semester=4,
            source="poop",
        )
        mandatory_practice.competencies = [opk]

        db.add_all([mandatory_discipline, variative_discipline, mandatory_practice])
        db.add(CurriculumPlan(name="Test plan", status="draft"))
        db.commit()
    finally:
        db.close()

    return TestClient(app)


def test_table1_returns_manual_mode_for_pks() -> None:
    client = _build_test_client()

    response = client.get("/api/v1/plans/1/table1")
    assert response.status_code == 200
    sections = response.json()["data"]

    pks_section = next(item for item in sections if item["competency"]["type"] == "ПКС")
    assert pks_section["mode"] == "manual"
    assert pks_section["mandatory_disciplines"] == []
    assert pks_section["variative_disciplines"] == []
    assert pks_section["mandatory_practices"] == []


def test_table1_transfer_moves_mandatory_and_selected_variative_elements() -> None:
    client = _build_test_client()

    table1_response = client.get("/api/v1/plans/1/table1")
    sections = table1_response.json()["data"]
    uk_section = next(item for item in sections if item["competency"]["code"] == "УК-1")
    selected_variative_id = uk_section["variative_disciplines"][0]["id"]

    transfer_response = client.post(
        "/api/v1/plans/1/table1/transfer",
        json={"selections": [{"element_id": selected_variative_id, "selected": True}]},
    )
    assert transfer_response.status_code == 200
    transfer_data = transfer_response.json()["data"]
    assert transfer_data["created_count"] == 3

    table2_response = client.get("/api/v1/plans/1/table2")
    data = table2_response.json()["data"]
    mandatory_block = data["grouped_elements"]["1"]["mandatory"]
    variative_block = data["grouped_elements"]["1"]["variative"]
    practices_block = data["grouped_elements"]["2"]["mandatory"]

    assert len(mandatory_block) == 1
    assert mandatory_block[0]["name"] == "Философия"
    assert len(variative_block) == 1
    assert variative_block[0]["name"] == "Политология"
    assert sorted(variative_block[0]["competency_ids"]) == [1, 2]
    assert len(practices_block) == 1
    assert practices_block[0]["name"] == "Учебная практика"


def test_table1_transfer_is_idempotent_for_same_selection() -> None:
    client = _build_test_client()

    table1_response = client.get("/api/v1/plans/1/table1")
    sections = table1_response.json()["data"]
    uk_section = next(item for item in sections if item["competency"]["code"] == "УК-1")
    selected_variative_id = uk_section["variative_disciplines"][0]["id"]

    client.post(
        "/api/v1/plans/1/table1/transfer",
        json={"selections": [{"element_id": selected_variative_id, "selected": True}]},
    )
    second_transfer = client.post(
        "/api/v1/plans/1/table1/transfer",
        json={"selections": [{"element_id": selected_variative_id, "selected": True}]},
    )

    assert second_transfer.status_code == 200
    assert second_transfer.json()["data"]["created_count"] == 0
