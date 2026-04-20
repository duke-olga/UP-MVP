from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import inspect, text

from backend.database import Base, SessionLocal, engine
from backend.modules.plan_builder import calculator as _calculator  # noqa: F401
from backend.modules.seed_ingest.loader import load_seed_data
from backend.routers import chat, competencies, export, table1, table2, table3, validation
from backend.schemas import HealthResponse, HealthResponseWrapper


def _ensure_column(table_name: str, column_name: str, ddl: str, default_sql: str | None = None) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in columns:
        return

    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
        if default_sql:
            connection.execute(text(f"UPDATE {table_name} SET {column_name} = {default_sql}"))


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


def _migrate_extended_fields() -> None:
    _ensure_column("recommended_elements", "program_code", "VARCHAR(20)")
    _ensure_column("recommended_elements", "extra_hours", "FLOAT", "0")
    _ensure_column("recommended_elements", "practice_type", "VARCHAR(30)")
    _ensure_column("recommended_elements", "is_fgos_mandatory", "INTEGER", "0")
    _ensure_column("recommended_elements", "fgos_requirement", "VARCHAR(100)")
    _ensure_column("recommended_elements", "source_name", "VARCHAR(255)")

    _ensure_column("curriculum_plans", "program_code", "VARCHAR(20)", "''")
    _ensure_column("plan_elements", "extra_hours", "FLOAT", "0")
    _ensure_column("plan_elements", "practice_type", "VARCHAR(30)")
    _ensure_column("plan_elements", "fgos_requirement", "VARCHAR(100)")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate_recommended_elements_semesters()
    _migrate_plan_elements_semesters()
    _migrate_extended_fields()
    db = SessionLocal()
    try:
        load_seed_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="UP-MVP API", version="0.1.0", lifespan=lifespan)
app.include_router(chat.router)
app.include_router(competencies.router)
app.include_router(table1.router)
app.include_router(table2.router)
app.include_router(table3.router)
app.include_router(validation.router)
app.include_router(export.router)


@app.get("/api/v1/health", response_model=HealthResponseWrapper)
def healthcheck() -> HealthResponseWrapper:
    return HealthResponseWrapper(data=HealthResponse(status="ok"))
