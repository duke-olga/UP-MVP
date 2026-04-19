from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.models import Competency, NormativeParam
from backend.routers import export, table2


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
    app.include_router(table2.router)
    app.include_router(export.router)
    app.dependency_overrides[get_db] = override_get_db

    db = testing_session_local()
    try:
        db.add_all(
            [
                NormativeParam(key="X_total", value=240.0),
                NormativeParam(key="X_year", value=70.0),
                NormativeParam(key="X_b1", value=150.0),
                NormativeParam(key="X_b2", value=21.0),
                NormativeParam(key="X_b3", value=9.0),
                NormativeParam(key="X_mandatory_percent", value=0.4),
                NormativeParam(key="X_pe_ze", value=2.0),
                NormativeParam(key="X_pe_hours", value=72.0),
                NormativeParam(key="X_semester_max", value=35.0),
                NormativeParam(key="CreditHourRatio", value=36.0),
            ]
        )
        db.add(Competency(code="УК-1", type="УК", name="УК 1", description="desc"))
        db.commit()
    finally:
        db.close()

    return TestClient(app)


def test_export_xlsx_returns_downloadable_workbook() -> None:
    client = _build_test_client()

    create_plan_response = client.post("/api/v1/plans", json={"name": "Plan for export", "program_code": "090304"})
    plan_id = create_plan_response.json()["data"]["id"]

    client.post(
        f"/api/v1/plans/{plan_id}/table2/elements",
        json={
            "name": "Философия",
            "block": "1",
            "part": "mandatory",
            "credits": 3.0,
            "semesters": [1, 2],
            "competency_ids": [1],
            "source_element_id": None,
        },
    )

    response = client.get(f"/api/v1/plans/{plan_id}/export/xlsx")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert 'attachment; filename="plan_' in response.headers["content-disposition"]

    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook["Учебный план"]

    assert sheet["A1"].value == "Учебный план"
    assert sheet["A2"].value == "План: Plan for export"
    assert sheet["A6"].value == "Блок 1. Дисциплины"
    assert sheet["A7"].value == "Философия"
    assert sheet["D7"].value == "1, 2"
