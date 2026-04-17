from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.database import Base, SessionLocal, engine
from backend.modules.plan_builder import calculator as _calculator  # noqa: F401
from backend.modules.seed_ingest.loader import load_seed_data
from backend.routers import competencies


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        load_seed_data(db)
    finally:
        db.close()
    yield


app = FastAPI(title="UP-MVP API", version="0.1.0", lifespan=lifespan)
app.include_router(competencies.router)


@app.get("/api/v1/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
