import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Program
from app.schemas import IngestResponse, ProgramCreate, ProgramResponse
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
    return [str(row[0]) for row in rows if row and str(row[0]).strip()]


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
