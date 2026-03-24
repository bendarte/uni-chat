from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    status: str


class DependencyStatus(BaseModel):
    ok: bool
    detail: Optional[str] = None


class ReadinessResponse(BaseModel):
    status: str
    ready: bool
    dependencies: Dict[str, DependencyStatus]


class Program(BaseModel):
    name: str
    university: str
    city: Optional[str] = None
    country: Optional[str] = None
    level: Optional[str] = None
    language: Optional[str] = None
    duration_years: Optional[int] = None
    study_pace: Optional[str] = None
    field: Optional[str] = None
    description: Optional[str] = None
    career_paths: Optional[str] = None
    tuition_eu: Optional[str] = None
    tuition_non_eu: Optional[str] = None
    source_url: Optional[str] = None


class ProgramCreate(Program):
    pass


class ProgramResponse(Program):
    id: UUID
    last_updated: datetime
    model_config = ConfigDict(from_attributes=True)


class ChatFilters(BaseModel):
    cities: Optional[List[str]] = None
    level: Optional[str] = None
    language: Optional[str] = None
    study_pace: Optional[str] = None
    field: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    filters: Optional[ChatFilters] = None

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class RecommendationItem(BaseModel):
    program_id: Optional[str] = None
    source_id: Optional[str] = None
    name: str
    university: str
    city: Optional[str] = None
    explanation: List[str]
    source_url: str
    score: Optional[float] = None


class Citation(BaseModel):
    program_id: str
    title: str
    university: str
    url: str
    snippet: str


class ChatResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    answer: str = ""
    questions: List[str] = []
    recommendations: List[RecommendationItem] = []
    citations: List[Citation] = []
    active_filters: Optional[Dict[str, Any]] = None


class IngestResponse(BaseModel):
    status: str
    crawled: int
    stored_in_postgres: int
    embedded_in_qdrant: int
