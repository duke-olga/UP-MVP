from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.models import Competency, NormativeParam, RecommendedElement
from backend.routers import export, table1, table2, table3, validation


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
    app.include_router(table3.router)
    app.include_router(validation.router)
    app.include_router(export.router)
    app.dependency_overrides[get_db] = override_get_db

    db = testing_session_local()
    try:
        db.add_all(
            [
                NormativeParam(key="X_total", value=14.0),
                NormativeParam(key="X_year", value=14.0),
                NormativeParam(key="X_b1", value=10.0),
                NormativeParam(key="X_b2", value=3.0),
                NormativeParam(key="X_b3", value=1.0),
                NormativeParam(key="X_mandatory_percent", value=0.4),
                NormativeParam(key="X_pe_ze", value=2.0),
                NormativeParam(key="X_pe_hours", value=72.0),
                NormativeParam(key="CreditHourRatio", value=36.0),
            ]
        )

        uk = Competency(code="УК-1", type="УК", name="УК 1", description="desc")
        opk = Competency(code="ОПК-1", type="ОПК", name="ОПК 1", description="desc")
        pks = Competency(code="ПКС-1", type="ПКС", name="ПКС 1", description="desc")
        db.add_all([uk, opk, pks])
        db.flush()

        recommendations = [
            RecommendedElement(
                name="Философия",
                element_type="discipline",
                part="mandatory",
                credits=3.0,
                semester=1,
                source="poop",
                competencies=[uk],
            ),
            RecommendedElement(
                name="История",
                element_type="discipline",
                part="mandatory",
                credits=2.0,
                semester=1,
                source="poop",
                competencies=[uk],
            ),
            RecommendedElement(
                name="Иностранный язык",
                element_type="discipline",
                part="mandatory",
                credits=2.0,
                semester=1,
                source="poop",
                competencies=[uk],
            ),
            RecommendedElement(
                name="Безопасность жизнедеятельности",
                element_type="discipline",
                part="mandatory",
                credits=1.0,
                semester=1,
                source="poop",
                competencies=[uk],
            ),
            RecommendedElement(
                name="Физическая культура",
                element_type="discipline",
                part="mandatory",
                credits=2.0,
                semester=2,
                source="poop",
                competencies=[uk],
            ),
            RecommendedElement(
                name="Учебная практика",
                element_type="practice",
                part="mandatory",
                credits=2.0,
                semester=2,
                source="poop",
                competencies=[opk],
            ),
            RecommendedElement(
                name="Производственная практика",
                element_type="practice",
                part="mandatory",
                credits=1.0,
                semester=2,
                source="poop",
                competencies=[opk],
            ),
            RecommendedElement(
                name="Правоведение",
                element_type="discipline",
                part="variative",
                credits=2.0,
                semester=3,
                source="poop",
                competencies=[uk],
            ),
        ]
        db.add_all(recommendations)
        db.commit()
    finally:
        db.close()

    return TestClient(app)


def test_demo_flow_covers_mvp_scenario(monkeypatch) -> None:
    client = _build_test_client()

    monkeypatch.setattr(validation, "generate_recommendations", lambda report: "LLM demo recommendations")

    create_plan_response = client.post("/api/v1/plans", json={"name": "Demo plan"})
    assert create_plan_response.status_code == 200
    plan_id = create_plan_response.json()["data"]["id"]

    table1_response = client.get(f"/api/v1/plans/{plan_id}/table1")
    assert table1_response.status_code == 200
    table1_data = table1_response.json()["data"]
    assert len(table1_data) == 3
    assert any(section["mode"] == "manual_only" for section in table1_data)

    transfer_response = client.post(
        f"/api/v1/plans/{plan_id}/table1/transfer",
        json={"selections": []},
    )
    assert transfer_response.status_code == 200
    assert transfer_response.json()["data"]["created_count"] == 7

    blocked_approve = client.patch(f"/api/v1/plans/{plan_id}/status", json={"status": "approved"})
    assert blocked_approve.status_code == 400

    create_manual = client.post(
        f"/api/v1/plans/{plan_id}/table2/elements",
        json={
            "name": "ГИА",
            "block": "3",
            "part": "mandatory",
            "credits": 1.0,
            "semester": 4,
            "competency_ids": [3],
            "source_element_id": None,
        },
    )
    assert create_manual.status_code == 200

    table2_response = client.get(f"/api/v1/plans/{plan_id}/table2")
    assert table2_response.status_code == 200
    table2_data = table2_response.json()["data"]
    assert table2_data["aggregates"]["total_credits"] == 14.0
    assert table2_data["aggregates"]["by_block"]["3"] == 1.0

    table3_before_validate = client.get(f"/api/v1/plans/{plan_id}/table3")
    assert table3_before_validate.status_code == 200
    latest_before_validate = table3_before_validate.json()["data"]["latest_report"]
    assert latest_before_validate is not None
    assert len(latest_before_validate["results"]) > 0
    assert latest_before_validate["llm_recommendations"] is None

    validate_response = client.post(f"/api/v1/plans/{plan_id}/validate")
    assert validate_response.status_code == 200
    validate_body = validate_response.json()
    assert validate_body["llm_recommendations"] == "LLM demo recommendations"
    assert validate_body["results"] == []

    table3_after_validate = client.get(f"/api/v1/plans/{plan_id}/table3")
    assert table3_after_validate.status_code == 200
    latest_report = table3_after_validate.json()["data"]["latest_report"]
    assert latest_report is not None
    assert latest_report["llm_recommendations"] == "LLM demo recommendations"

    export_response = client.get(f"/api/v1/plans/{plan_id}/export/xlsx")
    assert export_response.status_code == 200
    workbook = load_workbook(BytesIO(export_response.content))
    assert workbook["Учебный план"]["A2"].value == "План: Demo plan"

    approve_response = client.patch(f"/api/v1/plans/{plan_id}/status", json={"status": "approved"})
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["status"] == "approved"
