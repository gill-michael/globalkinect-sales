"""FastAPI app for the new sales engine.

Two endpoints today:
  GET /healthz — public, returns {"status": "ok"}.
  GET /me      — Clerk-JWT-protected, returns the matched users row.

Run on port 8788 (Operator Console uses 8787 — do not collide):
  uvicorn sales_api.main:app --port 8788 --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sales_api.auth_middleware import UnauthorizedError, require_user
from sales_services.auth import prefetch_jwks

try:
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        prefetch_jwks()
        logger.info('Clerk JWKS pre-fetched at startup.')
    except Exception as exc:
        logger.warning('Eager JWKS fetch failed (will retry on first /me call): %s', exc)
    yield


app = FastAPI(title='Global Kinect Sales API', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.exception_handler(UnauthorizedError)
async def _unauth_handler(request: Request, exc: UnauthorizedError):
    return JSONResponse(status_code=401, content={'error': 'unauthorized'})


@app.get('/healthz')
async def healthz() -> dict:
    return {'status': 'ok'}


@app.get('/me')
async def me(user: dict = Depends(require_user)) -> dict:
    return user
