from fastapi import FastAPI
from sqlalchemy import text

from app.api.coach import router as coach_router
from app.core.config import settings
from app.db.session import engine


app = FastAPI(
    title=settings.app_name,
)


app.include_router(coach_router)


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.get("/health/db")
def health_db():

    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT 1")
        ).scalar()

    return {
        "status": "ok",
        "database": result == 1,
    }
