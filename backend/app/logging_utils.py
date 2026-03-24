import json
import logging
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from fastapi import Request

_request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


def ensure_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", "").strip() if hasattr(request.state, "request_id") else ""
    if request_id:
        return request_id

    header_request_id = request.headers.get("X-Request-Id", "").strip()
    request_id = header_request_id or str(uuid4())
    request.state.request_id = request_id
    return request_id


def bind_request_id(request_id: str):
    return _request_id_context.set(request_id)


def reset_request_id(token) -> None:
    _request_id_context.reset(token)


def current_request_id() -> str:
    return _request_id_context.get()


def log_event(logger: logging.Logger, level: str, event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "request_id": current_request_id(),
        **fields,
    }
    getattr(logger, level)(json.dumps(payload, ensure_ascii=False, default=str))
