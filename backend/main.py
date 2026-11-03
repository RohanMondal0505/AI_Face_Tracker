"""Application entry point: python -m uvicorn backend.main:app --reload."""

from fastapi import FastAPI

from .routers import health, tracking

app = FastAPI(title="AI Face Tracker")

app.include_router(health.router)
app.include_router(tracking.router)
