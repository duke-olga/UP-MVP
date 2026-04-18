from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import inspect, text

from backend.database import Base, SessionLocal, engine
from backend.modules.plan_builder import calculator as _calculator  # noqa: F401
from backend.modules.seed_ingest.loader import load_seed_data
from backend.routers import competencies, export, table1, table2, table3, validation


def _migrate_recommended_elements_semesters() -> None:
    inspector = inspect(engine)
    if "recommended_elements" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("recommended_elements")}
    if "semesters" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE recommended_elements ADD COLUMN semesters JSON"))
        if "semester" in columns:
            rows = connection.execute(text("SELECT id, semester FROM recommended_elements")).fetchall()
            for row in rows:
                semesters_json = "[]" if row.semester is None else f"[{int(row.semester)}]"
                connection.execute(
                    text("UPDATE recommended_elements SET semesters = :semesters WHERE id = :id"),
                    {"id": row.id, "semesters": semesters_json},
                )
        else:
            connection.execute(text("UPDATE recommended_elements SET semesters = '[]'"))


def _migrate_plan_elements_semesters() -> None:
    inspector = inspect(engine)
    if "plan_elements" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("plan_elements")}
    if "semesters" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE plan_elements ADD COLUMN semesters JSON"))
        if "semester" in columns:
            rows = connection.execute(text("SELECT id, semester FROM plan_elements")).fetchall()
            for row in rows:
                semesters_json = "[]" if row.semester is None else f"[{int(row.semester)}]"
                connection.execute(
                    text("UPDATE plan_elements SET semesters = :semesters WHERE id = :id"),
                    {"id": row.id, "semesters": semesters_json},
                )
        else:
            connection.execute(text("UPDATE plan_elements SET semesters = '[]'"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate_recommended_elements_semesters()
    _migrate_plan_elements_semesters()
    db = SessionLocal()
    try:
        load_seed_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="UP-MVP API", version="0.1.0", lifespan=lifespan)
app.include_router(competencies.router)
app.include_router(table1.router)
app.include_router(table2.router)
app.include_router(table3.router)
app.include_router(validation.router)
app.include_router(export.router)


@app.get("/api/v1/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
