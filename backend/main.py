from fastapi import FastAPI


app = FastAPI(title="UP-MVP API", version="0.1.0")


@app.get("/api/v1/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
