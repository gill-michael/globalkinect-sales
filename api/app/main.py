"""FastAPI entry point for the Global Kinect sales-engine dashboard proxy API."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.routers import notion_proxy

DASHBOARD_ORIGIN = os.getenv("DASHBOARD_ORIGIN", "http://localhost:5174")

app = FastAPI(title="Global Kinect Sales Engine API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[DASHBOARD_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
    expose_headers=["X-Notion-Proxy-Error"],
)

app.include_router(notion_proxy.router, prefix="/api/notion", tags=["notion"])


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
