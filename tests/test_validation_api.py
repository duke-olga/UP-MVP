from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.models import Competency, NormativeParam
from backend.routers import table2, validation


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
    app.include_router(validation.router)
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
        db.add_all(
            [
                Competency(code="УК-1", type="УК", name="УК 1", description="desc"),
                Competency(code="ОПК-1", type="ОПК", name="ОПК 1", description="desc"),
                Competency(code="ПКС-1", type="ПКС", name="ПКС 1", description="desc"),
            ]
        )
        db.commit()
    finally:
        db.close()

    return TestClient(app)


def test_validate_plan_saves_llm_recommendations(monkeypatch) -> None:
    client = _build_test_client()

    def fake_generate_recommendations(report):
        return f"LLM summary for report {report.id}"

    monkeypatch.setattr(validation, "generate_recommendations", fake_generate_recommendations)

    create_plan_response = client.post("/api/v1/plans", json={"name": "Plan with llm"})
    plan_id = create_plan_response.json()["data"]["id"]

    client.post(
        f"/api/v1/plans/{plan_id}/table2/elements",
        json={
            "name": "Философия",
            "block": "1",
            "part": "mandatory",
            "credits": 10.0,
            "semesters": [1],
            "competency_ids": [1],
            "source_element_id": None,
        },
    )

    response = client.post(f"/api/v1/plans/{plan_id}/validate")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["llm_recommendations"].startswith("LLM summary")
    assert len(body["results"]) > 0
