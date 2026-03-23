from collections import Counter, defaultdict
from typing import Dict, List
from urllib.parse import urlparse

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


@router.get("/sources/stats")
def source_stats() -> List[Dict[str, object]]:
    grouped = defaultdict(
        lambda: {
            "domain": "",
            "name_counts": Counter(),
            "page_urls": set(),
            "program_count": 0,
            "last_updated": None,
        }
    )

    with SessionLocal() as db:
        rows = (
            db.query(Program.university, Program.source_url, Program.last_updated)
            .filter(Program.source_url.isnot(None), Program.source_url != "")
            .all()
        )

    for row in rows:
        domain = urlparse(row.source_url).netloc.lower()
        bucket = grouped[domain]
        bucket["domain"] = domain
        bucket["name_counts"][row.university or "Unknown"] += 1
        bucket["page_urls"].add(row.source_url)
        bucket["program_count"] += 1
        if row.last_updated and (bucket["last_updated"] is None or row.last_updated > bucket["last_updated"]):
            bucket["last_updated"] = row.last_updated

    payload = []
    for bucket in grouped.values():
        payload.append(
            {
                "domain": bucket["domain"],
                "university": bucket["name_counts"].most_common(1)[0][0] if bucket["name_counts"] else "Unknown",
                "page_count": len(bucket["page_urls"]),
                "program_count": bucket["program_count"],
                "last_updated": bucket["last_updated"].isoformat() if bucket["last_updated"] else None,
            }
        )

    payload.sort(key=lambda item: (-int(item["program_count"]), str(item["university"])))
    return payload
