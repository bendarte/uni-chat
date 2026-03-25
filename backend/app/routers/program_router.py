import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Program
from app.schemas import IngestResponse, ProgramCreate, ProgramResponse
from app.services.metadata_normalization import display_city, is_country_name
from app.services.source_validation import normalize_source_url
from scripts.ingest_all import ingest_all as run_ingestion_pipeline

router = APIRouter(tags=["programs"])


def require_admin_api_key(request: Request) -> None:
    expected_api_key = settings.admin_api_key.strip()
    if not expected_api_key:
        raise HTTPException(status_code=503, detail="Admin API key not configured")

    provided_api_key = request.headers.get("X-Admin-API-Key", "").strip()
    if not provided_api_key or not secrets.compare_digest(provided_api_key, expected_api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/programs", response_model=List[ProgramResponse])
def list_programs(db: Session = Depends(get_db)) -> List[ProgramResponse]:
    programs = db.query(Program).order_by(Program.last_updated.desc()).all()
    for program in programs:
        program.source_url = normalize_source_url(program.source_url)
    return programs


@router.get("/programs/cities", response_model=List[str])
def list_program_cities(db: Session = Depends(get_db)) -> List[str]:
    rows = (
        db.query(Program.city)
        .filter(Program.city.isnot(None), Program.city != "", func.lower(Program.city) != "multiple locations")
        .distinct()
        .order_by(Program.city.asc())
        .all()
    )
    cities: List[str] = []
    seen = set()
    for row in rows:
        if not row:
            continue
        raw_value = str(row[0]).strip()
        if not raw_value or is_country_name(raw_value):
            continue
        label = display_city(raw_value)
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        cities.append(label)
    return cities


@router.post("/programs", response_model=ProgramResponse, dependencies=[Depends(require_admin_api_key)])
def create_program(
    payload: ProgramCreate, db: Session = Depends(get_db)
) -> ProgramResponse:
    data = payload.model_dump()
    data["source_url"] = normalize_source_url(data.get("source_url"))
    program = Program(**data)
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


@router.post("/ingest", response_model=IngestResponse, dependencies=[Depends(require_admin_api_key)])
def ingest_programs() -> IngestResponse:
    result = run_ingestion_pipeline()
    return IngestResponse(status="ok", **result)
