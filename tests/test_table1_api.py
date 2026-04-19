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
    testing_session_local = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(table1.router)
    app.include_router(table2.router)
    app.dependency_overrides[get_db] = override_get_db

    db = testing_session_local()
    try:
        uk = Competency(code="УК-1", type="УК", name="УК 1", description="desc")
        opk = Competency(code="ОПК-1", type="ОПК", name="ОПК 1", description="desc")
        pks = Competency(code="ПКС-1", type="ПКС", name="ПКС 1", description="desc")
        db.add_all([uk, opk, pks])
        db.flush()

        recommendations = [
            RecommendedElement(
                program_code="090304",
                name="Философия",
                element_type="discipline",
                part="mandatory",
                credits=3.0,
                semesters=[1],
                source="poop",
                source_name="090304_POOP_B.pdf",
                is_fgos_mandatory=1,
                fgos_requirement="philosophy",
                competencies=[uk],
            ),
            RecommendedElement(
                program_code="090304",
                name="Политология",
                element_type="discipline",
                part="variative",
                credits=2.0,
                semesters=[2, 3],
                source="best_practice",
                source_name="090304_ВШЭ.pdf",
                competencies=[uk, opk],
            ),
            RecommendedElement(
                program_code="090304",
                name="Учебная практика",
                element_type="practice",
                part="mandatory",
                credits=3.0,
                semesters=[4],
                source="local_requirement",
                source_name="local_rules.xlsx",
                practice_type="educational",
                is_fgos_mandatory=1,
                fgos_requirement="educational_practice",
                competencies=[opk],
            ),
            RecommendedElement(
                program_code="090301",
                name="Чужая рекомендация",
                element_type="discipline",
                part="variative",
                credits=5.0,
                semesters=[5],
                source="best_practices",
                source_name="090301_ИТМО.pdf",
                competencies=[uk],
            ),
        ]
        db.add_all(recommendations)
        db.add(CurriculumPlan(name="Test plan", program_code="090304", status="draft"))
        db.commit()
    finally:
        db.close()

    return TestClient(app)


def test_table1_returns_manual_mode_for_pks() -> None:
    client = _build_test_client()

    response = client.get("/api/v1/plans/1/table1")
    assert response.status_code == 200
    sections = response.json()["data"]["competencies"]

    pks_section = next(item for item in sections if item["competency"]["type"] == "ПКС")
    assert pks_section["mode"] == "manual_only"
    assert pks_section["mandatory_disciplines"] == []
    assert pks_section["variative_disciplines"] == []
    assert pks_section["mandatory_practices"] == []


def test_table1_filters_recommendations_by_program_and_keeps_source_titles() -> None:
    client = _build_test_client()

    response = client.get("/api/v1/plans/1/table1")
    assert response.status_code == 200
    data = response.json()["data"]
    sections = data["competencies"]

    uk_section = next(item for item in sections if item["competency"]["code"] == "УК-1")
    variative_names = [item["name"] for item in uk_section["variative_disciplines"]]
    assert variative_names == ["Политология"]
    assert uk_section["variative_disciplines"][0]["source_label"] == "Лучшие практики"
    assert uk_section["variative_disciplines"][0]["source_title"] == "ВШЭ"
    assert uk_section["variative_disciplines"][0]["semesters"] == [2, 3]

    philosophy_group = next(item for item in data["fgos_disciplines"] if item["requirement"] == "philosophy")
    assert philosophy_group["items"][0]["source_label"] == "ПООП"
    assert philosophy_group["items"][0]["source_title"] == "ПООП"
    assert philosophy_group["items"][0]["semesters"] == [1]

    educational_practice_group = next(
        item for item in data["fgos_practices"] if item["requirement"] == "educational_practice"
    )
    assert educational_practice_group["items"][0]["source_title"] == "Локальные требования вуза"


def test_table1_transfer_moves_only_selected_program_elements() -> None:
    client = _build_test_client()

    table1_response = client.get("/api/v1/plans/1/table1")
    payload = table1_response.json()["data"]
    sections = payload["competencies"]
    uk_section = next(item for item in sections if item["competency"]["code"] == "УК-1")
    selected_variative_id = uk_section["variative_disciplines"][0]["id"]
    selected_fgos_discipline_id = next(
        item["id"] for group in payload["fgos_disciplines"] if group["requirement"] == "philosophy" for item in group["items"]
    )
    selected_fgos_practice_id = next(
        item["id"] for group in payload["fgos_practices"] if group["requirement"] == "educational_practice" for item in group["items"]
    )

    transfer_response = client.post(
        "/api/v1/plans/1/table1/transfer",
        json={
            "selections": [
                {"element_id": selected_variative_id, "selected": True},
                {"element_id": selected_fgos_discipline_id, "selected": True},
                {"element_id": selected_fgos_practice_id, "selected": True},
            ]
        },
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
    assert practices_block[0]["practice_type"] == "educational"


def test_table1_transfer_is_idempotent_for_same_selection() -> None:
    client = _build_test_client()

    table1_response = client.get("/api/v1/plans/1/table1")
    payload = table1_response.json()["data"]
    sections = payload["competencies"]
    uk_section = next(item for item in sections if item["competency"]["code"] == "УК-1")
    selected_variative_id = uk_section["variative_disciplines"][0]["id"]
    selected_fgos_discipline_id = next(
        item["id"] for group in payload["fgos_disciplines"] if group["requirement"] == "philosophy" for item in group["items"]
    )
    selected_fgos_practice_id = next(
        item["id"] for group in payload["fgos_practices"] if group["requirement"] == "educational_practice" for item in group["items"]
    )

    selections = [
        {"element_id": selected_variative_id, "selected": True},
        {"element_id": selected_fgos_discipline_id, "selected": True},
        {"element_id": selected_fgos_practice_id, "selected": True},
    ]
    client.post("/api/v1/plans/1/table1/transfer", json={"selections": selections})
    second_transfer = client.post("/api/v1/plans/1/table1/transfer", json={"selections": selections})

    assert second_transfer.status_code == 200
    assert second_transfer.json()["data"]["created_count"] == 0


def test_table1_transfer_removes_deselected_recommendation_from_table2() -> None:
    client = _build_test_client()

    table1_response = client.get("/api/v1/plans/1/table1")
    payload = table1_response.json()["data"]
    selected_variative_id = next(
        section["variative_disciplines"][0]["id"]
        for section in payload["competencies"]
        if section["variative_disciplines"]
    )

    first_transfer = client.post(
        "/api/v1/plans/1/table1/transfer",
        json={"selections": [{"element_id": selected_variative_id, "selected": True}]},
    )
    assert first_transfer.status_code == 200
    assert first_transfer.json()["data"]["created_count"] == 1

    second_transfer = client.post(
        "/api/v1/plans/1/table1/transfer",
        json={"selections": [{"element_id": selected_variative_id, "selected": False}]},
    )
    assert second_transfer.status_code == 200
    assert second_transfer.json()["data"]["deleted_count"] == 1

    table2_response = client.get("/api/v1/plans/1/table2")
    data = table2_response.json()["data"]
    assert "1" not in data["grouped_elements"] or "variative" not in data["grouped_elements"].get("1", {})


def test_table1_transfer_rejects_multiple_fgos_discipline_variants_in_same_group() -> None:
    client = _build_test_client()

    app = client.app
    override = app.dependency_overrides[get_db]
    db_generator = override()
    db = next(db_generator)
    try:
        uk = db.query(Competency).order_by(Competency.id).first()
        db.add(
            RecommendedElement(
                program_code="090304",
                name="Философия и наука",
                element_type="discipline",
                part="mandatory",
                credits=3.0,
                semesters=[2],
                source="best_practice",
                source_name="090304_ИТМО.pdf",
                is_fgos_mandatory=1,
                fgos_requirement="philosophy",
                competencies=[uk],
            )
        )
        db.commit()
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass

    table1_response = client.get("/api/v1/plans/1/table1")
    philosophy_items = next(
        group["items"] for group in table1_response.json()["data"]["fgos_disciplines"] if group["requirement"] == "philosophy"
    )
    assert len(philosophy_items) == 2

    transfer_response = client.post(
        "/api/v1/plans/1/table1/transfer",
        json={
            "selections": [
                {"element_id": philosophy_items[0]["id"], "selected": True},
                {"element_id": philosophy_items[1]["id"], "selected": True},
            ]
        },
    )

    assert transfer_response.status_code == 400
