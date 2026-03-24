import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import engine
from app.logging_utils import log_event
from app.qdrant_client import PROGRAMS_COLLECTION_NAME, get_qdrant_client
from app.schemas import DependencyStatus, HealthResponse, ReadinessResponse
from app.services.session_service import SessionService

router = APIRouter(tags=["health"])
logger = logging.getLogger("uvicorn.error")


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


def _check_postgres() -> DependencyStatus:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return DependencyStatus(ok=True)
    except Exception as exc:
        log_event(logger, "warning", "postgres_readiness_failed", error=str(exc))
        return DependencyStatus(ok=False, detail=str(exc))


def _check_redis() -> DependencyStatus:
    try:
        if SessionService().ping():
            return DependencyStatus(ok=True)
        log_event(logger, "warning", "redis_readiness_failed", error="Redis ping returned false")
        return DependencyStatus(ok=False, detail="Redis ping returned false")
    except Exception as exc:
        log_event(logger, "warning", "redis_readiness_failed", error=str(exc))
        return DependencyStatus(ok=False, detail=str(exc))


def _check_qdrant() -> DependencyStatus:
    try:
        get_qdrant_client().count(
            collection_name=PROGRAMS_COLLECTION_NAME,
            exact=True,
        )
        return DependencyStatus(ok=True)
    except Exception as exc:
        log_event(logger, "warning", "qdrant_readiness_failed", error=str(exc))
        return DependencyStatus(ok=False, detail=str(exc))


@router.get("/ready", response_model=ReadinessResponse)
def readiness_check() -> JSONResponse:
    dependencies = {
        "postgres": _check_postgres(),
        "redis": _check_redis(),
        "qdrant": _check_qdrant(),
    }
    ready = all(dependency.ok for dependency in dependencies.values())
    payload = ReadinessResponse(
        status="ok" if ready else "degraded",
        ready=ready,
        dependencies=dependencies,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )
