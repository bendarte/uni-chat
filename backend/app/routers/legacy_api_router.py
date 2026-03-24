import uuid
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.logging_utils import log_event
from app.services.chat_service import ChatService

router = APIRouter(tags=["legacy-api"])
logger = logging.getLogger("uvicorn.error")


class LegacyPreferences(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    city: Optional[str] = None
    level: Optional[str] = Field(default=None, alias="studyLevel")
    language: Optional[str] = None
    study_pace: Optional[str] = Field(default=None, alias="studyPace")


class LegacyChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    preferences: Optional[LegacyPreferences] = None

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


class LegacyCitation(BaseModel):
    source_id: str
    program_id: str
    title: str
    university: str
    url: str
    snippet: str


class LegacyRecommendation(BaseModel):
    program_id: str
    title: str
    university: str
    match_reason: str
    confidence: float
    source_ids: List[str]


class LegacyChatResponse(BaseModel):
    answer: str
    citations: List[LegacyCitation]
    recommended_programs: List[LegacyRecommendation]
    request_id: str
    blocked: bool
    block_reason: Optional[str] = None


def _normalize_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().lower()


def _to_filters(preferences: Optional[LegacyPreferences]) -> dict:
    if not preferences:
        return {}

    filters = {}
    if preferences.city:
        filters["cities"] = [preferences.city.strip()]
    if preferences.level:
        filters["level"] = _normalize_value(preferences.level)
    if preferences.language:
        filters["language"] = _normalize_value(preferences.language)
    if preferences.study_pace:
        filters["study_pace"] = _normalize_value(preferences.study_pace)
    return filters


@router.post("/api/chat", response_model=LegacyChatResponse)
def chat_legacy(request: Request, payload: LegacyChatRequest) -> LegacyChatResponse:
    started_at = time.perf_counter()
    service: ChatService = request.app.state.chat_service
    chat_result = service.handle_message(
        message=payload.message,
        filters=_to_filters(payload.preferences),
        conversation_id=payload.session_id,
    )

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    if chat_result.questions:
        answer = "Jag behöver lite mer information:\n- " + "\n- ".join(chat_result.questions)
        response = LegacyChatResponse(
            answer=answer,
            citations=[],
            recommended_programs=[],
            request_id=request_id,
            blocked=False,
        )
        log_event(
            logger,
            "info",
            "legacy_chat_request_completed",
            session_id=payload.session_id or "-",
            query_latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            recommendation_count=0,
            question_count=len(chat_result.questions),
            route="legacy",
        )
        return response

    recommendations: List[LegacyRecommendation] = []
    for index, rec in enumerate(chat_result.recommendations, start=1):
        deterministic_id = rec.program_id or str(
            uuid.uuid5(uuid.NAMESPACE_DNS, f"{rec.name}|{rec.university}|{index}")
        )
        source_id = rec.source_id or f"ref-{index}"
        match_reason = " ".join(rec.explanation)

        recommendations.append(
            LegacyRecommendation(
                program_id=deterministic_id,
                title=rec.name,
                university=rec.university,
                match_reason=match_reason,
                confidence=float(rec.score or 0.0),
                source_ids=[source_id],
            )
        )

    if recommendations:
        top = recommendations[0]
        answer = f"Toppmatch: {top.title} vid {top.university}. {top.match_reason}"
    else:
        answer = "Jag sammanställer de närmaste programmen utifrån din profil. Prova gärna att lägga till önskad stad eller nivå för ännu mer träffsäkra förslag."

    response = LegacyChatResponse(
        answer=answer,
        citations=[],
        recommended_programs=recommendations,
        request_id=request_id,
        blocked=False,
    )
    log_event(
        logger,
        "info",
        "legacy_chat_request_completed",
        session_id=payload.session_id or "-",
        query_latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
        recommendation_count=len(recommendations),
        question_count=0,
        route="legacy",
    )
    return response
