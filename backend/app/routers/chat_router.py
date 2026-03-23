import logging
import time

from fastapi import APIRouter, Request

from app.schemas import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("uvicorn.error")


@router.post("", response_model=ChatResponse)
def chat(request: Request, payload: ChatRequest) -> ChatResponse:
    started_at = time.perf_counter()
    service: ChatService = request.app.state.chat_service
    filters = payload.filters.model_dump(exclude_none=True) if payload.filters else None
    conversation_id = payload.conversation_id or payload.session_id
    response = service.handle_message(
        payload.message,
        filters=filters,
        conversation_id=conversation_id,
    )
    query_latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "chat_audit session_id=%s query_latency_ms=%s recommendation_count=%s question_count=%s",
        conversation_id or "-",
        query_latency_ms,
        len(response.recommendations),
        len(response.questions),
    )
    return response
