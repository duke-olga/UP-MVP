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


def test_create_plan_and_table2_crud_flow() -> None:
    client = _build_test_client()

    create_plan_response = client.post("/api/v1/plans", json={"name": "Test plan"})
    assert create_plan_response.status_code == 200
    plan_id = create_plan_response.json()["data"]["id"]

    create_element_response = client.post(
        f"/api/v1/plans/{plan_id}/table2/elements",
        json={
            "name": "Программирование",
            "block": "1",
            "part": "mandatory",
            "credits": 3.0,
            "semesters": [1, 2],
            "competency_ids": [1, 2],
            "source_element_id": None,
        },
    )
    assert create_element_response.status_code == 200
    element = create_element_response.json()["data"]
    assert element["hours"] == 108
    assert element["semesters"] == [1, 2]

    element_id = element["id"]
    update_element_response = client.patch(
        f"/api/v1/plans/{plan_id}/table2/elements/{element_id}",
        json={"credits": 4.0, "semesters": [2, 3]},
    )
    assert update_element_response.status_code == 200
    assert update_element_response.json()["data"]["hours"] == 144
    assert update_element_response.json()["data"]["semesters"] == [2, 3]

    table2_response = client.get(f"/api/v1/plans/{plan_id}/table2")
    assert table2_response.status_code == 200
    data = table2_response.json()["data"]
    assert data["aggregates"]["total_credits"] == 4.0
    assert data["aggregates"]["by_block"]["1"] == 4.0
    assert data["aggregates"]["by_year"]["1"] == 2.0
    assert data["aggregates"]["by_year"]["2"] == 2.0
    assert len(data["grouped_elements"]["1"]["mandatory"]) == 1

    delete_element_response = client.delete(f"/api/v1/plans/{plan_id}/table2/elements/{element_id}")
    assert delete_element_response.status_code == 200
    assert delete_element_response.json()["data"]["deleted"] is True


def test_delete_plan_removes_plan() -> None:
    client = _build_test_client()

    create_plan_response = client.post("/api/v1/plans", json={"name": "Delete me"})
    plan_id = create_plan_response.json()["data"]["id"]

    delete_response = client.delete(f"/api/v1/plans/{plan_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["data"] == {"deleted": True, "plan_id": plan_id}

    list_response = client.get("/api/v1/plans")
    ids = [item["id"] for item in list_response.json()["data"]]
    assert plan_id not in ids


def test_approve_is_blocked_when_validation_has_errors() -> None:
    client = _build_test_client()

    create_plan_response = client.post("/api/v1/plans", json={"name": "Invalid plan"})
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

    approve_response = client.patch(
        f"/api/v1/plans/{plan_id}/status",
        json={"status": "approved"},
    )

    assert approve_response.status_code == 400
    assert "cannot be approved" in approve_response.json()["detail"]


def test_table2_filters_unknown_competency_ids() -> None:
    client = _build_test_client()

    create_plan_response = client.post("/api/v1/plans", json={"name": "Filtered competencies"})
    plan_id = create_plan_response.json()["data"]["id"]

    create_element_response = client.post(
        f"/api/v1/plans/{plan_id}/table2/elements",
        json={
            "name": "Программирование",
            "block": "1",
            "part": "mandatory",
            "credits": 3.0,
            "semesters": [1],
            "competency_ids": [1, 999, 2],
            "source_element_id": None,
        },
    )
    assert create_element_response.status_code == 200
    assert create_element_response.json()["data"]["competency_ids"] == [1, 2]

    element_id = create_element_response.json()["data"]["id"]
    update_element_response = client.patch(
        f"/api/v1/plans/{plan_id}/table2/elements/{element_id}",
        json={"competency_ids": [2, 12345]},
    )
    assert update_element_response.status_code == 200
    assert update_element_response.json()["data"]["competency_ids"] == [2]

    table2_response = client.get(f"/api/v1/plans/{plan_id}/table2")
    elements = table2_response.json()["data"]["grouped_elements"]["1"]["mandatory"]
    assert elements[0]["competency_ids"] == [2]
