from typing import Dict

from fastapi import APIRouter
from sqlalchemy import func

from app.db import SessionLocal
from app.models import Program
from app.qdrant_client import PROGRAMS_COLLECTION_NAME, get_qdrant_client
from app.services.session_service import SessionService

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/system/status")
def system_status() -> Dict[str, object]:
    with SessionLocal() as db:
        programs = int(db.query(func.count(Program.id)).scalar() or 0)
        source_pages = int(db.query(func.count(func.distinct(Program.source_url))).scalar() or 0)

    vector_chunks = 0
    try:
        vector_chunks = int(
            get_qdrant_client().count(
                collection_name=PROGRAMS_COLLECTION_NAME,
                exact=True,
            ).count
        )
    except Exception:
        vector_chunks = 0

    sessions = SessionService()
    redis_connected = sessions.ping()

    return {
        "status": "ok",
        "redis_enabled": True,
        "redis_connected": redis_connected,
        "rate_limit_backend": "redis" if redis_connected else "local-fallback",
        "vector_chunks": vector_chunks,
        "programs": programs,
        "source_pages": source_pages,
    }
