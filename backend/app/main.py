from collections import OrderedDict
import logging
import secrets
import threading
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import redis

from app.config import settings
from app.db import Base, engine, ensure_program_schema
from app.logging_utils import bind_request_id, ensure_request_id, log_event, reset_request_id
from app.qdrant_client import ensure_program_collection
from app.routers.chat_router import router as chat_router
from app.routers.health_router import router as health_router
from app.routers.legacy_api_router import router as legacy_api_router
from app.routers.program_router import router as program_router
from app.routers.system_router import router as system_router
from app.services.chat_service import ChatService

MAX_RATE_LIMIT_FALLBACK_ENTRIES = 10_000
_rate_limit_fallback = OrderedDict()
_rate_limit_lock = threading.Lock()
_redis_rate_limiter = None


def _remember_rate_limit_entry(identifier: str, record: dict[str, float]) -> None:
    if identifier in _rate_limit_fallback:
        _rate_limit_fallback.pop(identifier, None)
    _rate_limit_fallback[identifier] = record
    while len(_rate_limit_fallback) > MAX_RATE_LIMIT_FALLBACK_ENTRIES:
        _rate_limit_fallback.popitem(last=False)


def _get_rate_limit_identifier(request: Request) -> str:
    client_id = (request.headers.get("X-Client-Id") or "").strip()
    if client_id:
        return f"client:{client_id}"
    if request.client and request.client.host:
        return f"ip:{request.client.host}"
    return "anonymous"


def _get_redis_rate_limiter():
    global _redis_rate_limiter
    if _redis_rate_limiter is None:
        _redis_rate_limiter = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            health_check_interval=30,
            retry_on_timeout=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_rate_limiter


def _check_local_rate_limit(identifier: str) -> tuple[bool, int]:
    now = time.time()
    window = settings.rate_limit_window_seconds
    limit = settings.rate_limit_max_requests
    with _rate_limit_lock:
        record = _rate_limit_fallback.get(identifier)
        if not record or record["reset_at"] <= now:
            _remember_rate_limit_entry(
                identifier,
                {"count": 1, "reset_at": now + window},
            )
            return True, window

        record["count"] += 1
        _remember_rate_limit_entry(identifier, record)
        retry_after = max(1, int(record["reset_at"] - now))
        allowed = record["count"] <= limit
        return allowed, retry_after


def _check_rate_limit(request: Request) -> tuple[bool, int, str]:
    identifier = _get_rate_limit_identifier(request)
    if not settings.rate_limit_enabled:
        return True, 0, "disabled"

    try:
        client = _get_redis_rate_limiter()
        key = f"rate_limit:{identifier}"
        current = int(client.incr(key))
        if current == 1:
            client.expire(key, settings.rate_limit_window_seconds)
        ttl = int(client.ttl(key))
        retry_after = ttl if ttl and ttl > 0 else settings.rate_limit_window_seconds
        return current <= settings.rate_limit_max_requests, retry_after, "redis"
    except Exception:
        allowed, retry_after = _check_local_rate_limit(identifier)
        return allowed, retry_after, "local-fallback"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    Base.metadata.create_all(bind=engine)
    ensure_program_schema()
    ensure_program_collection()
    app.state.chat_service = ChatService()
    yield


app = FastAPI(title="University Recommendation Backend", lifespan=lifespan)

_cors_origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins else [],
    allow_credentials=bool(_cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key", "X-Client-Id"],
)


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if request.url.path in {"/health", "/ready"}:
        return await call_next(request)

    expected_api_key = settings.backend_api_key.strip()
    if not expected_api_key:
        log_event(
            logging.getLogger("uvicorn.error"),
            "error",
            "backend_api_key_missing",
            path=request.url.path,
        )
        return JSONResponse(status_code=503, content={"detail": "Server misconfigured"})

    provided_api_key = request.headers.get("X-API-Key", "").strip()
    if not provided_api_key or not secrets.compare_digest(provided_api_key, expected_api_key):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    return await call_next(request)


@app.middleware("http")
async def rate_limit_requests(request: Request, call_next):
    if request.url.path in {"/health", "/ready"}:
        return await call_next(request)

    allowed, retry_after, backend = _check_rate_limit(request)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "backend": backend},
            headers={"Retry-After": str(retry_after)},
        )

    response = await call_next(request)
    if settings.rate_limit_enabled and retry_after > 0:
        response.headers["X-RateLimit-Backend"] = backend
    return response


@app.middleware("http")
async def attach_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id", "").strip() or str(uuid4())
    request.state.request_id = request_id
    token = bind_request_id(request_id)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_event(
            logging.getLogger("uvicorn.error"),
            "info",
            "http_request",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
            duration_ms=duration_ms,
        )
        reset_request_id(token)

    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger = logging.getLogger("uvicorn.error")
    if exc.status_code >= 500:
        bind_token = bind_request_id(ensure_request_id(request))
        log_event(logger, "error", "http_exception", path=request.url.path, detail=exc.detail)
        reset_request_id(bind_token)
        return JSONResponse(status_code=exc.status_code, content={"detail": "Internal server error"})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger = logging.getLogger("uvicorn.error")
    bind_token = bind_request_id(ensure_request_id(request))
    log_event(logger, "error", "unhandled_exception", path=request.url.path, error=str(exc))
    reset_request_id(bind_token)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health_router)
app.include_router(program_router)
app.include_router(chat_router)
app.include_router(legacy_api_router)
app.include_router(system_router)
